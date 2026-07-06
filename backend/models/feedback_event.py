from datetime import datetime
from typing import Any, Dict, Literal, Optional
from beanie import Document, PydanticObjectId
from pydantic import Field
import pymongo


class FeedbackEvent(Document):
    session_id: PydanticObjectId
    timestamp_ms: int = 0
    type: Literal["positioning", "rep_counted", "quality_warning", "completion"] = "positioning"
    message: str
    severity: Literal["info", "warning", "error"] = "info"
    data: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "feedback_events"
        indexes = [
            [("session_id", pymongo.ASCENDING)],
            [("type", pymongo.ASCENDING)],
        ]
