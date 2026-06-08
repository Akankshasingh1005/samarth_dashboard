"""
PS2 Exercise Analysis Service Factory
Auto-selects mock or real analyzer based on PS2_MODEL_PATH env var.
"""
from config import settings
from .base_analyzer import BaseExerciseAnalyzer
from .mock_analyzer import MockExerciseAnalyzer
from .model_analyzer import ModelExerciseAnalyzer

_analyzer: BaseExerciseAnalyzer | None = None


def get_analyzer() -> BaseExerciseAnalyzer:
    """Return the active PS2 analyzer (mock or real)."""
    global _analyzer
    if _analyzer is None:
        if settings.PS2_USE_REAL_MODEL and settings.PS2_MODEL_PATH:
            _analyzer = ModelExerciseAnalyzer()
            _analyzer.load_model(settings.PS2_MODEL_PATH)
        else:
            _analyzer = MockExerciseAnalyzer()
    return _analyzer


__all__ = ["get_analyzer", "BaseExerciseAnalyzer", "MockExerciseAnalyzer", "ModelExerciseAnalyzer"]
