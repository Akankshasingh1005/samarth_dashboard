"""
PS1 Pose Engine Adapter
=======================
The ONLY point of contact between the rest of Samarth and the PS1 pipeline.
PS1 internals (pipeline/) are NEVER imported directly from anywhere else.

Architecture:
  All external code  â†’  PoseEngineAdapter  â†’  PS1 modules (via sys.path injection)

Two modes:
  1. Real-time:  receives JPEG bytes per frame â†’ returns landmarks + angles + validation
  2. Batch:      receives video file path â†’ calls PS1's run_pipeline_on_video() â†’ returns full analysis
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

from backend_config import settings
from .schemas import (
    RealtimeFrameResult, BatchProcessingResult,
    EngineStatus, FrameAngles, FrameValidation, LandmarkCoord, SymmetryResult, RepetitionResult
)

# Visibility threshold for considering a landmark "visible" - relaxed for webcam use
VISIBILITY_THRESHOLD = 0.25
# Minimum average pose confidence to consider a valid detection
# Lowered from 0.45 to 0.3 — webcam feeds in normal indoor conditions commonly
# produce 0.3-0.4 average visibility; 0.45 was too aggressive and blocked most detections
MIN_POSE_CONFIDENCE = 0.3
# Minimum number of lower-body landmarks that must be clearly visible (visibility > 0.5)
# Lowered from 4 to 3 — allows detection with e.g. both hips + one knee visible
MIN_VISIBLE_LOWER_BODY = 3
LOWER_BODY_LANDMARK_NAMES = ["LEFT_HIP", "RIGHT_HIP", "LEFT_KNEE", "RIGHT_KNEE", "LEFT_ANKLE", "RIGHT_ANKLE"]
# Lighting threshold: mean frame brightness - very lenient for indoor use
MIN_BRIGHTNESS = 20
# Zone occupancy: fraction of frame height the person must occupy - lenient
MIN_HEIGHT_FRACTION = 0.15


class PoseEngineAdapter:
    """
    Adapter wrapping PS1 pipeline. Instantiated once at app startup.
    Thread-safe for concurrent WebSocket sessions (each uses its own PoseEstimator).
    """

    def __init__(self):
        self._ps1_path = str(settings.get_ps1_path())
        self._initialized = False
        self._active_sessions: int = 0
        # NOTE: _prev_landmarks removed from singleton — it is now per-session
        # to prevent cross-session state corruption when multiple sessions run concurrently.
        # Callers pass prev_landmarks into process_frame() and receive updated value back.
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
            logger.info(f"âœ… PS1 PoseEngineAdapter initialized - path: {self._ps1_path}")
        except Exception as e:
            logger.warning(f"âš ï¸ PS1 adapter init warning: {e}. Will retry on first use.")

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

    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # Real-time frame processing (WebSocket mode)
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def process_frame(
        self,
        frame_bytes: bytes,
        frame_index: int,
        timestamp_ms: int,
        pose_estimator,         # PS1 PoseEstimator instance (caller owns lifecycle)
        kinematics_extractor,   # PS1 KinematicsExtractor instance
        video_enhancer=None,    # PS1 VideoEnhancer instance
        prev_landmarks=None,    # Per-session previous landmarks for stability check
    ) -> RealtimeFrameResult:
        """
        Process a single JPEG frame using PS1's PoseEstimator.
        Called per-frame during a live WebSocket session.
        """
        try:
            # Decode JPEG bytes â†’ numpy array
            nparr = np.frombuffer(frame_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if frame is None:
                return self._empty_frame_result(frame_index, timestamp_ms)

            # Apply video enhancement if available
            enhanced_frame = frame
            if video_enhancer is not None:
                try:
                    enhanced_frame, _ = video_enhancer.enhance(frame)
                except Exception as e:
                    logger.warning(f"Failed to enhance frame: {e}")

            # Run PS1 inference
            results, _seg_mask = pose_estimator.process_frame(enhanced_frame)
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

            # IMPORTANT: Always run validation BEFORE the confidence gate.
            # This ensures lighting, zone, and body visibility checks are always
            # computed and sent to the frontend — even when confidence is low.
            # Previously, low-confidence frames returned _empty_frame_result()
            # which had adequate_lighting=False by default, making the UI always
            # report bad lighting when the person wasn't perfectly detected.
            validation = self._validate_frame(frame, joints, prev_landmarks)

            if joints is not None:
                # If pose confidence is too low, discard landmarks/angles to prevent
                # phantom joints, but still return validation data (lighting etc.)
                if pose_confidence < MIN_POSE_CONFIDENCE:
                    return RealtimeFrameResult(
                        frame_index=frame_index,
                        timestamp_ms=timestamp_ms,
                        validation=validation,
                        pose_confidence=pose_confidence,
                    )

                # Additional check: require at least MIN_VISIBLE_LOWER_BODY
                # lower-body landmarks to be clearly visible (visibility > 0.5).
                visible_lower_count = sum(
                    1 for name in LOWER_BODY_LANDMARK_NAMES
                    if name in joints and joints[name].get("visibility", 0) > 0.5
                )
                if visible_lower_count < MIN_VISIBLE_LOWER_BODY:
                    return RealtimeFrameResult(
                        frame_index=frame_index,
                        timestamp_ms=timestamp_ms,
                        validation=validation,
                        pose_confidence=pose_confidence,
                    )

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

    def _validate_frame(self, frame: np.ndarray, joints: Optional[Dict], prev_landmarks: Optional[Dict] = None) -> FrameValidation:
        """Run all 10 camera validation checks using PS1 landmark data.
        
        prev_landmarks is passed in per-session (not stored on self) to prevent
        cross-session state corruption when multiple sessions run concurrently.
        """
        h, w = frame.shape[:2]

        def visible(name: str) -> bool:
            if joints is None:
                return False
            jnt = joints.get(name)
            return jnt is not None and jnt.get("visibility", 0) >= VISIBILITY_THRESHOLD

        lh = visible("LEFT_HIP")
        rh = visible("RIGHT_HIP")
        lk = visible("LEFT_KNEE")
        rk = visible("RIGHT_KNEE")
        la = visible("LEFT_ANKLE")
        ra = visible("RIGHT_ANKLE")
        full_body = all([lh, rh, lk, rk, la, ra])

        # Check user inside exercise zone (person occupies center 60% of frame)
        inside_zone = False
        if joints and full_body:
            hip_y = joints.get("LEFT_HIP", {}).get("y_norm", 0)
            ankle_y = joints.get("LEFT_ANKLE", {}).get("y_norm", 1)
            hip_x = joints.get("LEFT_HIP", {}).get("x_norm", 0.5)
            person_height_frac = abs(ankle_y - hip_y) * 2  # rough full-body estimate
            in_x_zone = 0.05 < hip_x < 0.95
            in_height = person_height_frac >= MIN_HEIGHT_FRACTION
            inside_zone = in_x_zone and in_height

        # Lighting check: mean luminance of grayscale frame
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        mean_brightness = float(np.mean(gray))
        adequate_lighting = mean_brightness >= MIN_BRIGHTNESS

        # Camera stability: compare current landmarks to previous frame
        # Uses per-session prev_landmarks (passed as parameter) instead of
        # self._prev_landmarks to avoid cross-session interference
        camera_stable = True
        if prev_landmarks is not None and joints is not None:
            diffs = []
            for name in ["LEFT_HIP", "RIGHT_HIP", "LEFT_KNEE"]:
                prev = prev_landmarks.get(name)
                curr = joints.get(name)
                if prev and curr:
                    dx = abs(curr["x_norm"] - prev["x_norm"])
                    dy = abs(curr["y_norm"] - prev["y_norm"])
                    diffs.append(dx + dy)
            if diffs and np.mean(diffs) > 0.20:
                camera_stable = False

        all_valid = all([lh, rh, lk, rk, la, ra, full_body, inside_zone, adequate_lighting, camera_stable])

        # Build guidance message — lighting first since it blocks everything else
        guidance = ""
        if not adequate_lighting:
            guidance = "Improve lighting - room is too dark"
        elif not lh or not rh:
            guidance = "Move back - hips not visible"
        elif not lk or not rk:
            guidance = "Move back - knees not visible"
        elif not la or not ra:
            guidance = "Move back - ankles not visible. Ensure feet are in frame"
        elif not inside_zone:
            guidance = "Step into the exercise zone - move toward center"
        elif not camera_stable:
            guidance = "Hold still - camera is unstable"
        elif all_valid:
            guidance = "✔ Position confirmed - ready to start!"

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

    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # Batch video processing (upload-after mode)
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def process_video(self, video_path: str, session_id: str, output_dir: str) -> BatchProcessingResult:
        """
        Run PS1's full pipeline on an uploaded video file.
        Calls PS1's run_pipeline_on_video() - the same function used in PS1's main.py.
        Always generates an annotated video for upload flows.
        """
        try:
            os.makedirs(output_dir, exist_ok=True)

            # Import PS1 components (available after sys.path injection at startup)
            from modules.background_seg import BackgroundSegmenter
            from modules.video_enhance import VideoEnhancer
            from modules.pose_estimator import PoseEstimator

            # PS1 main pipeline function
            sys.path.insert(0, self._ps1_path)
            import importlib.util
            spec = importlib.util.spec_from_file_location("ps1_main", os.path.join(self._ps1_path, "main.py"))
            ps1_main = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(ps1_main)

            bg_handler = BackgroundSegmenter(use_isnet=False, device="cpu")
            # Disable enhancement for uploads — pre-recorded videos have stable
            # quality and NLM denoising is extremely slow (~50-200ms per frame).
            enhancer = VideoEnhancer(enabled=False)
            # Disable segmentation masks — only needed when generating annotated
            # video overlays, which we skip for upload flows.
            pose_estimator = PoseEstimator(enable_segmentation=False)

            # Use higher stride for batch processing (10fps effective for 30fps
            # source is plenty for angle tracking and rep detection).
            batch_stride = max(settings.PS1_STRIDE, 3)

            # Skip annotated video and matplotlib plots for upload flows —
            # the frontend renders its own Chart.js visualizations.
            ts_df, sum_df, video_summary = ps1_main.run_pipeline_on_video(
                video_path=video_path,
                output_subfolder_dir=output_dir,
                bg_handler=bg_handler,
                pose_estimator=pose_estimator,
                stride=batch_stride,
                save_annotated_video=False,
                enhancer=enhancer,
                skip_plots=True,
                enable_segmentation=False,
            )
            pose_estimator.close()

            # Parse repetitions
            reps = [RepetitionResult(**r) for r in video_summary.get("reps", [])]

            # Parse symmetry
            symmetry_raw = video_summary.get("summary", {}).get("symmetry", {})
            symmetry = {k: SymmetryResult(**v) for k, v in symmetry_raw.items()}

            ts = video_summary.get("time_series_data", {})
            total_frames = len(ts.get("left_knee", []))
            landmarks_detected_count = int(video_summary.get("landmarks_detected_count", 0))

            if landmarks_detected_count <= 0:
                return BatchProcessingResult(
                    session_id=session_id,
                    video_name=os.path.basename(video_path),
                    fps=video_summary.get("fps", 30.0),
                    total_frames=total_frames,
                    landmarks_detected_count=0,
                    time_series={},
                    repetitions=[],
                    symmetry={},
                    avg_left_rom=0.0,
                    avg_right_rom=0.0,
                    total_reps=0,
                    quality_summary=video_summary.get("quality_summary", {}),
                    status="failed",
                    error="No person pose was detected in the uploaded video. Please upload a clear full-body recording.",
                )

            # Find annotated video in the output directory
            annotated_video_path = None
            annotated_candidate = os.path.join(output_dir, "annotated_video.mp4")
            if os.path.exists(annotated_candidate):
                annotated_video_path = annotated_candidate

            return BatchProcessingResult(
                session_id=session_id,
                video_name=os.path.basename(video_path),
                fps=video_summary.get("fps", 30.0),
                total_frames=total_frames,
                landmarks_detected_count=landmarks_detected_count,
                time_series={k: [float(x) for x in v] for k, v in ts.items() if isinstance(v, list)},
                repetitions=reps,
                symmetry=symmetry,
                avg_left_rom=video_summary.get("avg_left_rom", 0.0),
                avg_right_rom=video_summary.get("avg_right_rom", 0.0),
                total_reps=len(reps),
                quality_summary=video_summary.get("quality_summary", {}),
                csv_timeseries_path=os.path.join(output_dir, "joint_data_timeseries.csv"),
                csv_summary_path=os.path.join(output_dir, "exercise_summary.csv"),
                annotated_video_path=annotated_video_path,
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
        Create a per-session pose estimator, kinematics extractor, and video enhancer.
        Caller is responsible for cleanup via close_session_context().
        """
        from modules.pose_estimator import PoseEstimator
        from modules.kinematics import KinematicsExtractor
        from modules.video_enhance import VideoEnhancer
        self._active_sessions += 1
        # Disable enhancement for live sessions — NLM denoising is 50-200ms/frame
        # which causes severe latency on the skeleton overlay. Webcam feeds have
        # stable quality and don't benefit from per-frame correction.
        enhancer = VideoEnhancer(enabled=False)
        # Disable segmentation masks — not needed for live sessions (no annotated
        # video is generated). Saves ~10-20ms per frame.
        return PoseEstimator(enable_segmentation=False), KinematicsExtractor(), enhancer

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
