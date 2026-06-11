"""
PS1 Pose Engine Adapter
=======================
The ONLY point of contact between the rest of Samarth and the PS1 pipeline.
PS1 internals (pipeline/) are NEVER imported directly from anywhere else.

Architecture:
  All external code  →  PoseEngineAdapter  →  PS1 modules (via sys.path injection)

Two modes:
  1. Real-time:  receives JPEG bytes per frame → returns landmarks + angles + validation
  2. Batch:      receives video file path → calls PS1's run_pipeline_on_video() → returns full analysis
"""
import sys
import os
import io
import time
import traceback
from typing import Dict, Optional
import numpy as np
import cv2
from loguru import logger

from config import settings
from .schemas import (
    RealtimeFrameResult, BatchProcessingResult,
    EngineStatus, FrameAngles, FrameValidation, LandmarkCoord, SymmetryResult, RepetitionResult
)

# Visibility threshold for considering a landmark "visible"
VISIBILITY_THRESHOLD = 0.5
# Lighting threshold: mean frame brightness
MIN_BRIGHTNESS = 50
# Zone occupancy: fraction of frame height the person must occupy
MIN_HEIGHT_FRACTION = 0.35


class PoseEngineAdapter:
    """
    Adapter wrapping PS1 pipeline. Instantiated once at app startup.
    Thread-safe for concurrent WebSocket sessions (each uses its own PoseEstimator).
    """

    def __init__(self):
        self._ps1_path = str(settings.get_ps1_path())
        self._initialized = False
        self._active_sessions: int = 0
        self._prev_landmarks: Optional[Dict] = None  # For camera stability check
        self._init()

    def _init(self):
        """Inject PS1 path and verify imports are available."""
        if self._ps1_path not in sys.path:
            sys.path.insert(0, self._ps1_path)

        try:
            # Smoke-test PS1 imports without instantiating heavy models
            import importlib
            importlib.import_module("modules.kinematics")
            importlib.import_module("modules.filter_utils")
            importlib.import_module("modules.feature_extractor")
            self._initialized = True
            logger.info(f"✅ PS1 PoseEngineAdapter initialized — path: {self._ps1_path}")
        except Exception as e:
            logger.warning(f"⚠️ PS1 adapter init warning: {e}. Will retry on first use.")

    def get_status(self) -> EngineStatus:
        try:
            import mediapipe  # noqa
            mp_available = True
        except ImportError:
            mp_available = False

        return EngineStatus(
            initialized=self._initialized,
            ps1_path=self._ps1_path,
            mediapipe_available=mp_available,
            mode="idle",
            active_sessions=self._active_sessions,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Real-time frame processing (WebSocket mode)
    # ─────────────────────────────────────────────────────────────────────────

    def process_frame(
        self,
        frame_bytes: bytes,
        frame_index: int,
        timestamp_ms: int,
        pose_estimator,         # PS1 PoseEstimator instance (caller owns lifecycle)
        kinematics_extractor,   # PS1 KinematicsExtractor instance
    ) -> RealtimeFrameResult:
        """
        Process a single JPEG frame using PS1's PoseEstimator.
        Called per-frame during a live WebSocket session.
        """
        try:
            # Decode JPEG bytes → numpy array
            nparr = np.frombuffer(frame_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if frame is None:
                return self._empty_frame_result(frame_index, timestamp_ms)

            # Run PS1 inference
            results, _seg_mask = pose_estimator.process_frame(frame)
            joints = pose_estimator.extract_joint_coordinates(results, frame.shape)

            # Extract angles
            angles = FrameAngles()
            landmarks = {}
            pose_confidence = 0.0

            if joints is not None:
                from modules.kinematics import KinematicsExtractor
                raw_angles = kinematics_extractor.extract_angles(joints)
                if raw_angles:
                    angles = FrameAngles(**raw_angles)

                # Build landmarks dict
                for name, data in joints.items():
                    landmarks[name] = LandmarkCoord(**data)

                # Compute average visibility as confidence proxy
                visibilities = [d["visibility"] for d in joints.values()]
                pose_confidence = float(np.mean(visibilities)) if visibilities else 0.0

            validation = self._validate_frame(frame, joints)
            self._prev_landmarks = joints  # Store for stability check next frame

            return RealtimeFrameResult(
                frame_index=frame_index,
                timestamp_ms=timestamp_ms,
                landmarks=landmarks,
                angles=angles,
                validation=validation,
                pose_confidence=pose_confidence,
            )

        except Exception as e:
            logger.error(f"[PoseEngine] Frame processing error: {e}")
            return self._empty_frame_result(frame_index, timestamp_ms)

    def _validate_frame(self, frame: np.ndarray, joints: Optional[Dict]) -> FrameValidation:
        """Run all 10 camera validation checks using PS1 landmark data."""
        h, w = frame.shape[:2]

        def visible(name: str) -> bool:
            if joints is None:
                return False
            jnt = joints.get(name)
            return jnt is not None

        lh = visible("LEFT_HIP")
        rh = visible("RIGHT_HIP")
        lk = visible("LEFT_KNEE")
        rk = visible("RIGHT_KNEE")
        la = visible("LEFT_ANKLE")
        ra = visible("RIGHT_ANKLE")
        full_body = all([lh, rh, lk, rk, la, ra])

        # Check user inside exercise zone (person occupies center of frame)
        inside_zone = False
        if joints:
            hip_x = joints.get("LEFT_HIP", {}).get("x_norm", 0.5)
            in_x_zone = 0.01 < hip_x < 0.99
            inside_zone = in_x_zone
        else:
            inside_zone = True

        # Lighting check: mean luminance of grayscale frame
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        mean_brightness = float(np.mean(gray))
        adequate_lighting = mean_brightness >= 10.0

        # Camera stability: compare current landmarks to previous frame
        camera_stable = True
        if self._prev_landmarks is not None and joints is not None:
            diffs = []
            for name in ["LEFT_HIP", "RIGHT_HIP", "LEFT_KNEE"]:
                prev = self._prev_landmarks.get(name)
                curr = joints.get(name)
                if prev and curr:
                    dx = abs(curr["x_norm"] - prev["x_norm"])
                    dy = abs(curr["y_norm"] - prev["y_norm"])
                    diffs.append(dx + dy)
            if diffs and np.mean(diffs) > 0.4:
                camera_stable = False

        all_valid = all([lh, rh, lk, rk, la, ra, full_body, inside_zone, adequate_lighting, camera_stable])

        # Build guidance message
        guidance = ""
        if joints is None or len(joints) == 0:
            guidance = "No person detected — stand in front of camera"
            all_valid = False
        elif not lh or not rh:
            guidance = "Move back — hips not visible"
        elif not lk or not rk:
            guidance = "Move back — knees not visible"
        elif not la or not ra:
            guidance = "Move back — ankles not visible. Ensure feet are in frame"
        elif not inside_zone:
            guidance = "Step into the exercise zone — move toward center"
        elif not adequate_lighting:
            guidance = "Improve lighting — room is too dark"
        elif not camera_stable:
            guidance = "Hold still — camera is unstable"
        elif all_valid:
            guidance = "✓ Position confirmed — ready to start!"

        return FrameValidation(
            left_hip_visible=lh,
            right_hip_visible=rh,
            left_knee_visible=lk,
            right_knee_visible=rk,
            left_ankle_visible=la,
            right_ankle_visible=ra,
            full_lower_body_visible=full_body,
            inside_zone=inside_zone,
            adequate_lighting=adequate_lighting,
            camera_stable=camera_stable,
            all_valid=all_valid,
            guidance_message=guidance,
        )

    def _empty_frame_result(self, frame_index: int, timestamp_ms: int) -> RealtimeFrameResult:
        return RealtimeFrameResult(
            frame_index=frame_index,
            timestamp_ms=timestamp_ms,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Batch video processing (upload-after mode)
    # ─────────────────────────────────────────────────────────────────────────

    def process_video(self, video_path: str, session_id: str, output_dir: str) -> BatchProcessingResult:
        """
        Run PS1's full pipeline on an uploaded video file.
        Calls PS1's run_pipeline_on_video() — the same function used in PS1's main.py.
        """
        try:
            os.makedirs(output_dir, exist_ok=True)

            # Ensure PS1 path is in sys.path first!
            if self._ps1_path not in sys.path:
                sys.path.insert(0, self._ps1_path)

            # Import PS1 components
            from modules.background_seg import BackgroundSegmenter
            from modules.video_enhance import VideoEnhancer
            from modules.pose_estimator import PoseEstimator

            # PS1 main pipeline function
            import importlib.util
            spec = importlib.util.spec_from_file_location("ps1_main", os.path.join(self._ps1_path, "main.py"))
            ps1_main = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(ps1_main)

            bg_handler = BackgroundSegmenter(use_isnet=False, device="cpu")
            enhancer = VideoEnhancer(enabled=settings.PS1_ENHANCE, level=settings.PS1_ENHANCE_LEVEL)
            pose_estimator = PoseEstimator()

            ts_df, sum_df, video_summary = ps1_main.run_pipeline_on_video(
                video_path=video_path,
                output_subfolder_dir=output_dir,
                bg_handler=bg_handler,
                pose_estimator=pose_estimator,
                stride=settings.PS1_STRIDE,
                save_annotated_video=settings.PS1_SAVE_ANNOTATED_VIDEO,
                enhancer=enhancer,
            )
            pose_estimator.close()

            # Parse repetitions
            reps = [RepetitionResult(**r) for r in video_summary.get("reps", [])]

            # Parse symmetry
            symmetry_raw = video_summary.get("summary", {}).get("symmetry", {})
            symmetry = {k: SymmetryResult(**v) for k, v in symmetry_raw.items()}

            ts = video_summary.get("time_series_data", {})
            total_frames = len(ts.get("left_knee", []))

            return BatchProcessingResult(
                session_id=session_id,
                video_name=os.path.basename(video_path),
                fps=video_summary.get("fps", 30.0),
                total_frames=total_frames,
                landmarks_detected_count=total_frames,  # PS1 fills with mock if not detected
                time_series={k: [float(x) for x in v] for k, v in ts.items() if isinstance(v, list)},
                repetitions=reps,
                symmetry=symmetry,
                avg_left_rom=video_summary.get("avg_left_rom", 0.0),
                avg_right_rom=video_summary.get("avg_right_rom", 0.0),
                total_reps=len(reps),
                quality_summary=video_summary.get("quality_summary", {}),
                csv_timeseries_path=os.path.join(output_dir, "joint_data_timeseries.csv"),
                csv_summary_path=os.path.join(output_dir, "exercise_summary.csv"),
                status="success",
            )

        except Exception as e:
            tb = traceback.format_exc()
            logger.error(f"[PoseEngine] Batch processing failed: {e}\n{tb}")
            return BatchProcessingResult(
                session_id=session_id,
                video_name=os.path.basename(video_path),
                fps=30.0,
                total_frames=0,
                landmarks_detected_count=0,
                time_series={},
                repetitions=[],
                symmetry={},
                avg_left_rom=0.0,
                avg_right_rom=0.0,
                total_reps=0,
                quality_summary={},
                status="failed",
                error=str(e),
            )

    def create_session_context(self):
        """
        Create a per-session pose estimator and kinematics extractor.
        Caller is responsible for cleanup via close_session_context().
        """
        from modules.pose_estimator import PoseEstimator
        from modules.kinematics import KinematicsExtractor
        self._active_sessions += 1
        return PoseEstimator(), KinematicsExtractor()

    def close_session_context(self, pose_estimator):
        pose_estimator.close()
        self._active_sessions = max(0, self._active_sessions - 1)


# Singleton adapter instance
_adapter: PoseEngineAdapter | None = None


def get_pose_engine() -> PoseEngineAdapter:
    global _adapter
    if _adapter is None:
        _adapter = PoseEngineAdapter()
    return _adapter
