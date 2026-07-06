from datetime import datetime
from typing import Literal, Optional
from beanie import Document, Indexed
from pydantic import EmailStr, Field
import pymongo


class User(Document):
    email: Indexed(EmailStr, unique=True)
    password_hash: str
    role: Literal["patient", "therapist", "admin"]
    first_name: str
    last_name: str
    is_active: bool = True
    avatar_url: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_login: Optional[datetime] = None

    class Settings:
        name = "users"
        indexes = [
            [("email", pymongo.ASCENDING)],
            [("role", pymongo.ASCENDING)],
        ]

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
