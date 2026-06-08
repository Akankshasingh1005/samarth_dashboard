"""
Mock PS2 Exercise Analyzer
Returns realistic simulated responses matching the exact PS2 JSON schema.
Active until PS2_MODEL_PATH is set in .env, at which point ModelExerciseAnalyzer takes over.
"""
import random
import numpy as np
from datetime import datetime
from typing import Dict, List

from .base_analyzer import BaseExerciseAnalyzer
from .schemas import (
    PS2RepResult, PS2SessionResult,
    PS2ErrorFlags, PS2Confidence, PS2ModeCommand, PS2SessionMetrics,
)


class MockExerciseAnalyzer(BaseExerciseAnalyzer):
    """
    Simulated PS2 analyzer. Generates realistic-looking error flags,
    confidence scores, session scores, and quality trends based on
    the angle data from PS1 — so the UI shows meaningful data.
    """

    def load_model(self, model_path: str) -> None:
        pass  # No-op for mock

    def analyze_rep(
        self,
        angle_data: Dict,
        rep_id: int,
        rep_number: int = 1,
        fps: float = 30.0,
    ) -> PS2RepResult:
        left_knee = angle_data.get("left_knee", [])
        right_knee = angle_data.get("right_knee", [])

        # Derive mock signals from actual PS1 data
        rom = 0.0
        speed = 0.0
        asymmetry = 0.0
        if left_knee and right_knee:
            rom = float(max(left_knee) - min(left_knee))
            if len(left_knee) > 1:
                speed = float(np.mean(np.abs(np.diff(left_knee)))) * fps
            n = min(len(left_knee), len(right_knee))
            if n > 0:
                asymmetry = float(np.mean(np.abs(
                    np.array(left_knee[:n]) - np.array(right_knee[:n])
                )))

        # Error flag logic from angle signals
        insufficient_ROM = 1 if rom < 20.0 else 0
        too_fast = 1 if speed > 40.0 else 0
        too_slow = 1 if speed < 2.0 and len(left_knee) > 10 else 0
        asymmetric = 1 if asymmetry > 10.0 else 0
        knee_valgus = random.choices([0, 1], weights=[0.85, 0.15])[0]
        trunk_comp = random.choices([0, 1], weights=[0.90, 0.10])[0]

        flags = PS2ErrorFlags(
            insufficient_ROM=insufficient_ROM,
            too_fast=too_fast,
            too_slow=too_slow,
            knee_valgus=knee_valgus,
            asymmetric=asymmetric,
            trunk_comp=trunk_comp,
        )

        # Confidence scores: errors have high confidence, non-errors low
        def conf(flag: int, base: float) -> float:
            return round(random.uniform(0.72, 0.95), 2) if flag else round(random.uniform(0.02, 0.25), 2)

        confidence = PS2Confidence(
            insufficient_ROM=conf(insufficient_ROM, 0.85),
            too_fast=conf(too_fast, 0.87),
            too_slow=conf(too_slow, 0.80),
            knee_valgus=conf(knee_valgus, 0.78),
            asymmetric=conf(asymmetric, 0.82),
            trunk_comp=conf(trunk_comp, 0.75),
        )

        total_errors = sum([insufficient_ROM, too_fast, too_slow, knee_valgus, asymmetric, trunk_comp])
        session_score = round(max(0.0, 1.0 - (total_errors * 0.15) - random.uniform(0, 0.05)), 2)

        return PS2RepResult(
            timestamp=datetime.utcnow().timestamp(),
            rep_id=rep_id,
            dtw_bypassed=False,
            error_flags=flags,
            confidence=confidence,
            mode_command=PS2ModeCommand(
                mode_id=2,
                mode_name="Resistive Torque",
                target_torque=round(random.uniform(2.0, 4.5), 1),
            ),
            session=PS2SessionMetrics(
                rep_number=rep_number,
                session_score=session_score,
                quality_trend="stable",
            ),
        )

    def analyze_session(
        self,
        session_id: str,
        angle_data: Dict,
        repetitions: List[Dict],
        fps: float = 30.0,
    ) -> PS2SessionResult:
        rep_results = []
        scores = []

        for i, rep in enumerate(repetitions):
            start_f = rep.get("start_frame", 0)
            end_f = rep.get("end_frame", len(angle_data.get("left_knee", [])))

            rep_angle_slice = {
                joint: angle_data.get(joint, [])[start_f:end_f]
                for joint in ["left_knee", "right_knee", "left_hip", "right_hip", "left_ankle", "right_ankle"]
            }

            result = self.analyze_rep(rep_angle_slice, rep_id=rep.get("rep_id", i + 1), rep_number=i + 1, fps=fps)
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
                ps2_mode="mock",
            )

        # Update quality_trend based on score trajectory
        if len(scores) >= 3:
            first_half = np.mean(scores[:len(scores)//2])
            second_half = np.mean(scores[len(scores)//2:])
            if second_half > first_half + 0.05:
                trend = "improving"
            elif second_half < first_half - 0.05:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "stable"

        # Update each rep's quality_trend
        for r in rep_results:
            r.session.quality_trend = trend

        overall_score = round(float(np.mean(scores)), 2)

        # Compute dominant errors across session
        error_counts = {
            "insufficient_ROM": sum(r.error_flags.insufficient_ROM for r in rep_results),
            "too_fast": sum(r.error_flags.too_fast for r in rep_results),
            "too_slow": sum(r.error_flags.too_slow for r in rep_results),
            "knee_valgus": sum(r.error_flags.knee_valgus for r in rep_results),
            "asymmetric": sum(r.error_flags.asymmetric for r in rep_results),
            "trunk_comp": sum(r.error_flags.trunk_comp for r in rep_results),
        }
        dominant = [k for k, v in error_counts.items() if v > len(rep_results) * 0.4]

        recs = []
        if "insufficient_ROM" in dominant:
            recs.append("Try to bend your knee further during each repetition.")
        if "too_fast" in dominant:
            recs.append("Slow down — aim for a 3-second lowering phase.")
        if "knee_valgus" in dominant:
            recs.append("Keep your knee aligned over your second toe.")
        if "asymmetric" in dominant:
            recs.append("Focus on equal weight distribution between both legs.")
        if "trunk_comp" in dominant:
            recs.append("Keep your torso upright throughout the exercise.")
        if not recs:
            recs.append("Excellent form! Maintain this consistency.")

        return PS2SessionResult(
            session_id=session_id,
            total_reps_analyzed=len(rep_results),
            overall_session_score=overall_score,
            quality_trend=trend,
            rep_results=rep_results,
            dominant_errors=dominant,
            recommendations=recs,
            ps2_mode="mock",
        )
