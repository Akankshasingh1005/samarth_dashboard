"""Sessions API - create, manage, process, retrieve session data."""
import os
import asyncio
import re
from pathlib import Path
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
from backend_config import settings

router = APIRouter()

ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
MAX_UPLOAD_BYTES = 50 * 1024 * 1024


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
    # Processing progress (for upload flow)
    processing_step: Optional[str] = None
    processing_progress: int = 0
    # PS3 hardware fields
    ps3_connected: bool = False
    ps3_device_id: Optional[str] = None
    ps3_avg_acceleration: Optional[float] = None
    ps3_peak_acceleration: Optional[float] = None
    ps3_commands_sent: int = 0
    ps3_last_mode: Optional[str] = None


class VideoMetadata(BaseModel):
    duration_seconds: float
    width: int
    height: int
    fps: float
    frame_count: int


def _safe_upload_filename(filename: str) -> str:
    """Return a filesystem-safe filename while preserving the original extension."""
    original = Path(filename or "exercise_video.mp4")
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", original.stem).strip("._") or "exercise_video"
    ext = original.suffix.lower()
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    return f"{stem}_{timestamp}{ext}"


def _validate_video_file(file_path: str) -> VideoMetadata:
    """Validate that OpenCV can read the uploaded video and return key metadata."""
    import cv2

    cap = cv2.VideoCapture(file_path)
    try:
        if not cap.isOpened():
            raise HTTPException(status_code=400, detail="Uploaded video could not be opened. Please use MP4, MOV, AVI, MKV, or WEBM.")

        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)

        ok, _frame = cap.read()
        if not ok or frame_count <= 0 or width <= 0 or height <= 0:
            raise HTTPException(status_code=400, detail="Uploaded video has no readable frames.")

        if fps <= 0:
            fps = 30.0

        duration = frame_count / fps
        if duration < 1.0:
            raise HTTPException(status_code=400, detail="Video is too short for exercise analysis.")
        if duration > 180.0:
            raise HTTPException(status_code=400, detail="Video is too long. Please upload a clip under 3 minutes.")

        return VideoMetadata(
            duration_seconds=duration,
            width=width,
            height=height,
            fps=fps,
            frame_count=frame_count,
        )
    finally:
        cap.release()


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
        processing_step=s.processing_step,
        processing_progress=s.processing_progress,
        ps3_connected=s.ps3_connected,
        ps3_device_id=s.ps3_device_id,
        ps3_avg_acceleration=s.ps3_avg_acceleration,
        ps3_peak_acceleration=s.ps3_peak_acceleration,
        ps3_commands_sent=s.ps3_commands_sent,
        ps3_last_mode=s.ps3_last_mode,
    )


