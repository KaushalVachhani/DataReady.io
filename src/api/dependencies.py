"""
API Dependencies

Provides dependency injection for API endpoints.
Manages singleton instances of core components.
"""

from functools import lru_cache

from src.core.interview_orchestrator import InterviewOrchestrator
from src.core.ai_reasoning import AIReasoningLayer
from src.core.audio_processor import AudioProcessor
from src.core.evaluation_engine import EvaluationEngine
from src.core.report_generator import ReportGenerator


# ============================================================================
# SINGLETON INSTANCES
# ============================================================================

_orchestrator: InterviewOrchestrator | None = None
_audio_processor: AudioProcessor | None = None


def get_orchestrator() -> InterviewOrchestrator:
    """
    Get the interview orchestrator singleton.
    
    Lazily initializes all required components.
    """
    global _orchestrator
    
    if _orchestrator is None:
        # Initialize components
        try:
            ai_reasoning = AIReasoningLayer()
        except Exception:
            # AI reasoning is optional for testing
            ai_reasoning = None
        
        try:
            audio_processor = AudioProcessor()
        except Exception:
            audio_processor = None
        
        evaluation_engine = EvaluationEngine(ai_reasoning)
        report_generator = ReportGenerator(ai_reasoning)
        
        _orchestrator = InterviewOrchestrator(
            ai_reasoning=ai_reasoning,
            audio_processor=audio_processor,
            evaluation_engine=evaluation_engine,
            report_generator=report_generator,
        )
    
    return _orchestrator


def get_audio_processor() -> AudioProcessor:
    """Get the audio processor singleton."""
    global _audio_processor
    
    if _audio_processor is None:
        _audio_processor = AudioProcessor()
    
    return _audio_processor


async def cleanup():
    """Cleanup resources on shutdown."""
    global _orchestrator, _audio_processor
    
    if _audio_processor:
        await _audio_processor.close()
        _audio_processor = None
    
    if _orchestrator and _orchestrator.ai_reasoning:
        await _orchestrator.ai_reasoning.close()
    
    _orchestrator = None
