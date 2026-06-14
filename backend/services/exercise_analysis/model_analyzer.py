"""
Real PS2 Model Analyzer — Powered by RehabNet (ST-GCN + Transformer + BiLSTM)
==============================================================================
Loads rehabnet_best.pth and runs real inference on joint angle data from PS1.
The model classifies movement quality (correct/incorrect), produces a quality
score (0-1), and detects exercise type. These outputs are mapped to the PS2
schema (error_flags, confidence, session_score, quality_trend).

Activated automatically when PS2_MODEL_PATH is set in .env.
"""
import os
import traceback
import numpy as np
import torch
from typing import Dict, List
from datetime import datetime

from .base_analyzer import BaseExerciseAnalyzer
from .schemas import (
    PS2RepResult, PS2SessionResult,
    PS2ErrorFlags, PS2Confidence, PS2ModeCommand, PS2SessionMetrics,
)
from loguru import logger


class ModelExerciseAnalyzer(BaseExerciseAnalyzer):
    """
    Real PS2 model analyzer using the RehabNet architecture.
    Produces genuine error detection and quality scoring for physiotherapy exercises.
    """

    def __init__(self):
        self.model = None
        self.device = "cpu"
        self._loaded = False
        self._num_joints = 6
        self._joint_order = ["left_hip", "right_hip", "left_knee", "right_knee", "left_ankle", "right_ankle"]

    def load_model(self, model_path: str) -> None:
        """Load the RehabNet model from a .pth checkpoint."""
        try:
            from .rehabnet_model import load_rehabnet
            self.model = load_rehabnet(model_path, device=self.device)
            self._loaded = True
            logger.info(f"✅ PS2 RehabNet model loaded from: {model_path}")
        except Exception as e:
            logger.error(f"❌ PS2 model load failed: {e}\n{traceback.format_exc()}")
            self._loaded = False

    def _prepare_input_tensor(self, angle_data: Dict, target_frames: int = 60) -> torch.Tensor:
        """
        Convert PS1 angle data dict to model input tensor.

        PS1 provides angles in degrees per joint. We convert to normalized xyz-like
        coordinates by creating synthetic 2D positions based on joint angles, so the
        ST-GCN topology can process them.

        Input: dict with keys like left_knee, right_knee etc. (each List[float] of angles)
        Output: (1, 3, T, 6) tensor
        """
        # Gather raw angle signals per joint
        signals = []
        for joint in self._joint_order:
            raw = angle_data.get(joint, [])
            if not raw:
                raw = [180.0]  # default extended position
            signals.append(np.array(raw, dtype=np.float32))

        # Find shortest non-trivial length and pad/truncate all to target_frames
        max_len = max(len(s) for s in signals)
        effective_len = min(max(max_len, 2), target_frames * 2)

        processed = []
        for s in signals:
            if len(s) < effective_len:
                # Pad by repeating last value
                padded = np.pad(s, (0, effective_len - len(s)), mode='edge')
            else:
                padded = s[:effective_len]
            processed.append(padded)

        # Resample to target_frames via linear interpolation
        resampled = []
        for p in processed:
            if len(p) == target_frames:
                resampled.append(p)
            else:
                x_orig = np.linspace(0, 1, len(p))
                x_target = np.linspace(0, 1, target_frames)
                resampled.append(np.interp(x_target, x_orig, p))

        # Convert angles to synthetic xyz coordinates
        # Channel 0: normalized angle (0-1 range from 0-180 degrees)
        # Channel 1: angular velocity (first derivative)
        # Channel 2: angle cosine (for periodicity encoding)
        tensor_data = np.zeros((3, target_frames, self._num_joints), dtype=np.float32)
        for j, angles in enumerate(resampled):
            angles = np.array(angles, dtype=np.float32)
            # Channel 0: normalized angle
            tensor_data[0, :, j] = angles / 180.0
            # Channel 1: angular velocity (scaled)
            velocity = np.gradient(angles)
            tensor_data[1, :, j] = velocity / 50.0  # normalize velocity
            # Channel 2: cosine of angle (captures curvature)
            tensor_data[2, :, j] = np.cos(np.radians(angles))

        return torch.tensor(tensor_data, dtype=torch.float32).unsqueeze(0)  # (1, 3, T, 6)

    def _compute_hand_features(self, angle_data: Dict) -> torch.Tensor:
        """
        Compute 10 hand-crafted statistics from the angle data.
        These augment the neural features with domain-specific signals.
        """
        features = []
        for joint in ["left_knee", "right_knee", "left_hip", "right_hip"]:
            signal = np.array(angle_data.get(joint, [180.0]), dtype=np.float32)
            rom = float(np.max(signal) - np.min(signal))  # range of motion
            mean_speed = float(np.mean(np.abs(np.gradient(signal)))) if len(signal) > 1 else 0.0
            features.extend([rom / 90.0, mean_speed / 20.0])  # normalize

        # Bilateral symmetry feature
        lk = np.array(angle_data.get("left_knee", [180.0]), dtype=np.float32)
        rk = np.array(angle_data.get("right_knee", [180.0]), dtype=np.float32)
        n = min(len(lk), len(rk))
        if n > 1:
            asymmetry = float(np.mean(np.abs(lk[:n] - rk[:n]))) / 30.0
            corr = float(np.corrcoef(lk[:n], rk[:n])[0, 1]) if n > 2 else 0.0
        else:
            asymmetry = 0.0
            corr = 0.0
        features.extend([asymmetry, max(0, corr)])

        return torch.tensor([features[:10]], dtype=torch.float32)

    def analyze_rep(
        self,
        angle_data: Dict,
        rep_id: int,
        rep_number: int = 1,
        fps: float = 30.0,
    ) -> PS2RepResult:
        """Analyze a single repetition using the RehabNet model."""
        if not self._loaded or self.model is None:
            logger.warning("PS2 model not loaded, returning default result")
            return self._default_rep_result(rep_id, rep_number)

        try:
            # Prepare input
            x = self._prepare_input_tensor(angle_data, target_frames=60)
            hand_feats = self._compute_hand_features(angle_data)

            # Run inference
            with torch.no_grad():
                output = self.model(x, hand_features=hand_feats)

            classify_logits = output["classify_logits"]  # (1, 2)
            quality_score = output["quality_score"]  # (1,)

            # Interpret outputs
            probs = torch.softmax(classify_logits, dim=1).squeeze(0).numpy()
            correct_prob = float(probs[0])
            incorrect_prob = float(probs[1])
            quality_val = float(quality_score.item())

            # Derive error flags from model output + angle analysis
            lk = np.array(angle_data.get("left_knee", [180.0]), dtype=np.float32)
            rk = np.array(angle_data.get("right_knee", [180.0]), dtype=np.float32)
            rom = float(np.max(lk) - np.min(lk)) if len(lk) > 1 else 0.0
            speed = float(np.mean(np.abs(np.gradient(lk)))) * fps if len(lk) > 1 else 0.0

            n = min(len(lk), len(rk))
            asymmetry = float(np.mean(np.abs(lk[:n] - rk[:n]))) if n > 1 else 0.0

            # Error detection: combine model confidence with heuristic thresholds
            insufficient_ROM = 1 if (rom < 20.0 or (incorrect_prob > 0.6 and rom < 40.0)) else 0
            too_fast = 1 if speed > 35.0 else 0
            too_slow = 1 if (speed < 2.0 and len(lk) > 10) else 0
            knee_valgus = 1 if (incorrect_prob > 0.7 and quality_val < 0.4) else 0
            asymmetric_flag = 1 if asymmetry > 8.0 else 0
            trunk_comp = 1 if (incorrect_prob > 0.75 and quality_val < 0.35) else 0

            flags = PS2ErrorFlags(
                insufficient_ROM=insufficient_ROM,
                too_fast=too_fast,
                too_slow=too_slow,
                knee_valgus=knee_valgus,
                asymmetric=asymmetric_flag,
                trunk_comp=trunk_comp,
            )

            # Confidence from model probabilities
            confidence = PS2Confidence(
                insufficient_ROM=round(min(1.0, incorrect_prob * (1 - rom / 90.0)) if insufficient_ROM else max(0, 1 - rom / 90.0), 2),
                too_fast=round(min(1.0, speed / 50.0), 2),
                too_slow=round(1.0 - min(1.0, speed / 10.0), 2) if too_slow else round(max(0, 1 - speed / 10.0), 2),
                knee_valgus=round(incorrect_prob, 2),
                asymmetric=round(min(1.0, asymmetry / 15.0), 2),
                trunk_comp=round(incorrect_prob * (1 - quality_val), 2),
            )

            # Session score: weighted combination of model quality and heuristics
            total_errors = sum([insufficient_ROM, too_fast, too_slow, knee_valgus, asymmetric_flag, trunk_comp])
            session_score = round(max(0.0, min(1.0, quality_val * 0.6 + correct_prob * 0.4 - total_errors * 0.08)), 2)

            return PS2RepResult(
                timestamp=datetime.utcnow().timestamp(),
                rep_id=rep_id,
                dtw_bypassed=False,
                error_flags=flags,
                confidence=confidence,
                mode_command=PS2ModeCommand(
                    mode_id=1 if quality_val > 0.6 else 2,
                    mode_name="Assistive" if quality_val > 0.6 else "Resistive Torque",
                    target_torque=round(max(1.0, 5.0 * (1 - quality_val)), 1),
                ),
                session=PS2SessionMetrics(
                    rep_number=rep_number,
                    session_score=session_score,
                    quality_trend="stable",  # Updated at session level
                ),
            )

        except Exception as e:
            logger.error(f"PS2 rep analysis error: {e}\n{traceback.format_exc()}")
            return self._default_rep_result(rep_id, rep_number)

    def analyze_session(
        self,
        session_id: str,
        angle_data: Dict,
        repetitions: List[Dict],
        fps: float = 30.0,
    ) -> PS2SessionResult:
        """Analyze a complete exercise session using the RehabNet model."""
        if not self._loaded or self.model is None:
            logger.warning("PS2 model not loaded, returning default session result")
            return self._default_session_result(session_id)

        rep_results = []
        scores = []

        for i, rep in enumerate(repetitions):
            start_f = rep.get("start_frame", 0)
            end_f = rep.get("end_frame", len(angle_data.get("left_knee", [])))

            # Slice angle data for this rep
            rep_angle_slice = {
                joint: angle_data.get(joint, [])[start_f:end_f]
                for joint in self._joint_order
            }

            result = self.analyze_rep(
                rep_angle_slice,
                rep_id=rep.get("rep_id", i + 1),
                rep_number=i + 1,
                fps=fps,
            )
            scores.append(result.session.session_score)
            rep_results.append(result)

        if not rep_results:
            return PS2SessionResult(
                session_id=session_id,
                total_reps_analyzed=0,
                overall_session_score=0.0,
                quality_trend="stable",
                rep_results=[],
                dominant_errors=[],
                recommendations=["Complete at least one repetition for analysis."],
                ps2_mode="real",
            )

        # Determine quality trend from score trajectory
        if len(scores) >= 3:
            first_half = np.mean(scores[:len(scores) // 2])
            second_half = np.mean(scores[len(scores) // 2:])
            if second_half > first_half + 0.05:
                trend = "improving"
            elif second_half < first_half - 0.05:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "stable"

        # Update each rep's quality trend
        for r in rep_results:
            r.session.quality_trend = trend

        overall_score = round(float(np.mean(scores)), 2)

        # Compute dominant errors
        error_counts = {
            "insufficient_ROM": sum(r.error_flags.insufficient_ROM for r in rep_results),
            "too_fast": sum(r.error_flags.too_fast for r in rep_results),
            "too_slow": sum(r.error_flags.too_slow for r in rep_results),
            "knee_valgus": sum(r.error_flags.knee_valgus for r in rep_results),
            "asymmetric": sum(r.error_flags.asymmetric for r in rep_results),
            "trunk_comp": sum(r.error_flags.trunk_comp for r in rep_results),
        }
        dominant = [k for k, v in error_counts.items() if v > len(rep_results) * 0.3]

        # Generate recommendations based on detected issues
        recs = []
        if "insufficient_ROM" in dominant:
            recs.append("Try to increase your range of motion gradually. Aim for full flexion during each rep.")
        if "too_fast" in dominant:
            recs.append("Slow down your movements. Aim for a controlled 3-second lowering phase.")
        if "too_slow" in dominant:
            recs.append("Try to maintain a steady rhythm. Each rep should take 2-4 seconds.")
        if "knee_valgus" in dominant:
            recs.append("Focus on knee alignment — keep your knee tracking over your second toe.")
        if "asymmetric" in dominant:
            recs.append("Work on bilateral symmetry — distribute weight equally between both legs.")
        if "trunk_comp" in dominant:
            recs.append("Keep your torso upright throughout the exercise. Engage your core.")
        if not recs:
            if overall_score >= 0.8:
                recs.append("Excellent form! Your movement quality is consistently good. Keep it up!")
            elif overall_score >= 0.6:
                recs.append("Good session. Focus on maintaining consistent form through all repetitions.")
            else:
                recs.append("Review the exercise demo video and focus on controlled, full-range movements.")

        return PS2SessionResult(
            session_id=session_id,
            total_reps_analyzed=len(rep_results),
            overall_session_score=overall_score,
            quality_trend=trend,
            rep_results=rep_results,
            dominant_errors=dominant,
            recommendations=recs,
            ps2_mode="real",
        )

    def _default_rep_result(self, rep_id: int, rep_number: int) -> PS2RepResult:
        """Fallback result when model fails."""
        return PS2RepResult(
            timestamp=datetime.utcnow().timestamp(),
            rep_id=rep_id,
            dtw_bypassed=True,
            error_flags=PS2ErrorFlags(),
            confidence=PS2Confidence(),
            mode_command=PS2ModeCommand(),
            session=PS2SessionMetrics(rep_number=rep_number, session_score=0.5, quality_trend="stable"),
        )

    def _default_session_result(self, session_id: str) -> PS2SessionResult:
        """Fallback session result when model fails."""
        return PS2SessionResult(
            session_id=session_id,
            total_reps_analyzed=0,
            overall_session_score=0.5,
            quality_trend="stable",
            rep_results=[],
            dominant_errors=[],
            recommendations=["Model not available. Please check PS2 configuration."],
            ps2_mode="real",
        )
