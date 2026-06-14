"""
PS2 Exercise Analysis Service Factory
Auto-selects mock or real analyzer based on PS2_MODEL_PATH env var.
"""
from backend_config import settings
from .base_analyzer import BaseExerciseAnalyzer
from .mock_analyzer import MockExerciseAnalyzer
from .model_analyzer import ModelExerciseAnalyzer
from loguru import logger

_analyzer: BaseExerciseAnalyzer | None = None


def get_analyzer() -> BaseExerciseAnalyzer:
    """Return the active PS2 analyzer (mock or real)."""
    global _analyzer
    if _analyzer is None:
        if settings.PS2_USE_REAL_MODEL and settings.PS2_MODEL_PATH:
            model_analyzer = ModelExerciseAnalyzer()
            resolved_path = settings.get_ps2_model_path()
            model_analyzer.load_model(resolved_path)
            if getattr(model_analyzer, "_loaded", False):
                _analyzer = model_analyzer
            else:
                logger.warning("PS2 model unavailable after load attempt; falling back to mock analyzer.")
                _analyzer = MockExerciseAnalyzer()
        else:
            _analyzer = MockExerciseAnalyzer()
    return _analyzer


__all__ = ["get_analyzer", "BaseExerciseAnalyzer", "MockExerciseAnalyzer", "ModelExerciseAnalyzer"]
