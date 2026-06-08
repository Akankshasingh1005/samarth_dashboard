from datetime import datetime
from typing import Literal, Optional
from beanie import Document, PydanticObjectId
from pydantic import Field
import pymongo


class Notification(Document):
    user_id: PydanticObjectId
    type: Literal["session_reminder", "report_ready", "therapist_message", "system"] = "system"
    title: str
    message: str
    is_read: bool = False
    action_url: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "notifications"
        indexes = [
            [("user_id", pymongo.ASCENDING)],
            [("is_read", pymongo.ASCENDING)],
            [("created_at", pymongo.DESCENDING)],
        ]
