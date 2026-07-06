from datetime import datetime, date
from typing import List, Literal, Optional
from beanie import Document, PydanticObjectId
from pydantic import BaseModel, Field
import pymongo


class PrescribedExercise(BaseModel):
    exercise_id: PydanticObjectId
    prescribed_reps: int = 10
    prescribed_sets: int = 3
    frequency_per_week: int = 3
    notes: Optional[str] = None


class ExercisePlan(Document):
    patient_id: PydanticObjectId
    therapist_id: PydanticObjectId
    name: str
    description: Optional[str] = None
    status: Literal["active", "paused", "completed"] = "active"
    start_date: date = Field(default_factory=date.today)
    end_date: Optional[date] = None
    exercises: List[PrescribedExercise] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "exercise_plans"
        indexes = [
            [("patient_id", pymongo.ASCENDING)],
            [("therapist_id", pymongo.ASCENDING)],
            [("status", pymongo.ASCENDING)],
        ]
