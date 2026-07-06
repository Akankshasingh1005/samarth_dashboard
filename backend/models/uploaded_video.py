from datetime import datetime
from typing import Literal, Optional
from beanie import Document, PydanticObjectId
from pydantic import Field
import pymongo


class UploadedVideo(Document):
    session_id: PydanticObjectId
    patient_id: PydanticObjectId
    original_filename: str
    stored_path: str
    cloudinary_url: Optional[str] = None
    file_size_bytes: Optional[int] = None
    duration_seconds: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[float] = None
    processing_status: Literal["pending", "processing", "completed", "failed"] = "pending"
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "uploaded_videos"
        indexes = [
            [("session_id", pymongo.ASCENDING)],
            [("patient_id", pymongo.ASCENDING)],
            [("processing_status", pymongo.ASCENDING)],
        ]
