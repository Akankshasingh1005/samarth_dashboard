from datetime import datetime
from typing import Literal, Optional
from beanie import Document, PydanticObjectId
from pydantic import Field
import pymongo


class Session(Document):
    patient_id: PydanticObjectId
    therapist_id: Optional[PydanticObjectId] = None
    exercise_id: PydanticObjectId
    plan_id: Optional[PydanticObjectId] = None
    status: Literal["in_progress", "completed", "abandoned"] = "in_progress"
    mode: Literal["live", "uploaded"] = "live"
    start_time: datetime = Field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    video_path: Optional[str] = None
    video_url: Optional[str] = None
    ps1_processed: bool = False
    ps2_processed: bool = False
    # PS1 results
    total_reps: int = 0
    completed_reps: int = 0
    avg_left_rom: float = 0.0
    avg_right_rom: float = 0.0
    symmetry_score: float = 0.0
    # PS2 results (populated when PS2 is integrated)
    quality_score: Optional[float] = None
    quality_trend: Optional[str] = None  # improving | stable | declining
    session_score: Optional[float] = None
    # Processing progress tracking
    processing_step: Optional[str] = None  # e.g. "enhancing", "pose_detection", "kinematics", "analysis"
    processing_progress: int = 0  # 0-100 percentage
    # PS3 sensor integration (future hardware module)
    ps3_connected: bool = False
    ps3_sensor_data_path: Optional[str] = None
    # Metadata
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "sessions"
        indexes = [
            [("patient_id", pymongo.ASCENDING)],
            [("exercise_id", pymongo.ASCENDING)],
            [("start_time", pymongo.DESCENDING)],
            [("status", pymongo.ASCENDING)],
        ]
