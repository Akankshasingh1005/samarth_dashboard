"""
PS3 Sensor Hub — Schemas and Mock Service
Simulates wearable IMU sensor data until PS3 hardware integration is complete.
"""
import random
import math
import time
from typing import Literal, Optional
from pydantic import BaseModel, Field


class SensorAccelerometer(BaseModel):
    x: float = 0.0
    y: float = 0.0
    z: float = 9.81  # gravity baseline


class SensorGyroscope(BaseModel):
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


class SensorReading(BaseModel):
    """Single sensor data frame — matches expected PS3 hardware output."""
    connected: bool = False
    device_id: Optional[str] = None
    battery_percent: int = 0
    signal_strength: int = 0  # dBm
    calibration_status: Literal["uncalibrated", "calibrating", "calibrated"] = "uncalibrated"
    connection_status: Literal["disconnected", "connecting", "connected"] = "disconnected"
    accelerometer: SensorAccelerometer = Field(default_factory=SensorAccelerometer)
    gyroscope: SensorGyroscope = Field(default_factory=SensorGyroscope)
    temperature_celsius: float = 0.0
    timestamp: float = Field(default_factory=time.time)
    ps3_mode: Literal["simulated", "real"] = "simulated"


class MockSensorHub:
    """
    Simulates PS3 IMU sensor data.
    Returns flat/noisy signals when disconnected (simulated).

    To integrate PS3:
    1. Create RealSensorHub implementing the same interface
    2. Set PS3_SENSOR_PORT and PS3_USE_REAL_SENSOR=true in .env
    3. System auto-switches
    """

    def get_status(self) -> SensorReading:
        """Return simulated 'disconnected' sensor status."""
        return SensorReading(
            connected=False,
            device_id="SIM-001",
            battery_percent=0,
            signal_strength=0,
            calibration_status="uncalibrated",
            connection_status="disconnected",
            ps3_mode="simulated",
        )

    def get_data(self) -> SensorReading:
        """Return simulated sensor data (slight noise around zero)."""
        t = time.time()
        noise = lambda: random.gauss(0, 0.05)
        return SensorReading(
            connected=False,
            device_id="SIM-001",
            battery_percent=random.randint(78, 85),
            signal_strength=-65,
            calibration_status="uncalibrated",
            connection_status="disconnected",
            accelerometer=SensorAccelerometer(
                x=noise(),
                y=noise(),
                z=9.81 + noise(),
            ),
            gyroscope=SensorGyroscope(
                x=noise() * 0.1,
                y=noise() * 0.1,
                z=noise() * 0.1,
            ),
            temperature_celsius=36.5 + noise() * 0.2,
            ps3_mode="simulated",
        )

    def connect(self, port: str) -> dict:
        return {"success": False, "message": "PS3 hardware not yet integrated. Simulated mode active."}

    def calibrate(self) -> dict:
        return {"success": False, "message": "Calibration requires PS3 hardware connection."}


_sensor_hub: MockSensorHub | None = None


def get_sensor_hub() -> MockSensorHub:
    global _sensor_hub
    if _sensor_hub is None:
        _sensor_hub = MockSensorHub()
    return _sensor_hub
