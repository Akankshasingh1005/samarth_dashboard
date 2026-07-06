from datetime import datetime
from typing import Dict, Optional
from beanie import Document, PydanticObjectId
from pydantic import BaseModel, Field
import pymongo


class LandmarkData(BaseModel):
    x_norm: float
    y_norm: float
    z_norm: float
    visibility: float


class ValidationStatus(BaseModel):
    left_hip_visible: bool = False
    right_hip_visible: bool = False
    left_knee_visible: bool = False
    right_knee_visible: bool = False
    left_ankle_visible: bool = False
    right_ankle_visible: bool = False
    full_lower_body_visible: bool = False
    inside_zone: bool = False
    adequate_lighting: bool = False
    camera_stable: bool = False

    @property
    def all_valid(self) -> bool:
        return all([
            self.left_hip_visible, self.right_hip_visible,
            self.left_knee_visible, self.right_knee_visible,
            self.left_ankle_visible, self.right_ankle_visible,
            self.full_lower_body_visible, self.inside_zone,
            self.adequate_lighting, self.camera_stable,
        ])


class PoseData(Document):
    session_id: PydanticObjectId
    frame_index: int
    timestamp_ms: int
    landmarks: Dict[str, LandmarkData] = Field(default_factory=dict)
    validation_status: ValidationStatus = Field(default_factory=ValidationStatus)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "pose_data"
        indexes = [
            [("session_id", pymongo.ASCENDING)],
            [("session_id", pymongo.ASCENDING), ("frame_index", pymongo.ASCENDING)],
        ]
