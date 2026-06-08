from datetime import datetime
from typing import List, Optional
from beanie import Document, PydanticObjectId
from pydantic import Field
import pymongo


class Therapist(Document):
    user_id: PydanticObjectId
    license_number: Optional[str] = None
    specialization: Optional[str] = None
    clinic_name: Optional[str] = None
    phone: Optional[str] = None
    bio: Optional[str] = None
    patient_ids: List[PydanticObjectId] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "therapists"
        indexes = [
            [("user_id", pymongo.ASCENDING)],
        ]
