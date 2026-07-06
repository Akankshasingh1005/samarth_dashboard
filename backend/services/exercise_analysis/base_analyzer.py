"""
Abstract base class that all PS2 analyzers must implement.
Your teammate implements ModelExerciseAnalyzer in model_analyzer.py,
then sets PS2_MODEL_PATH in .env - the system auto-switches.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from .schemas import PS2RepResult, PS2SessionResult


class BaseExerciseAnalyzer(ABC):
    """
    Interface contract for all exercise analyzers (mock and real PS2 model).
    
    To integrate your PS2 model:
    1. Create ModelExerciseAnalyzer in model_analyzer.py
    2. Implement all abstract methods below
    3. Set PS2_MODEL_PATH=<path_to_weights> in .env
    4. System auto-switches - no other changes needed
    """

    @abstractmethod
    def load_model(self, model_path: str) -> None:
        """
        Load trained model weights from disk.
        Called once at application startup when PS2_MODEL_PATH is set.
        
        Args:
            model_path: Absolute path to model weights file
        """
        ...

    @abstractmethod
    def analyze_rep(
        self,
        angle_data: Dict,
        rep_id: int,
        rep_number: int = 1,
        fps: float = 30.0,
    ) -> PS2RepResult:
        """
        Analyze a single repetition from angle time-series data.
        
        Args:
            angle_data: Dict with keys: left_knee, right_knee, left_hip, 
                        right_hip, left_ankle, right_ankle (all List[float])
            rep_id: Unique rep identifier
            rep_number: Rep sequence number in session
            fps: Video FPS for timing calculations
            
        Returns:
            PS2RepResult matching exact PS2 JSON schema
        """
        ...

    @abstractmethod
    def analyze_session(
        self,
        session_id: str,
        angle_data: Dict,
        repetitions: List[Dict],
        fps: float = 30.0,
    ) -> PS2SessionResult:
        """
        Analyze a complete session of repetitions.
        
        Args:
            session_id: Database session ID string
            angle_data: Full session time-series dict
            repetitions: List of rep dicts from PS1 (with start_frame, end_frame, etc.)
            fps: Video FPS
            
        Returns:
            PS2SessionResult with all rep results + session-level metrics
        """
        ...
