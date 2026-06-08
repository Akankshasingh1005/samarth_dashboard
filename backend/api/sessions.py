"""Sessions API — create, manage, process, retrieve session data."""
import os
import asyncio
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from pydantic import BaseModel
from beanie import PydanticObjectId

from models.session import Session
from models.angle_data import AngleData, TimeSeries, RepetitionData, JointSymmetry
from models.uploaded_video import UploadedVideo
from models.feedback_event import FeedbackEvent
from models.exercise import Exercise
from services.auth_service import get_current_user, get_current_patient
from services.pose_engine import get_pose_engine
from services.exercise_analysis import get_analyzer
from models.user import User
from config import settings

router = APIRouter()


class CreateSessionRequest(BaseModel):
    exercise_id: str
    plan_id: Optional[str] = None
    mode: str = "live"


class SessionOut(BaseModel):
    id: str
    patient_id: str
    exercise_id: str
    status: str
    mode: str
    start_time: datetime
    end_time: Optional[datetime]
    duration_seconds: Optional[float]
    total_reps: int
    avg_left_rom: float
    avg_right_rom: float
    symmetry_score: float
    ps1_processed: bool
    ps2_processed: bool
    quality_score: Optional[float]
    quality_trend: Optional[str]
    session_score: Optional[float]
    video_url: Optional[str]


def _to_out(s: Session) -> SessionOut:
    return SessionOut(
        id=str(s.id),
        patient_id=str(s.patient_id),
        exercise_id=str(s.exercise_id),
        status=s.status,
        mode=s.mode,
        start_time=s.start_time,
        end_time=s.end_time,
        duration_seconds=s.duration_seconds,
        total_reps=s.total_reps,
        avg_left_rom=s.avg_left_rom,
        avg_right_rom=s.avg_right_rom,
        symmetry_score=s.symmetry_score,
        ps1_processed=s.ps1_processed,
        ps2_processed=s.ps2_processed,
        quality_score=s.quality_score,
        quality_trend=s.quality_trend,
        session_score=s.session_score,
        video_url=s.video_url,
    )


