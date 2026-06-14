"""
PS1 Pose Engine Adapter Schemas
Input/output Pydantic models for all PS1 adapter interactions.
"""
from typing import Dict, List, Literal, Optional
from pydantic import BaseModel


class LandmarkCoord(BaseModel):
    x_norm: float
    y_norm: float
    z_norm: float
    visibility: float
    x_px: int
    y_px: int


class FrameValidation(BaseModel):
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
    all_valid: bool = False
    guidance_message: str = ""


class FrameAngles(BaseModel):
    left_hip: float = 0.0
    right_hip: float = 0.0
    left_knee: float = 0.0
    right_knee: float = 0.0
    left_ankle: float = 0.0
    right_ankle: float = 0.0


class RealtimeFrameResult(BaseModel):
    """Result returned per-frame during live WebSocket session."""
    frame_index: int
    timestamp_ms: int
    landmarks: Dict[str, LandmarkCoord] = {}
    angles: FrameAngles = FrameAngles()
    validation: FrameValidation = FrameValidation()
    pose_confidence: float = 0.0


class RepetitionResult(BaseModel):
    rep_id: int
    start_frame: int
    peak_frame: int
    end_frame: int
    start_time: float
    peak_time: float
    end_time: float
    duration: float
    rom: float


class SymmetryResult(BaseModel):
    trajectory_correlation: float = 0.0
    left_overall_rom: float = 0.0
    right_overall_rom: float = 0.0
    rom_symmetry_index: float = 0.0
    average_angle_difference: float = 0.0
    symmetry_score_percentage: float = 0.0


class BatchProcessingResult(BaseModel):
    """Full result from PS1 batch video processing."""
    session_id: str
    video_name: str
    fps: float
    total_frames: int
    landmarks_detected_count: int
    time_series: Dict[str, List[float]]
    repetitions: List[RepetitionResult]
    symmetry: Dict[str, SymmetryResult]
    avg_left_rom: float
    avg_right_rom: float
    total_reps: int
    quality_summary: Dict
    csv_timeseries_path: Optional[str] = None
    csv_summary_path: Optional[str] = None
    annotated_video_path: Optional[str] = None
    status: Literal["success", "partial", "failed"] = "success"
    error: Optional[str] = None



class EngineStatus(BaseModel):
    initialized: bool = False
    ps1_path: str = ""
    mediapipe_available: bool = False
    mode: Literal["realtime", "batch", "idle"] = "idle"
    active_sessions: int = 0
