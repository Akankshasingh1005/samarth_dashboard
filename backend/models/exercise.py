from datetime import datetime
from typing import List, Literal, Optional
from beanie import Document
from pydantic import Field
import pymongo


class Exercise(Document):
    name: str
    slug: str  # unique identifier e.g. "step-up-step-down"
    description: str
    category: Literal["knee", "hip", "ankle", "full_leg"]
    difficulty: Literal["beginner", "intermediate", "advanced"] = "beginner"
    target_joints: List[str] = Field(default_factory=list)
    target_reps: int = 10
    target_sets: int = 3
    target_rom_degrees: float = 90.0
    estimated_duration_seconds: int = 120
    gif_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    demo_video_url: Optional[str] = None
    audio_guide_url: Optional[str] = None
    safety_instructions: List[str] = Field(default_factory=list)
    contraindications: List[str] = Field(default_factory=list)
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "exercises"
        indexes = [
            [("slug", pymongo.ASCENDING)],
            [("category", pymongo.ASCENDING)],
            [("is_active", pymongo.ASCENDING)],
        ]
