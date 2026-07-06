from datetime import datetime, date
from typing import Optional, Dict
from beanie import Document, Link, PydanticObjectId
from pydantic import Field
import pymongo


class TargetROM(dict):
    pass


class Patient(Document):
    user_id: PydanticObjectId
    therapist_id: Optional[PydanticObjectId] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    medical_history: Optional[str] = None
    injury_type: Optional[str] = None
    injury_date: Optional[date] = None
    surgery_date: Optional[date] = None
    current_condition: Optional[str] = None
    target_rom: Dict[str, float] = Field(default_factory=lambda: {
        "left_knee": 120.0, "right_knee": 120.0,
        "left_hip": 100.0, "right_hip": 100.0,
        "left_ankle": 30.0, "right_ankle": 30.0,
    })
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "patients"
        indexes = [
            [("user_id", pymongo.ASCENDING)],
            [("therapist_id", pymongo.ASCENDING)],
        ]
