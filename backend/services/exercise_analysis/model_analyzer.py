"""
Real PS2 Model Analyzer — TEMPLATE FOR YOUR TEAMMATE
=====================================================
When your PS2 model is ready:
1. Fill in the load_model() and analyze_rep() methods
2. Set PS2_MODEL_PATH=<path> in .env
3. System auto-switches from mock to this analyzer

Supported model formats: PyTorch, ONNX, scikit-learn, TensorFlow SavedModel
"""
from typing import Dict, List
from .base_analyzer import BaseExerciseAnalyzer
from .schemas import PS2RepResult, PS2SessionResult
from .mock_analyzer import MockExerciseAnalyzer


class ModelExerciseAnalyzer(BaseExerciseAnalyzer):
    """
    Real PS2 model analyzer. 
    Falls back to MockExerciseAnalyzer if model fails to load.
    """

    def __init__(self):
        self.model = None
        self._fallback = MockExerciseAnalyzer()
        self._loaded = False

    def load_model(self, model_path: str) -> None:
        """
        TODO (PS2 teammate): Load your trained model here.
        
        Example for PyTorch:
            import torch
            self.model = torch.load(model_path, map_location='cpu')
            self.model.eval()
        
        Example for ONNX:
            import onnxruntime as ort
            self.model = ort.InferenceSession(model_path)
        
        Example for scikit-learn:
            import joblib
            self.model = joblib.load(model_path)
        """
        try:
            # ── INSERT YOUR MODEL LOADING CODE HERE ──────────────────────────
            # self.model = ...
            # ─────────────────────────────────────────────────────────────────
            self._loaded = bool(self.model)
        except Exception as e:
            import traceback
            print(f"[PS2] Model load failed: {e}\n{traceback.format_exc()}")
            self._loaded = False

    def analyze_rep(
        self,
        angle_data: Dict,
        rep_id: int,
        rep_number: int = 1,
        fps: float = 30.0,
    ) -> PS2RepResult:
        if not self._loaded:
            return self._fallback.analyze_rep(angle_data, rep_id, rep_number, fps)

        # ── INSERT YOUR INFERENCE CODE HERE ──────────────────────────────────
        # features = self._extract_features(angle_data, fps)
        # prediction = self.model.predict(features)
        # return PS2RepResult(
        #     rep_id=rep_id,
        #     error_flags=PS2ErrorFlags(**prediction.flags),
        #     confidence=PS2Confidence(**prediction.confidence),
        #     ...
        # )
        # ─────────────────────────────────────────────────────────────────────

        return self._fallback.analyze_rep(angle_data, rep_id, rep_number, fps)

    def analyze_session(
        self,
        session_id: str,
        angle_data: Dict,
        repetitions: List[Dict],
        fps: float = 30.0,
    ) -> PS2SessionResult:
        if not self._loaded:
            return self._fallback.analyze_session(session_id, angle_data, repetitions, fps)

        # ── INSERT YOUR SESSION-LEVEL INFERENCE CODE HERE ────────────────────
        # Run rep-by-rep inference and aggregate
        # ─────────────────────────────────────────────────────────────────────

        return self._fallback.analyze_session(session_id, angle_data, repetitions, fps)

    def _extract_features(self, angle_data: Dict, fps: float) -> list:
        """
        TODO (PS2 teammate): Extract feature vector from angle_data for model input.
        Expected input keys: left_knee, right_knee, left_hip, right_hip, 
                             left_ankle, right_ankle (all List[float])
        """
        import numpy as np
        features = []
        for joint in ["left_knee", "right_knee", "left_hip", "right_hip"]:
            signal = angle_data.get(joint, [])
            if signal:
                arr = np.array(signal)
                features.extend([
                    float(np.mean(arr)),
                    float(np.std(arr)),
                    float(np.max(arr) - np.min(arr)),  # ROM
                    float(np.mean(np.abs(np.diff(arr)))) * fps,  # avg speed
                ])
        return features
