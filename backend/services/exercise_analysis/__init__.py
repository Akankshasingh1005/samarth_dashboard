"""PS2 Exercise Analysis Service Factory."""
from backend_config import settings
from .base_analyzer import BaseExerciseAnalyzer
from .model_analyzer import ModelExerciseAnalyzer
from loguru import logger

_analyzer: BaseExerciseAnalyzer | None = None


def get_analyzer() -> BaseExerciseAnalyzer:
    """Return the active real PS2 analyzer."""
    global _analyzer
    if _analyzer is None:
        if not settings.PS2_USE_REAL_MODEL or not settings.PS2_MODEL_PATH:
            raise RuntimeError("PS2 real model is not configured. Set PS2_MODEL_PATH and PS2_USE_REAL_MODEL=true.")

        model_analyzer = ModelExerciseAnalyzer()
        resolved_path = settings.get_ps2_model_path()
        model_analyzer.load_model(resolved_path)
        if not getattr(model_analyzer, "_loaded", False):
            logger.error("PS2 model unavailable after load attempt.")
            raise RuntimeError(f"PS2 real model could not be loaded from {resolved_path}.")
        _analyzer = model_analyzer
    return _analyzer


__all__ = ["get_analyzer", "BaseExerciseAnalyzer", "ModelExerciseAnalyzer"]
