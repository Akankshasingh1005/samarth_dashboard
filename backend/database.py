"""
MongoDB connection setup using Motor (async) + Beanie (ODM).
"""
import sys
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

from backend_config import settings


_client: AsyncIOMotorClient | None = None


async def connect_db():
    global _client
    logger.info(f"Connecting to MongoDB: {settings.MONGO_DB_NAME}")
    _client = AsyncIOMotorClient(settings.MONGO_URI)

    # Import all document models for Beanie init
    from models.user import User
    from models.patient import Patient
    from models.therapist import Therapist
    from models.exercise import Exercise
    from models.exercise_plan import ExercisePlan
    from models.session import Session
    from models.pose_data import PoseData
    from models.angle_data import AngleData
    from models.report import Report
    from models.analytics import AnalyticsSnapshot
    from models.notification import Notification
    from models.uploaded_video import UploadedVideo
    from models.feedback_event import FeedbackEvent
    from models.system_log import SystemLog

    await init_beanie(
        database=_client[settings.MONGO_DB_NAME],
        document_models=[
            User, Patient, Therapist, Exercise, ExercisePlan,
            Session, PoseData, AngleData, Report, AnalyticsSnapshot,
            Notification, UploadedVideo, FeedbackEvent, SystemLog,
        ],
    )
    logger.info("✅ MongoDB connected and Beanie initialized")


async def close_db():
    global _client
    if _client:
        _client.close()
        logger.info("MongoDB connection closed")


def get_db():
    """Return the raw Motor database (for aggregation pipelines)."""
    if _client is None:
        raise RuntimeError("Database not connected. Call connect_db() first.")
    return _client[settings.MONGO_DB_NAME]
