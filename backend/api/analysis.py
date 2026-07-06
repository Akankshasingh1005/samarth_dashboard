"""PS2 Exercise Analysis API using the configured real RehabNet model."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional
from services.exercise_analysis import get_analyzer
from services.exercise_analysis.schemas import PS2SessionResult, PS2RepResult
from services.auth_service import get_current_user
from models.user import User

router = APIRouter()


class AnalyzeRepRequest(BaseModel):
    angle_data: Dict[str, List[float]]
    rep_id: int
    rep_number: int = 1
    fps: float = 30.0


class AnalyzeSessionRequest(BaseModel):
    session_id: str
    angle_data: Dict[str, List[float]]
    repetitions: List[Dict]
    fps: float = 30.0


@router.post("/error-detection", response_model=PS2RepResult)
async def error_detection(req: AnalyzeRepRequest, current_user: User = Depends(get_current_user)):
    """Analyze a single rep for movement errors. Returns PS2 JSON schema."""
    analyzer = get_analyzer()
    return analyzer.analyze_rep(req.angle_data, req.rep_id, req.rep_number, req.fps)


@router.post("/session/{session_id}", response_model=PS2SessionResult)
async def analyze_session(
    session_id: str,
    req: AnalyzeSessionRequest,
    current_user: User = Depends(get_current_user),
):
    """Analyze full session. Returns session_score, quality_trend, per-rep results."""
    analyzer = get_analyzer()
    return analyzer.analyze_session(session_id, req.angle_data, req.repetitions, req.fps)


@router.get("/session/{session_id}", response_model=PS2SessionResult)
async def get_session_analysis(session_id: str, current_user: User = Depends(get_current_user)):
    """Retrieve stored PS2 analysis for a completed session."""
    from models.angle_data import AngleData
    from beanie import PydanticObjectId
    from models.session import Session

    session = await Session.get(PydanticObjectId(session_id))
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    angle_data = await AngleData.find_one(AngleData.session_id == PydanticObjectId(session_id))
    if not angle_data or not angle_data.ps2_rep_results:
        raise HTTPException(status_code=404, detail="PS2 analysis not yet available")

    from services.exercise_analysis.schemas import PS2RepResult, PS2ErrorFlags, PS2Confidence, PS2ModeCommand, PS2SessionMetrics
    rep_results = [PS2RepResult(**r) for r in angle_data.ps2_rep_results]

    total = len(rep_results)
    error_types = ["insufficient_ROM", "too_fast", "too_slow", "knee_valgus", "asymmetric", "trunk_comp"]
    error_counts = {e: sum(getattr(r.error_flags, e, 0) for r in rep_results) for e in error_types}
    dominant_errors = [k for k, v in error_counts.items() if total > 0 and v > total * 0.3]

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
        overall_score = session.session_score or 0.0
        if overall_score >= 0.8:
            recs.append("Excellent form! Your movement quality is consistently good. Keep it up!")
        elif overall_score >= 0.6:
            recs.append("Good session. Focus on maintaining consistent form through all repetitions.")
        else:
            recs.append("Review the exercise demo video and focus on controlled, full-range movements.")

    ps2_mode = getattr(angle_data, "ps2_mode", "real")

    return PS2SessionResult(
        session_id=session_id,
        total_reps_analyzed=total,
        overall_session_score=session.session_score or 0.0,
        quality_trend=session.quality_trend or "stable",
        rep_results=rep_results,
        dominant_errors=dominant_errors,
        recommendations=recs,
        ps2_mode=ps2_mode,
    )


@router.get("/status")
async def ps2_status(current_user: User = Depends(get_current_user)):
    from backend_config import settings
    return {
        "mode": "real" if settings.PS2_USE_REAL_MODEL else "not_configured",
        "model_path": settings.PS2_MODEL_PATH or None,
        "ready": bool(settings.PS2_USE_REAL_MODEL and settings.PS2_MODEL_PATH),
    }
