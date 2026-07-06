"""
PS2 Exercise Analysis Schemas
Exact Pydantic models matching the PS2 output JSON contract.
"""
from datetime import datetime
from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class PS2ErrorFlags(BaseModel):
    """Binary flags for each detected movement error (0=no error, 1=error detected)."""
    insufficient_ROM: int = 0
    too_fast: int = 0
    too_slow: int = 0
    knee_valgus: int = 0
    asymmetric: int = 0
    trunk_comp: int = 0


class PS2Confidence(BaseModel):
    """Model confidence score (0.0-1.0) for each error type."""
    insufficient_ROM: float = 0.0
    too_fast: float = 0.0
    too_slow: float = 0.0
    knee_valgus: float = 0.0
    asymmetric: float = 0.0
    trunk_comp: float = 0.0


class PS2ModeCommand(BaseModel):
    """Resistance/mode command output from PS2 model."""
    mode_id: int = 0
    mode_name: str = "None"
    target_torque: float = 0.0


class PS2SessionMetrics(BaseModel):
    """Session-level metrics from PS2 analysis."""
    rep_number: int = 0
    session_score: float = 0.0
    quality_trend: Literal["improving", "stable", "declining"] = "stable"


class PS2RepResult(BaseModel):
    """Complete PS2 output for a single repetition - matches exact PS2 JSON schema."""
    timestamp: float = Field(default_factory=lambda: datetime.utcnow().timestamp())
    rep_id: int
    dtw_bypassed: bool = False
    error_flags: PS2ErrorFlags = Field(default_factory=PS2ErrorFlags)
    confidence: PS2Confidence = Field(default_factory=PS2Confidence)
    mode_command: PS2ModeCommand = Field(default_factory=PS2ModeCommand)
    session: PS2SessionMetrics = Field(default_factory=PS2SessionMetrics)


class PS2SessionResult(BaseModel):
    """Full session analysis result from PS2."""
    session_id: str
    total_reps_analyzed: int = 0
    overall_session_score: float = 0.0
    quality_trend: Literal["improving", "stable", "declining"] = "stable"
    rep_results: List[PS2RepResult] = Field(default_factory=list)
    dominant_errors: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    ps2_mode: Literal["real"] = "real"
