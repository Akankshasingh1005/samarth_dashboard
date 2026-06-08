from datetime import datetime
from typing import Literal, Optional
from beanie import Document, PydanticObjectId
from pydantic import Field
import pymongo


class SystemLog(Document):
    level: Literal["info", "warning", "error", "critical"] = "info"
    service: Literal["pose_engine", "auth", "session", "analysis", "sensor", "system"]
    message: str
    user_id: Optional[PydanticObjectId] = None
    session_id: Optional[PydanticObjectId] = None
    traceback: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "system_logs"
        indexes = [
            # TTL index: auto-delete logs older than 30 days
            [("created_at", pymongo.ASCENDING)],
            [("level", pymongo.ASCENDING)],
            [("service", pymongo.ASCENDING)],
        ]
