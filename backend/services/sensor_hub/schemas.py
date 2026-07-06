"""
PS3 Sensor Hub — Pydantic Schemas
Shared data models matching the actual ESP32 exoskeleton hardware output.

ESP32 packet format:
{
    "knee_angle": 75.3, "hip_angle": 45.1, "foot_force": 3.42,
    "stance": true, "knee_pwm": 95, "knee_dir": "ext",
    "hip_pwm": 60, "hip_dir": "ext", "motors": "on"
}
"""
import time
from typing import Literal, Optional
from pydantic import BaseModel, Field


# ---------- ESP32 Data Packet (what the hardware sends) ----------

class ExoMotorStatus(BaseModel):
    """Motor state for one joint actuator."""
    pwm: int = 0                   # PWM value (0-255)
    direction: str = "ext"         # "ext" (extension) or "flex" (flexion)


class ExoSensorData(BaseModel):
    """Parsed ESP32 exoskeleton data frame — matches actual hardware output."""
    knee_angle: float = 0.0        # Knee joint angle (degrees, computed on ESP32)
    hip_angle: float = 0.0         # Hip joint angle (degrees, computed on ESP32)
    foot_force: float = 0.0        # Foot pressure sensor (Newtons)
    stance: bool = False           # Whether patient foot is on ground
    knee_motor: ExoMotorStatus = Field(default_factory=ExoMotorStatus)
    hip_motor: ExoMotorStatus = Field(default_factory=ExoMotorStatus)
    motors_active: bool = False    # Overall motor status (on/off)


# ---------- Legacy-compatible SensorReading (used by API + frontend) ----------

class SensorAccelerometer(BaseModel):
    """3-axis accelerometer reading (kept for backward compat)."""
    x: float = 0.0
    y: float = 0.0
    z: float = 9.81


class SensorGyroscope(BaseModel):
    """3-axis gyroscope reading (kept for backward compat)."""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


class SensorReading(BaseModel):
    """
    Full sensor data frame — extends legacy schema with real ESP32 exo data.
    The API and frontend consume this model.
    """
    connected: bool = False
    device_id: Optional[str] = None
    battery_percent: int = 0
    signal_strength: int = 0
    calibration_status: Literal["uncalibrated", "calibrating", "calibrated"] = "uncalibrated"
    connection_status: Literal["disconnected", "connecting", "connected"] = "disconnected"
    # Legacy IMU fields (backward compat — populated from ESP32 angles)
    accelerometer: SensorAccelerometer = Field(default_factory=SensorAccelerometer)
    gyroscope: SensorGyroscope = Field(default_factory=SensorGyroscope)
    temperature_celsius: float = 0.0
    timestamp: float = Field(default_factory=time.time)
    ps3_mode: Literal["simulated", "real"] = "simulated"
    # ---- Real ESP32 exoskeleton data ----
    exo: Optional[ExoSensorData] = None
    esp_url: Optional[str] = None


# ---------- Command sent TO the ESP32 ----------

class SensorCommand(BaseModel):
    """Command structure for sending mode/torque to exoskeleton via ESP32."""
    cmd: str = "set_mode"          # set_mode | calibrate | e_stop | motors_off | motors_on
    mode_id: int = 0               # PS2 mode (1=Assistive, 2=Resistive)
    mode_name: str = "None"
    target_torque: float = 0.0     # Desired torque (Nm) — ESP32 firmware maps to PWM
    knee_pwm: Optional[int] = None    # Direct PWM override (0-255)
    knee_dir: Optional[str] = None    # "ext" or "flex"
    hip_pwm: Optional[int] = None     # Direct PWM override (0-255)
    hip_dir: Optional[str] = None     # "ext" or "flex"