@router.post("/", response_model=SessionOut, status_code=201)
async def create_session(req: CreateSessionRequest, current_user: User = Depends(get_current_user)):
    from models.patient import Patient
    patient = await Patient.find_one(Patient.user_id == current_user.id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient profile not found")

    session = Session(
        patient_id=patient.id,
        exercise_id=PydanticObjectId(req.exercise_id),
        plan_id=PydanticObjectId(req.plan_id) if req.plan_id else None,
        mode=req.mode,
        status="in_progress",
    )
    await session.insert()
    return _to_out(session)


@router.get("/", response_model=List[SessionOut])
async def list_sessions(current_user: User = Depends(get_current_user), limit: int = 20, skip: int = 0):
    from models.patient import Patient
    patient = await Patient.find_one(Patient.user_id == current_user.id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient profile not found")
    sessions = await Session.find(
        Session.patient_id == patient.id
    ).sort(-Session.start_time).skip(skip).limit(limit).to_list()
    return [_to_out(s) for s in sessions]


@router.get("/{session_id}", response_model=SessionOut)
async def get_session(session_id: str, current_user: User = Depends(get_current_user)):
    session = await Session.get(PydanticObjectId(session_id))
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return _to_out(session)


@router.put("/{session_id}/complete")
async def complete_session(session_id: str, notes: Optional[str] = None, current_user: User = Depends(get_current_user)):
    session = await Session.get(PydanticObjectId(session_id))
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.status = "completed"
    session.end_time = datetime.utcnow()
    if session.start_time:
        session.duration_seconds = (session.end_time - session.start_time).total_seconds()
    if notes:
        session.notes = notes
    session.updated_at = datetime.utcnow()
    await session.save()
    return _to_out(session)


@router.post("/{session_id}/upload-video")
async def upload_session_video(
    session_id: str,
    background_tasks: BackgroundTasks,
    video: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    session = await Session.get(PydanticObjectId(session_id))
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Save video locally
    upload_dir = os.path.join(settings.LOCAL_UPLOAD_DIR, session_id)
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, video.filename)

    with open(file_path, "wb") as f:
        content = await video.read()
        f.write(content)

    # Create video record
    video_record = UploadedVideo(
        session_id=session.id,
        patient_id=session.patient_id,
        original_filename=video.filename,
        stored_path=file_path,
        file_size_bytes=len(content),
        processing_status="pending",
    )
    await video_record.insert()

    session.video_path = file_path
    session.updated_at = datetime.utcnow()
    await session.save()

    # Trigger PS1 processing in background
    background_tasks.add_task(_process_video_background, str(session.id), file_path, str(video_record.id))

    return {"message": "Video uploaded. PS1 processing started.", "video_id": str(video_record.id)}


async def _process_video_background(session_id: str, video_path: str, video_record_id: str):
    """Background task: run PS1 batch processing, then PS2 analysis."""
    try:
        video_record = await UploadedVideo.get(PydanticObjectId(video_record_id))
        if video_record:
            video_record.processing_status = "processing"
            await video_record.save()

        output_dir = os.path.join(settings.LOCAL_UPLOAD_DIR, session_id, "output")
        engine = get_pose_engine()
        result = engine.process_video(video_path, session_id, output_dir)

        session = await Session.get(PydanticObjectId(session_id))
        if not session:
            return

        if result.status == "success":
            # Store angle data
            time_series = TimeSeries(
                frames=list(range(result.total_frames)),
                time_seconds=[i / result.fps for i in range(result.total_frames)],
                left_knee=result.time_series.get("left_knee", []),
                right_knee=result.time_series.get("right_knee", []),
                left_hip=result.time_series.get("left_hip", []),
                right_hip=result.time_series.get("right_hip", []),
                left_ankle=result.time_series.get("left_ankle", []),
                right_ankle=result.time_series.get("right_ankle", []),
                left_knee_velocity=result.time_series.get("left_knee_velocity", []),
                right_knee_velocity=result.time_series.get("right_knee_velocity", []),
            )

            reps_data = [RepetitionData(**r.model_dump()) for r in result.repetitions]
            sym_data = {k: JointSymmetry(**v.model_dump()) for k, v in result.symmetry.items()}

            angle_data_doc = AngleData(
                session_id=PydanticObjectId(session_id),
                video_name=result.video_name,
                fps=result.fps,
                time_series=time_series,
                repetitions=reps_data,
                symmetry=sym_data,
            )

            # Run PS2 analysis on PS1 results
            analyzer = get_analyzer()
            ps2_result = analyzer.analyze_session(
                session_id=session_id,
                angle_data=result.time_series,
                repetitions=[r.model_dump() for r in result.repetitions],
                fps=result.fps,
            )
            angle_data_doc.ps2_rep_results = [r.model_dump() for r in ps2_result.rep_results]
            await angle_data_doc.insert()

            # Update session with results
            session.total_reps = result.total_reps
            session.avg_left_rom = result.avg_left_rom
            session.avg_right_rom = result.avg_right_rom
            sym_score = 0.0
            if result.symmetry.get("left_knee"):
                sym_score = result.symmetry["left_knee"].symmetry_score_percentage
            session.symmetry_score = sym_score
            session.ps1_processed = True
            session.ps2_processed = True
            session.session_score = ps2_result.overall_session_score
            session.quality_trend = ps2_result.quality_trend
            session.updated_at = datetime.utcnow()
            await session.save()

            if video_record:
                video_record.processing_status = "completed"
                await video_record.save()
        else:
            if video_record:
                video_record.processing_status = "failed"
                video_record.error_message = result.error
                await video_record.save()

    except Exception as e:
        import traceback
        from loguru import logger
        logger.error(f"Background processing failed: {e}\n{traceback.format_exc()}")


@router.get("/{session_id}/angle-data")
async def get_angle_data(session_id: str, current_user: User = Depends(get_current_user)):
    angle_data = await AngleData.find_one(AngleData.session_id == PydanticObjectId(session_id))
    if not angle_data:
        raise HTTPException(status_code=404, detail="Angle data not yet available. PS1 may still be processing.")
    return angle_data.model_dump()


@router.get("/{session_id}/ps2-results")
async def get_ps2_results(session_id: str, current_user: User = Depends(get_current_user)):
    angle_data = await AngleData.find_one(AngleData.session_id == PydanticObjectId(session_id))
    if not angle_data:
        raise HTTPException(status_code=404, detail="Session data not available.")
    return {
        "session_id": session_id,
        "ps2_rep_results": angle_data.ps2_rep_results,
        "total_analyzed": len(angle_data.ps2_rep_results),
    }