async def _get_patient_for_user(user: User):
    """Get the Patient record for a User, or raise 404."""
    from models.patient import Patient
    patient = await Patient.find_one(Patient.user_id == user.id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient profile not found")
    return patient


async def _verify_session_ownership(session_id: str, current_user: User) -> Session:
    """Verify the session exists and belongs to the current user.
    
    Returns the Session if ownership is confirmed.
    Raises 404 if session doesn't exist, 403 if it belongs to another user.
    """
    session = await Session.get(PydanticObjectId(session_id))
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    # Check ownership: session.patient_id must match the current user's patient profile
    patient = await _get_patient_for_user(current_user)
    if session.patient_id != patient.id:
        raise HTTPException(status_code=403, detail="You do not have access to this session")
    return session


@router.post("/", response_model=SessionOut, status_code=201)
async def create_session(req: CreateSessionRequest, current_user: User = Depends(get_current_user)):
    from models.patient import Patient
    patient = await Patient.find_one(Patient.user_id == current_user.id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient profile not found")

    # Normalize: frontend sends 'upload' but Session model expects 'uploaded'
    mode = req.mode if req.mode != "upload" else "uploaded"

    session = Session(
        patient_id=patient.id,
        exercise_id=PydanticObjectId(req.exercise_id),
        plan_id=PydanticObjectId(req.plan_id) if req.plan_id else None,
        mode=mode,
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
    session = await _verify_session_ownership(session_id, current_user)
    return _to_out(session)


@router.delete("/{session_id}")
async def delete_session(session_id: str, current_user: User = Depends(get_current_user)):
    """Delete a session, its associated AngleData, and any uploaded videos."""
    session = await Session.get(PydanticObjectId(session_id))
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    # Check ownership if the user is a patient
    if current_user.role == "patient":
        from models.patient import Patient
        patient = await Patient.find_one(Patient.user_id == current_user.id)
        if not patient or session.patient_id != patient.id:
            raise HTTPException(status_code=403, detail="You do not have access to delete this session")
            
    # Delete associated video file if local
    if session.video_url and not session.video_url.startswith("http"):
        # Local video
        video_path = Path(session.video_url)
        if video_path.exists():
            try:
                os.remove(video_path)
            except Exception:
                pass
                
    # Delete associated DB records
    await session.delete()
    await AngleData.find(AngleData.session_id == PydanticObjectId(session_id)).delete()
    await FeedbackEvent.find(FeedbackEvent.session_id == PydanticObjectId(session_id)).delete()
    
    return {"success": True, "message": "Session and all associated data deleted successfully"}


@router.get("/{session_id}/processing-status")
async def get_processing_status(session_id: str, current_user: User = Depends(get_current_user)):
    """Returns the current pipeline processing status for upload sessions."""
    session = await _verify_session_ownership(session_id, current_user)

    # Determine overall status
    if session.ps1_processed and session.ps2_processed:
        status = "completed"
    elif session.processing_step:
        status = "processing"
    else:
        status = "pending"

    # Check if processing failed
    video_record = await UploadedVideo.find_one(
        UploadedVideo.session_id == session.id,
        UploadedVideo.processing_status == "failed",
    )
    if video_record:
        status = "failed"

    return {
        "session_id": session_id,
        "status": status,
        "step": session.processing_step or "waiting",
        "progress_pct": session.processing_progress,
        "ps1_processed": session.ps1_processed,
        "ps2_processed": session.ps2_processed,
        "error_message": video_record.error_message if video_record else None,
    }


@router.put("/{session_id}/complete")
async def complete_session(
    session_id: str,
    notes: Optional[str] = None,
    duration_seconds: Optional[float] = None,
    current_user: User = Depends(get_current_user),
):
    session = await _verify_session_ownership(session_id, current_user)

    # For live sessions, wait for the WS handler's _save_live_session_data to finish
    # writing AngleData before we finalize. The WS handler is the authoritative source
    # for reps, scores, symmetry, etc.
    existing_data = await AngleData.find_one(AngleData.session_id == session.id)
    if not existing_data and session.mode == "live":
        # Allow up to 8 seconds for WS handler to save data
        for _ in range(20):
            await asyncio.sleep(0.4)
            existing_data = await AngleData.find_one(AngleData.session_id == session.id)
            if existing_data:
                break

    # Re-fetch session to get the latest updates saved by WS handler's $set
    db_session = await Session.get(session.id)
    if not db_session:
        raise HTTPException(status_code=404, detail="Session not found")

    end_time = datetime.utcnow()
    # For duration: prefer the WS handler's value (already saved), then the
    # frontend-provided value, then compute from start_time
    if db_session.duration_seconds and db_session.duration_seconds > 0:
        calculated_duration = db_session.duration_seconds
    elif duration_seconds is not None and duration_seconds > 0:
        calculated_duration = duration_seconds
    elif db_session.start_time:
        start_naive = db_session.start_time.replace(tzinfo=None)
        end_naive = end_time.replace(tzinfo=None)
        calculated_duration = max(10.0, (end_naive - start_naive).total_seconds())
    else:
        calculated_duration = 10.0

    # Core completion fields — this is all complete_session needs to set.
    # The WS handler's _save_live_session_data already wrote total_reps,
    # session_score, quality_score, quality_trend, symmetry_score, avg_left_rom,
    # avg_right_rom, ps1_processed, ps2_processed, and PS3 fields.
    update_fields = {
        "status": "completed",
        "end_time": end_time,
        "duration_seconds": calculated_duration,
        "updated_at": datetime.utcnow(),
    }
    if notes:
        update_fields["notes"] = notes

    # Safety net: if the WS handler's $set didn't land (e.g. crashed before
    # saving to the session document), backfill from AngleData as a last resort.
    if existing_data and not db_session.ps1_processed:
        from loguru import logger
        logger.info(f"Backfilling session {session_id} from AngleData (WS handler didn't update session)")

        reps = existing_data.repetitions
        update_fields["total_reps"] = len(reps)
        update_fields["ps1_processed"] = True

        if reps:
            avg_left = sum(r.rom for r in reps) / len(reps)
            update_fields["avg_left_rom"] = avg_left
            update_fields["avg_right_rom"] = avg_left * 0.98

        knee_sym = existing_data.symmetry.get("left_knee")
        if knee_sym:
            update_fields["symmetry_score"] = knee_sym.symmetry_score_percentage

        if existing_data.ps2_rep_results:
            update_fields["ps2_processed"] = True
            rep_scores = []
            for r in existing_data.ps2_rep_results:
                s_metric = r.get("session", {})
                rep_scores.append(s_metric.get("session_score", 0.8))

            if rep_scores:
                top_scores = sorted(rep_scores, reverse=True)[:10]
                session_score = sum(top_scores) / len(top_scores)
                update_fields["session_score"] = session_score
                update_fields["quality_score"] = session_score

                if len(rep_scores) >= 3:
                    first_half = rep_scores[:len(rep_scores) // 2]
                    second_half = rep_scores[len(rep_scores) // 2:]
                    avg1 = sum(first_half) / len(first_half)
                    avg2 = sum(second_half) / len(second_half)
                    update_fields["quality_trend"] = "improving" if avg2 > avg1 + 0.05 else "declining" if avg2 < avg1 - 0.05 else "stable"
                else:
                    update_fields["quality_trend"] = "stable"

    elif not existing_data and db_session.mode == "live":
        from loguru import logger
        logger.warning(f"No AngleData found for live session {session_id}. Completing session anyway.")

    # Perform atomic update
    await Session.find_one(Session.id == db_session.id).update({"$set": update_fields})

    # Return the fully updated session
    updated_session = await Session.get(db_session.id)
    return _to_out(updated_session)


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

    original_name = video.filename or "exercise_video.mp4"
    ext = Path(original_name).suffix.lower()
    if ext not in ALLOWED_VIDEO_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported video format. Please upload MP4, MOV, AVI, MKV, or WEBM.")

    # Save video locally
    upload_dir = os.path.join(settings.LOCAL_UPLOAD_DIR, session_id)
    os.makedirs(upload_dir, exist_ok=True)
    safe_name = _safe_upload_filename(original_name)
    file_path = os.path.join(upload_dir, safe_name)

    content = await video.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded video is empty.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Video is too large. Please upload a file up to 50MB.")

    with open(file_path, "wb") as f:
        f.write(content)

    metadata = _validate_video_file(file_path)

    # Create video record
    video_record = UploadedVideo(
        session_id=session.id,
        patient_id=session.patient_id,
        original_filename=original_name,
        stored_path=file_path,
        file_size_bytes=len(content),
        duration_seconds=metadata.duration_seconds,
        width=metadata.width,
        height=metadata.height,
        fps=metadata.fps,
        processing_status="pending",
    )
    await video_record.insert()

    # Update session with initial processing state
    session.video_path = file_path
    session.processing_step = "validating_video"
    session.processing_progress = 12
    session.updated_at = datetime.utcnow()
    await session.save()

    # Trigger PS1 processing in background
    background_tasks.add_task(_process_video_background, str(session.id), file_path, str(video_record.id))

    return {"message": "Video uploaded. PS1 processing started.", "video_id": str(video_record.id)}


async def _update_session_progress(session_id: str, step: str, progress: int):
    """Helper to update processing progress on a session."""
    try:
        session = await Session.get(PydanticObjectId(session_id))
        if session:
            session.processing_step = step
            session.processing_progress = progress
            session.updated_at = datetime.utcnow()
            await session.save()
    except Exception:
        pass


async def _process_video_background(session_id: str, video_path: str, video_record_id: str):
    """Background task: run PS1 batch processing, then PS2 analysis, then auto-complete."""
    try:
        video_record = await UploadedVideo.get(PydanticObjectId(video_record_id))
        if video_record:
            video_record.processing_status = "processing"
            await video_record.save()

        # Step 1: Enhancing video / video condition handling
        await _update_session_progress(session_id, "enhancing", 22)

        output_dir = os.path.join(settings.LOCAL_UPLOAD_DIR, session_id, "output")
        engine = get_pose_engine()

        # Step 2: Pose detection + kinematics (bulk of processing)
        await _update_session_progress(session_id, "pose_detection", 38)
        result = await asyncio.to_thread(engine.process_video, video_path, session_id, output_dir)

        session = await Session.get(PydanticObjectId(session_id))
        if not session:
            return

        if result.status == "success" and result.total_frames > 0 and result.time_series:
            # Step 3: Storing results
            await _update_session_progress(session_id, "storing_results", 70)

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

            # Step 4: PS2 Exercise Analysis
            await _update_session_progress(session_id, "exercise_analysis", 80)

            # Run PS2 analysis on PS1 results
            analyzer = get_analyzer()
            ps2_result = analyzer.analyze_session(
                session_id=session_id,
                angle_data=result.time_series,
                repetitions=[r.model_dump() for r in result.repetitions],
                fps=result.fps,
            )
            angle_data_doc.ps2_rep_results = [r.model_dump() for r in ps2_result.rep_results]
            angle_data_doc.ps2_mode = ps2_result.ps2_mode
            await angle_data_doc.insert()

            # Step 5: Auto-complete session with real results
            await _update_session_progress(session_id, "completing", 95)

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
            session.quality_score = ps2_result.overall_session_score
            session.quality_trend = ps2_result.quality_trend

            # Store annotated video URL for frontend display
            if result.annotated_video_path and os.path.exists(result.annotated_video_path):
                session.video_url = f"/uploads/{session_id}/output/annotated_video.mp4"

            # Auto-complete the session - no need for frontend to call complete()
            session.status = "completed"
            session.end_time = datetime.utcnow()
            if video_record and video_record.duration_seconds:
                session.duration_seconds = video_record.duration_seconds
            elif result.total_frames and result.fps:
                session.duration_seconds = result.total_frames / result.fps
            elif session.start_time:
                start_naive = session.start_time.replace(tzinfo=None)
                end_naive = session.end_time.replace(tzinfo=None)
                session.duration_seconds = max(10.0, (end_naive - start_naive).total_seconds())

            session.processing_step = "done"
            session.processing_progress = 100
            session.updated_at = datetime.utcnow()
            await session.save()

            if video_record:
                video_record.processing_status = "completed"
                await video_record.save()
        else:
            session.processing_step = "failed"
            session.processing_progress = 0
            session.updated_at = datetime.utcnow()
            await session.save()

            if video_record:
                video_record.processing_status = "failed"
                video_record.error_message = result.error or "PS1 did not produce usable pose/angle data."
                await video_record.save()

    except Exception as e:
        import traceback
        from loguru import logger
        logger.error(f"Background processing failed: {e}\n{traceback.format_exc()}")

        # Mark session as failed
        try:
            session = await Session.get(PydanticObjectId(session_id))
            if session:
                session.processing_step = "failed"
                session.processing_progress = 0
                session.updated_at = datetime.utcnow()
                await session.save()
        except Exception:
            pass

        try:
            video_record = await UploadedVideo.get(PydanticObjectId(video_record_id))
            if video_record:
                video_record.processing_status = "failed"
                video_record.error_message = str(e)
                await video_record.save()
        except Exception:
            pass


@router.get("/{session_id}/angle-data")
async def get_angle_data(session_id: str, current_user: User = Depends(get_current_user)):
    await _verify_session_ownership(session_id, current_user)
    angle_data = await AngleData.find_one(AngleData.session_id == PydanticObjectId(session_id))
    if not angle_data:
        raise HTTPException(status_code=404, detail="Angle data not yet available. PS1 may still be processing.")
    return angle_data.model_dump()


@router.get("/{session_id}/ps2-results")
async def get_ps2_results(session_id: str, current_user: User = Depends(get_current_user)):
    await _verify_session_ownership(session_id, current_user)
    angle_data = await AngleData.find_one(AngleData.session_id == PydanticObjectId(session_id))
    if not angle_data:
        raise HTTPException(status_code=404, detail="Session data not available.")

    rep_results = angle_data.ps2_rep_results or []
    total = len(rep_results)
    ps2_mode = getattr(angle_data, 'ps2_mode', 'mock')

    scores = []
    for r in rep_results:
        s_metric = r.get("session", {})
        scores.append(s_metric.get("session_score", 0.5))

    if scores:
        top_scores = sorted(scores, reverse=True)[:10]
        overall_score = sum(top_scores) / len(top_scores)
    else:
        overall_score = 0.0

    # Determine quality trend
    quality_trend = "stable"
    if len(scores) >= 3:
        first_half = scores[:len(scores)//2]
        second_half = scores[len(scores)//2:]
        avg1 = sum(first_half) / len(first_half)
        avg2 = sum(second_half) / len(second_half)
        if avg2 > avg1 + 0.05:
            quality_trend = "improving"
        elif avg2 < avg1 - 0.05:
            quality_trend = "declining"

    # Compute dominant errors (flagged in >30% of reps)
    error_types = ["insufficient_ROM", "too_fast", "too_slow", "knee_valgus", "asymmetric", "trunk_comp"]
    error_counts = {e: sum(r.get("error_flags", {}).get(e, 0) for r in rep_results) for e in error_types}
    dominant_errors = [k for k, v in error_counts.items() if total > 0 and v > total * 0.3]

    # Generate recommendations
    recs = []
    if "insufficient_ROM" in dominant_errors:
        recs.append("Try to increase your range of motion gradually. Aim for full flexion during each rep.")
    if "too_fast" in dominant_errors:
        recs.append("Slow down your movements. Aim for a controlled 3-second lowering phase.")
    if "too_slow" in dominant_errors:
        recs.append("Try to maintain a steady rhythm. Each rep should take 2-4 seconds.")
    if "knee_valgus" in dominant_errors:
        recs.append("Focus on knee alignment - keep your knee tracking over your second toe.")
    if "asymmetric" in dominant_errors:
        recs.append("Work on bilateral symmetry - distribute weight equally between both legs.")
    if "trunk_comp" in dominant_errors:
        recs.append("Keep your torso upright throughout the exercise. Engage your core.")
    if not recs:
        if overall_score >= 0.8:
            recs.append("Excellent form! Your movement quality is consistently good.")
        elif overall_score >= 0.6:
            recs.append("Good session overall. Focus on maintaining consistent form.")
        else:
            recs.append("Review the exercise demo and focus on controlled, full-range movements.")

    return {
        "session_id": session_id,
        "total_reps_analyzed": total,
        "overall_session_score": round(overall_score, 2),
        "quality_trend": quality_trend,
        "rep_results": rep_results,
        "dominant_errors": dominant_errors,
        "recommendations": recs,
        "ps2_mode": ps2_mode,
    }
