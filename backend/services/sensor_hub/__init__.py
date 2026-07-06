"""PS3 Sensor Hub — Factory that auto-switches between Mock and Real (ESP32)."""
from .schemas import (
    SensorReading, SensorAccelerometer, SensorGyroscope,
    ExoSensorData, ExoMotorStatus, SensorCommand,
)
from .mock_sensor import MockSensorHub
from .real_sensor import RealSensorHub

_sensor_hub = None


def get_sensor_hub() -> MockSensorHub | RealSensorHub:
    """
    Return the active sensor hub instance.
    Uses RealSensorHub (ESP32) when PS3_USE_REAL_SENSOR=true and PS3_ESP_URL is set.
    Falls back to MockSensorHub otherwise.
    """
    global _sensor_hub
    if _sensor_hub is None:
        try:
            from backend_config import settings
            if settings.PS3_USE_REAL_SENSOR and getattr(settings, "PS3_ESP_URL", ""):
                _sensor_hub = RealSensorHub(
                    esp_url=settings.PS3_ESP_URL,
                    poll_interval_ms=getattr(settings, "PS3_POLL_INTERVAL_MS", 100),
                )
                _sensor_hub.connect()
            else:
                _sensor_hub = MockSensorHub()
        except Exception:
            _sensor_hub = MockSensorHub()
    return _sensor_hub


def reset_sensor_hub():
    """Reset the singleton (useful for reconnection or testing)."""
    global _sensor_hub
    if _sensor_hub is not None and hasattr(_sensor_hub, "disconnect"):
        _sensor_hub.disconnect()
    _sensor_hub = None


__all__ = [
    "MockSensorHub", "RealSensorHub",
    "SensorReading", "SensorAccelerometer", "SensorGyroscope",
    "ExoSensorData", "ExoMotorStatus", "SensorCommand",
    "get_sensor_hub", "reset_sensor_hub",
]
