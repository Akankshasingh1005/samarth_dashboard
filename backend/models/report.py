from datetime import datetime
from typing import List, Literal, Optional
from beanie import Document, PydanticObjectId
from pydantic import BaseModel, Field
import pymongo


class DateRange(BaseModel):
    from_date: datetime
    to_date: datetime


class Report(Document):
    patient_id: PydanticObjectId
    therapist_id: Optional[PydanticObjectId] = None
    session_ids: List[PydanticObjectId] = Field(default_factory=list)
    type: Literal["session", "weekly", "monthly", "progress"] = "session"
    date_range: Optional[DateRange] = None
    pdf_url: Optional[str] = None
    csv_url: Optional[str] = None
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "reports"
        indexes = [
            [("patient_id", pymongo.ASCENDING)],
            [("generated_at", pymongo.DESCENDING)],
        ]
