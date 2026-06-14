"""PS2 Exercise Analysis API — mock or real depending on PS2_MODEL_PATH."""
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

    return PS2SessionResult(
        session_id=session_id,
        total_reps_analyzed=len(rep_results),
        overall_session_score=session.session_score or 0.0,
        quality_trend=session.quality_trend or "stable",
        rep_results=rep_results,
        ps2_mode="mock",
    )


@router.get("/status")
async def ps2_status(current_user: User = Depends(get_current_user)):
    from backend_config import settings
    return {
        "mode": "real" if settings.PS2_USE_REAL_MODEL else "mock",
        "model_path": settings.PS2_MODEL_PATH or None,
        "ready": True,
    }
