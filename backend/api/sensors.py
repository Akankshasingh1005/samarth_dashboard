"""PS3 Sensor Hub API routes."""
from fastapi import APIRouter, Depends
from services.sensor_hub import get_sensor_hub, SensorReading
from services.auth_service import get_current_user
from models.user import User
from pydantic import BaseModel

router = APIRouter()


class ConnectRequest(BaseModel):
    port: str = ""


@router.post("/connect")
async def connect_sensor(req: ConnectRequest, current_user: User = Depends(get_current_user)):
    hub = get_sensor_hub()
    return hub.connect(req.port)


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
