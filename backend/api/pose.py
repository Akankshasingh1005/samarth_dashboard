"""PS1 Pose Engine API routes."""
from fastapi import APIRouter, Depends, HTTPException
from services.pose_engine import get_pose_engine
from services.auth_service import get_current_user
from models.user import User

router = APIRouter()


@router.get("/status")
async def pose_engine_status(current_user: User = Depends(get_current_user)):
    engine = get_pose_engine()
    return engine.get_status().model_dump()


@router.post("/process")
async def trigger_processing(session_id: str, current_user: User = Depends(get_current_user)):
    """Trigger PS1 batch processing for an already-uploaded video."""
    from models.session import Session
    from models.uploaded_video import UploadedVideo
    from beanie import PydanticObjectId
    from fastapi import BackgroundTasks
    from api.sessions import _process_video_background

    session = await Session.get(PydanticObjectId(session_id))
    if not session or not session.video_path:
        raise HTTPException(status_code=404, detail="Session or video not found")

    video_record = await UploadedVideo.find_one(
        UploadedVideo.session_id == session.id
    )
    if not video_record:
        raise HTTPException(status_code=404, detail="No uploaded video record found")

    # Re-trigger background processing
    import asyncio
    asyncio.create_task(
        _process_video_background(session_id, session.video_path, str(video_record.id))
    )
    return {"message": "PS1 processing triggered", "session_id": session_id}
