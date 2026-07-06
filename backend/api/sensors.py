"""PS3 Sensor Hub API routes — ESP32 hardware integration."""
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from services.sensor_hub import get_sensor_hub, SensorReading, reset_sensor_hub
from services.auth_service import get_current_user
from models.user import User
from pydantic import BaseModel
import asyncio
import json

router = APIRouter()


class ConnectRequest(BaseModel):
    port: str = ""         # Legacy: serial port
    esp_url: str = ""      # ESP32 URL (preferred)


class CommandRequest(BaseModel):
    cmd: str = "set_mode"
    mode_id: int = 0
    mode_name: str = "None"
    target_torque: float = 0.0


@router.post("/connect")
async def connect_sensor(req: ConnectRequest, current_user: User = Depends(get_current_user)):
    """Connect to ESP32 PS3 hardware. Accepts either esp_url or port."""
    from services.sensor_hub import reset_sensor_hub, RealSensorHub
    from backend_config import settings

    url = req.esp_url or req.port
    if url:
        settings.PS3_USE_REAL_SENSOR = True
        settings.PS3_ESP_URL = url

    reset_sensor_hub()
    hub = get_sensor_hub()

    if isinstance(hub, RealSensorHub):
        return {"success": True, "message": f"Connected to {hub._device_id}", "device_id": hub._device_id}
    
    # If connection failed and we fell back to mock, run a temporary connect to get the error details
    temp_hub = RealSensorHub(esp_url=url)
    return temp_hub.connect(url)


@router.post("/disconnect")
async def disconnect_sensor(current_user: User = Depends(get_current_user)):
    """Disconnect from ESP32 PS3 hardware."""
    hub = get_sensor_hub()
    result = hub.disconnect()
    reset_sensor_hub()
    return result


@router.get("/status", response_model=SensorReading)
async def sensor_status(current_user: User = Depends(get_current_user)):
    hub = get_sensor_hub()
    return hub.get_status()


@router.post("/calibrate")
async def calibrate_sensor(current_user: User = Depends(get_current_user)):
    hub = get_sensor_hub()
    return hub.calibrate()


@router.get("/data", response_model=SensorReading)
async def sensor_data(current_user: User = Depends(get_current_user)):
    """Returns live or simulated sensor IMU data."""
    hub = get_sensor_hub()
    return hub.get_data()


@router.post("/command")
async def send_command(req: CommandRequest, current_user: User = Depends(get_current_user)):
    """Send a mode/torque command to the ESP32 exoskeleton hardware."""
    hub = get_sensor_hub()
    return hub.send_command(req.model_dump())


@router.get("/stream")
async def sensor_stream(current_user: User = Depends(get_current_user)):
    """
    SSE (Server-Sent Events) endpoint for real-time sensor data streaming.
    Streams sensor readings at ~10 Hz for frontend display.
    """
    async def event_generator():
        hub = get_sensor_hub()
        while True:
            reading = hub.poll_once()
            data = reading.model_dump()
            yield f"data: {json.dumps(data)}\n\n"
            await asyncio.sleep(0.1)  # ~10 Hz

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
