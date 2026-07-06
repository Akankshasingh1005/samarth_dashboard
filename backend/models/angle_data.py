from datetime import datetime
from typing import Dict, List, Optional, Any
from beanie import Document, PydanticObjectId
from pydantic import BaseModel, Field
import pymongo


class RepetitionData(BaseModel):
    rep_id: int
    start_frame: int
    peak_frame: int
    end_frame: int
    start_time: float
    peak_time: float
    end_time: float
    duration: float
    rom: float


class JointSymmetry(BaseModel):
    trajectory_correlation: float = 0.0
    left_overall_rom: float = 0.0
    right_overall_rom: float = 0.0
    rom_symmetry_index: float = 0.0
    average_angle_difference: float = 0.0
    symmetry_score_percentage: float = 0.0


class TimeSeries(BaseModel):
    frames: List[int] = Field(default_factory=list)
    time_seconds: List[float] = Field(default_factory=list)
    left_knee: List[float] = Field(default_factory=list)
    right_knee: List[float] = Field(default_factory=list)
    left_hip: List[float] = Field(default_factory=list)
    right_hip: List[float] = Field(default_factory=list)
    left_ankle: List[float] = Field(default_factory=list)
    right_ankle: List[float] = Field(default_factory=list)
    left_knee_velocity: List[float] = Field(default_factory=list)
    right_knee_velocity: List[float] = Field(default_factory=list)
    left_knee_acceleration: List[float] = Field(default_factory=list)
    right_knee_acceleration: List[float] = Field(default_factory=list)


class AngleData(Document):
    session_id: PydanticObjectId
    video_name: Optional[str] = None
    fps: float = 30.0
    time_series: TimeSeries = Field(default_factory=TimeSeries)
    repetitions: List[RepetitionData] = Field(default_factory=list)
    symmetry: Dict[str, JointSymmetry] = Field(default_factory=dict)
    # PS2 per-rep analysis results from the real RehabNet model
    ps2_rep_results: List[Dict[str, Any]] = Field(default_factory=list)
    ps2_mode: str = "real"
    # PS3 exoskeleton time series (populated when ESP32 hardware is connected)
    ps3_knee_angle: List[float] = Field(default_factory=list)     # Knee angle from ESP32 IMU
    ps3_hip_angle: List[float] = Field(default_factory=list)      # Hip angle from ESP32 IMU
    ps3_foot_force: List[float] = Field(default_factory=list)     # Foot pressure sensor (N)
    ps3_stance: List[bool] = Field(default_factory=list)          # Stance phase per frame
    ps3_mode_commands: List[Dict[str, Any]] = Field(default_factory=list)  # [{rep_id, mode_id, mode_name, torque, timestamp}]
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "angle_data"
        indexes = [
            [("session_id", pymongo.ASCENDING)],
        ]
