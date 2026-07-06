import cv2
import numpy as np
from typing import Optional, Generator, Tuple

class VideoProcessor:
    """Utility class to read, resize, and standardize video frames"""
    def __init__(self, video_path):
        self.video_path = video_path
        self.cap = cv2.VideoCapture(video_path)
        if not self.cap.isOpened():
            raise IOError(f"Could not open video file {video_path}")
            
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if self.fps <= 0:
            self.fps = 30.0  # Fallback to standard 30 FPS if not metadata available

    def get_metadata(self):
        """Return video metadata"""
        return {
            "path": self.video_path,
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "frame_count": self.frame_count,
            "duration": self.frame_count / self.fps if self.fps > 0 else 0
        }

    def frame_generator(
        self,
        target_size=None,
        standardize=False,
        enhancer=None,
    ) -> Generator[Tuple[np.ndarray, np.ndarray, dict], None, None]:
        """
        Generator that yields processed video frames one by one.

        Yields
        ------
        original_frame : np.ndarray
            Raw BGR frame straight from the video (uint8). Always unchanged;
            used for visual overlays and annotation.
        processed_frame : np.ndarray
            Frame after optional enhancement, resize, and/or standardisation.
            This is the frame that should be fed to pose estimation.
        quality_report : dict
            Per-frame quality report produced by VideoEnhancer
            (empty dict when no enhancer is attached).
        """
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # Reset to start
        while True:
            ret, frame = self.cap.read()
            if not ret:
                break

            # Keep copy of original frame for overlays
            original_frame = frame.copy()

            # ── Video Quality Enhancement ───────────────────────────────────
            # Run adaptive quality correction before any resize / normalisation
            # so the enhancer sees the full-resolution signal metrics.
            quality_report: dict = {}
            if enhancer is not None:
                frame, quality_report = enhancer.enhance(frame)

            # Resize frame if target size is given
            if target_size is not None:
                frame = cv2.resize(frame, target_size)

            # Standardize pixel values (normalize to 0-1)
            if standardize:
                frame = frame.astype(np.float32) / 255.0

            yield original_frame, frame, quality_report

    def read_all_frames(
        self,
        target_size=None,
        standardize=False,
        enhancer=None,
    ):
        """Read and return all frames at once (useful for short clips).

        Returns
        -------
        original_frames : list of np.ndarray
        processed_frames : list of np.ndarray  (enhanced when enhancer is set)
        quality_reports  : list of dict
        """
        original_frames = []
        processed_frames = []
        quality_reports = []
        for orig, proc, qr in self.frame_generator(target_size, standardize, enhancer):
            original_frames.append(orig)
            processed_frames.append(proc)
            quality_reports.append(qr)
        return original_frames, processed_frames, quality_reports

    def release(self):
        """Release VideoCapture resources"""
        if self.cap is not None:
            self.cap.release()

    def __del__(self):
        self.release()
