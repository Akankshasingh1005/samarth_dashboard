"""
PS3 Sensor Hub — Real ESP32 Exoskeleton Hardware Driver
========================================================
Communicates with an ESP32-based motorized exoskeleton over Wi-Fi (HTTP).
The ESP32 sends processed joint angles, motor status, and foot force data.
The dashboard sends PS2 mode commands back for adaptive motor control.

Device: Hip-to-ankle motorized exoskeleton
  - Knee actuator (PWM-controlled, bidirectional ext/flex)
  - Hip actuator (PWM-controlled, bidirectional ext/flex)
  - Foot force sensor for stance detection
  - ESP32 computes joint angles onboard from IMU

Activated when PS3_USE_REAL_SENSOR=true and PS3_ESP_URL is set in .env.
"""
import time
import math
from typing import Optional, Dict, Any
from loguru import logger

from .schemas import (
    SensorReading, SensorAccelerometer, SensorGyroscope,
    ExoSensorData, ExoMotorStatus, SensorCommand,
)


class RealSensorHub:
    """
    Real PS3 sensor hub that communicates with ESP32 exoskeleton over Wi-Fi.

    The ESP32 serves a simple HTTP API:
      GET  /data      → returns latest exo data JSON frame
      GET  /status    → returns device status (battery, calibration, etc.)
      POST /command   → accepts mode/torque commands for the motors
      POST /calibrate → triggers motor homing/zeroing
    """

    def __init__(self, esp_url: str = "", poll_interval_ms: int = 100):
        self._esp_url = esp_url.rstrip("/") if esp_url else ""
        self._poll_interval = poll_interval_ms / 1000.0
        self._connected = False
        self._device_id: Optional[str] = None
        self._latest_reading = SensorReading()
        self._latest_exo = ExoSensorData()
        self._calibration_status = "uncalibrated"
        self._battery_percent = 0
        self._last_data_time = 0.0
        self._commands_sent = 0
        self._last_command: Optional[Dict] = None
        self._heartbeat_timeout = 10.0
        self._reconnect_interval = 5.0
        self._last_connect_attempt = 0.0
        self._thread = None
        self._stop_event = None

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def commands_sent(self) -> int:
        return self._commands_sent

    @property
    def last_command(self) -> Optional[Dict]:
        return self._last_command

    def _background_poll_loop(self):
        import httpx
        logger.info(f"[PS3] Background thread started for ESP32 at {self._esp_url}")
        
        last_retry = 0.0
        # Reuse Client to leverage HTTP connection pooling (keep-alive)
        with httpx.Client(timeout=1.0) as client:
            while not self._stop_event.is_set():
                if not self._connected:
                    # Attempt connection in background
                    now = time.time()
                    if now - last_retry >= self._reconnect_interval:
                        last_retry = now
                        self._last_connect_attempt = now
                        try:
                            resp = client.get(f"{self._esp_url}/status")
                            if resp.status_code == 200:
                                data = resp.json()
                                self._device_id = data.get("device_id", "ESP32-EXO")
                                self._calibration_status = data.get("calibration_status", "uncalibrated")
                                self._battery_percent = data.get("battery_percent", data.get("bat", 100))
                                self._connected = True
                                self._last_data_time = time.time()
                                logger.info(f"[PS3] Connected to ESP32 in background thread at {self._esp_url}")
                        except Exception:
                            pass
                
                if self._connected:
                    try:
                        resp = client.get(f"{self._esp_url}/data")
                        if resp.status_code == 200:
                            raw = resp.json()
                            self._latest_exo = self._parse_exo_data(raw)
                            self._latest_reading = self._build_reading()
                            self._last_data_time = time.time()
                    except Exception as e:
                        logger.debug(f"[PS3] Background poll failed: {e}")
                        # Mark disconnected if heartbeat elapsed
                        if time.time() - self._last_data_time > self._heartbeat_timeout:
                            self._connected = False
                            
                time.sleep(self._poll_interval)
        logger.info("[PS3] Background thread stopped")

    def connect(self, port: str = "") -> dict:
        """
        Connect to ESP32 hardware and start background polling thread.
        `port` parameter accepts URL for compatibility.
        """
        url = port if port.startswith("http") else self._esp_url
        if not url:
            return {"success": False, "message": "No ESP32 URL configured. Set PS3_ESP_URL in .env"}

        self._esp_url = url.rstrip("/")
        self._last_connect_attempt = time.time()

        try:
            import httpx
            with httpx.Client(timeout=1.5) as client:
                try:
                    resp = client.get(f"{self._esp_url}/status")
                    if resp.status_code == 200:
                        data = resp.json()
                        self._device_id = data.get("device_id", "ESP32-EXO")
                        self._calibration_status = data.get("calibration_status", "uncalibrated")
                        self._battery_percent = data.get("battery_percent", data.get("bat", 100))
                except Exception:
                    pass

                resp = client.get(f"{self._esp_url}/data")
                if resp.status_code == 200:
                    self._connected = True
                    self._last_data_time = time.time()
                    if not self._device_id:
                        self._device_id = "ESP32-EXO"
                    raw = resp.json()
                    self._latest_exo = self._parse_exo_data(raw)
                    self._latest_reading = self._build_reading()
                    
                    # Start background thread if not already running
                    if self._thread is None or not self._thread.is_alive():
                        import threading
                        self._stop_event = threading.Event()
                        self._thread = threading.Thread(target=self._background_poll_loop, daemon=True)
                        self._thread.start()
                        
                    logger.info(f"[PS3] Connected to ESP32 exoskeleton at {self._esp_url}")
                    return {"success": True, "message": f"Connected to {self._device_id}", "device_id": self._device_id}
                else:
                    self._connected = False
                    return {"success": False, "message": f"ESP32 responded with HTTP {resp.status_code}"}
        except Exception as e:
            logger.warning(f"[PS3] Could not reach ESP32 at {self._esp_url}: {e}")
            self._connected = False
            return {"success": False, "message": f"Cannot reach ESP32 at {self._esp_url}: {e}"}

    def disconnect(self) -> dict:
        """Disconnect from ESP32 hardware and stop background thread."""
        if self._stop_event:
            self._stop_event.set()
        self._connected = False
        self._thread = None
        logger.info("[PS3] Disconnected from ESP32 exoskeleton")
        return {"success": True, "message": "Disconnected from ESP32"}

    def get_status(self) -> SensorReading:
        """Return current connection state and device info."""
        if self._connected and (time.time() - self._last_data_time > self._heartbeat_timeout):
            logger.warning("[PS3] Heartbeat timeout — marking ESP32 as disconnected")
            self._connected = False
            
        if not self._connected:
            if self._thread is None or not self._thread.is_alive():
                # Start background thread to handle reconnection retries
                import threading
                self._stop_event = threading.Event()
                self._thread = threading.Thread(target=self._background_poll_loop, daemon=True)
                self._thread.start()

        return self._build_reading()

    def get_data(self) -> SensorReading:
        """Return latest cached data from ESP32."""
        if self._connected and (time.time() - self._last_data_time > self._heartbeat_timeout):
            self._connected = False
        if not self._connected:
            return self._disconnected_reading()
        return self._latest_reading

    def get_exo_data(self) -> ExoSensorData:
        """Return latest cached exoskeleton-specific data."""
        return self._latest_exo

    def poll_once(self) -> SensorReading:
        """
        Instantly return cached ESP32 reading without blocking the websocket frame handler.
        """
        # Trigger status check to handle reconnects in the background thread
        self.get_status()
        return self._latest_reading

    def calibrate(self) -> dict:
        """Send calibration/motor-homing command to ESP32."""
        if not self._connected or not self._esp_url:
            return {"success": False, "message": "ESP32 not connected"}

        try:
            import httpx
            self._calibration_status = "calibrating"
            with httpx.Client(timeout=5.0) as client:
                resp = client.post(f"{self._esp_url}/calibrate")
                if resp.status_code == 200:
                    data = resp.json()
                    self._calibration_status = data.get("calibration_status", "calibrated")
                    logger.info(f"[PS3] Calibration result: {self._calibration_status}")
                    return {"success": True, "message": f"Calibration: {self._calibration_status}"}
                else:
                    self._calibration_status = "uncalibrated"
                    return {"success": False, "message": f"Calibration failed (HTTP {resp.status_code})"}
        except Exception as e:
            self._calibration_status = "uncalibrated"
            return {"success": False, "message": f"Calibration error: {e}"}

    def send_command(self, command: dict) -> dict:
        """
        Send a mode/torque command to ESP32 for motor control.
        PS2 → PS3 bridge: PS2 analyzes a rep, produces mode_command,
        which gets forwarded here to adjust the exoskeleton motors.
        The ESP32 then applies the PWM/direction changes and sends back
        updated sensor data in the next poll cycle.
        """
        if not self._connected or not self._esp_url:
            return {"success": False, "message": "ESP32 not connected"}

        try:
            import httpx
            with httpx.Client(timeout=2.0) as client:
                resp = client.post(f"{self._esp_url}/command", json=command)
                if resp.status_code == 200:
                    self._commands_sent += 1
                    self._last_command = command
                    logger.info(f"[PS3] Command sent to ESP32: {command}")
                    return {"success": True, "message": "Command sent to ESP32"}
                else:
                    return {"success": False, "message": f"Command failed (HTTP {resp.status_code})"}
        except Exception as e:
            logger.warning(f"[PS3] Command send failed: {e}")
            return {"success": False, "message": f"Command error: {e}"}

    def _parse_exo_data(self, raw: dict) -> ExoSensorData:
        """
        Parse one ESP32 JSON response into ExoSensorData.
        Actual format:
        {
            "knee_angle": 75.3, "hip_angle": 45.1, "foot_force": 3.42,
            "stance": true, "knee_pwm": 95, "knee_dir": "ext",
            "hip_pwm": 60, "hip_dir": "ext", "motors": "on"
        }
        """
        try:
            return ExoSensorData(
                knee_angle=float(raw.get("knee_angle", 0)),
                hip_angle=float(raw.get("hip_angle", 0)),
                foot_force=float(raw.get("foot_force", 0)),
                stance=bool(raw.get("stance", False)),
                knee_motor=ExoMotorStatus(
                    pwm=int(raw.get("knee_pwm", 0)),
                    direction=str(raw.get("knee_dir", "ext")),
                ),
                hip_motor=ExoMotorStatus(
                    pwm=int(raw.get("hip_pwm", 0)),
                    direction=str(raw.get("hip_dir", "ext")),
                ),
                motors_active=str(raw.get("motors", "off")).lower() == "on",
            )
        except Exception as e:
            logger.warning(f"[PS3] Exo data parse error: {e}, raw={raw}")
            return ExoSensorData()

    def _build_reading(self) -> SensorReading:
        """Build a SensorReading from the latest exo data."""
        exo = self._latest_exo
        return SensorReading(
            connected=self._connected,
            device_id=self._device_id,
            battery_percent=self._battery_percent,
            signal_strength=-50 if self._connected else 0,
            calibration_status=self._calibration_status,
            connection_status="connected" if self._connected else "disconnected",
            accelerometer=SensorAccelerometer(),
            gyroscope=SensorGyroscope(),
            temperature_celsius=0.0,
            ps3_mode="real",
            exo=exo,
            esp_url=self._esp_url,
        )

    def _disconnected_reading(self) -> SensorReading:
        """Return a reading that indicates the hardware is not connected."""
        return SensorReading(
            connected=False,
            device_id=self._device_id,
            battery_percent=0,
            signal_strength=0,
            calibration_status="uncalibrated",
            connection_status="disconnected",
            ps3_mode="real",
            esp_url=self._esp_url,
        )
