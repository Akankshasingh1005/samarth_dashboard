"""
PS3 Sensor Hub — Mock Service
Simulates ESP32 exoskeleton data until real hardware is connected.
Generates realistic joint angles, motor status, and foot force data.
"""
import random
import math
import time
from typing import Optional

from .schemas import (
    SensorReading, SensorAccelerometer, SensorGyroscope,
    ExoSensorData, ExoMotorStatus,
)


class MockSensorHub:
    """
    Simulates PS3 exoskeleton sensor data.
    Returns simulated joint angles and motor status.

    To integrate real PS3:
    1. Set PS3_ESP_URL to the ESP32's IP address in .env
    2. Set PS3_USE_REAL_SENSOR=true in .env
    3. System auto-switches to RealSensorHub
    """

    def __init__(self):
        self._commands_sent = 0
        self._last_command: Optional[dict] = None
        self._start_time = time.time()

    @property
    def is_connected(self) -> bool:
        return False

    @property
    def commands_sent(self) -> int:
        return self._commands_sent

    @property
    def last_command(self) -> Optional[dict]:
        return self._last_command

    def get_status(self) -> SensorReading:
        """Return simulated 'disconnected' sensor status."""
        from backend_config import settings
        return SensorReading(
            connected=False,
            device_id="SIM-EXO-001",
            battery_percent=0,
            signal_strength=0,
            calibration_status="uncalibrated",
            connection_status="disconnected",
            ps3_mode="simulated",
            exo=None,
            esp_url=getattr(settings, "PS3_ESP_URL", ""),
        )

    def get_data(self) -> SensorReading:
        """Return simulated exoskeleton status. No mock data is returned when disconnected."""
        from backend_config import settings
        return SensorReading(
            connected=False,
            device_id="SIM-EXO-001",
            battery_percent=0,
            signal_strength=0,
            calibration_status="uncalibrated",
            connection_status="disconnected",
            accelerometer=SensorAccelerometer(),
            gyroscope=SensorGyroscope(),
            temperature_celsius=0.0,
            ps3_mode="simulated",
            exo=None,
            esp_url=getattr(settings, "PS3_ESP_URL", ""),
        )

    def get_exo_data(self) -> ExoSensorData:
        """Return simulated exoskeleton data."""
        reading = self.get_data()
        return reading.exo or ExoSensorData()

    def poll_once(self) -> SensorReading:
        """Simulated single poll."""
        return self.get_data()

    def connect(self, port: str = "") -> dict:
        return {"success": False, "message": "PS3 hardware not connected. Simulated mode active."}

    def disconnect(self) -> dict:
        return {"success": True, "message": "Simulated sensor disconnected."}

    def calibrate(self) -> dict:
        return {"success": False, "message": "Calibration requires PS3 hardware connection."}

    def send_command(self, command: dict) -> dict:
        """Stub: log the command but don't do anything."""
        self._commands_sent += 1
        self._last_command = command
        return {"success": False, "message": "Simulated mode — command not sent to hardware."}
