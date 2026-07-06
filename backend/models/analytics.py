from datetime import datetime
from typing import List, Literal, Optional
from beanie import Document, PydanticObjectId
from pydantic import BaseModel, Field
import pymongo


class TrendPoint(BaseModel):
    date: datetime
    value: float


class SessionFrequencyPoint(BaseModel):
    date: datetime
    count: int


class AnalyticsSnapshot(Document):
    patient_id: PydanticObjectId
    period: Literal["weekly", "monthly"]
    period_start: datetime
    period_end: datetime
    total_sessions: int = 0
    completed_sessions: int = 0
    total_reps: int = 0
    avg_symmetry_score: float = 0.0
    avg_rom_left: float = 0.0
    avg_rom_right: float = 0.0
    avg_session_score: Optional[float] = None
    rom_trend: List[TrendPoint] = Field(default_factory=list)
    symmetry_trend: List[TrendPoint] = Field(default_factory=list)
    session_frequency: List[SessionFrequencyPoint] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "analytics"
        indexes = [
            [("patient_id", pymongo.ASCENDING)],
            [("period_start", pymongo.DESCENDING)],
            [("patient_id", pymongo.ASCENDING), ("period", pymongo.ASCENDING), ("period_start", pymongo.DESCENDING)],
        ]
