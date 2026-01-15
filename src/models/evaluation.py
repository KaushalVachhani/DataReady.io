"""
Evaluation models for DataReady.io

Defines the rubric and scoring structures for evaluating candidate responses.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ScoreLevel(str, Enum):
    """Qualitative score levels."""
    
    EXCEPTIONAL = "exceptional"  # 9-10
    STRONG = "strong"           # 7-8
    ADEQUATE = "adequate"       # 5-6
    WEAK = "weak"               # 3-4
    POOR = "poor"               # 1-2


class ScoreBreakdown(BaseModel):
    """Detailed score breakdown for a response."""
    
    # Core dimensions (each 0-10)
    technical_correctness: float = Field(
        ..., ge=0, le=10,
        description="Accuracy of technical content"
    )
    depth_of_understanding: float = Field(
        ..., ge=0, le=10,
        description="How deeply the candidate understands the topic"
    )
    practical_experience: float = Field(
        ..., ge=0, le=10,
        description="Evidence of hands-on experience"
    )
    communication_clarity: float = Field(
        ..., ge=0, le=10,
        description="How clearly the answer was articulated"
    )
    confidence: float = Field(
        ..., ge=0, le=10,
        description="Confidence in delivery (not overconfidence)"
    )
    
    @property
    def overall_score(self) -> float:
        """Calculate weighted overall score."""
        weights = {
            "technical_correctness": 0.30,
            "depth_of_understanding": 0.25,
            "practical_experience": 0.20,
            "communication_clarity": 0.15,
            "confidence": 0.10,
        }
        return (
            self.technical_correctness * weights["technical_correctness"] +
            self.depth_of_understanding * weights["depth_of_understanding"] +
            self.practical_experience * weights["practical_experience"] +
            self.communication_clarity * weights["communication_clarity"] +
            self.confidence * weights["confidence"]
        )
    
    @property
    def level(self) -> ScoreLevel:
        """Get qualitative level from overall score."""
        score = self.overall_score
        if score >= 9:
            return ScoreLevel.EXCEPTIONAL
        elif score >= 7:
            return ScoreLevel.STRONG
        elif score >= 5:
            return ScoreLevel.ADEQUATE
        elif score >= 3:
            return ScoreLevel.WEAK
        else:
            return ScoreLevel.POOR


class EvaluationFeedback(BaseModel):
    """Qualitative feedback for a response."""
    
    what_went_well: list[str] = Field(
        default_factory=list,
        description="Positive aspects of the response"
    )
    what_was_missing: list[str] = Field(
        default_factory=list,
        description="Expected points that were not covered"
    )
    red_flags: list[str] = Field(
        default_factory=list,
        description="Concerning aspects of the response"
    )
    seniority_signals: list[str] = Field(
        default_factory=list,
        description="Indicators of experience level"
    )
    improvement_suggestions: list[str] = Field(
        default_factory=list,
        description="How to improve this answer"
    )


class ResponseEvaluation(BaseModel):
    """Complete evaluation of a single response."""
    
    # Reference
    question_id: str
    skill_id: str
    
    # Response data
    transcript: str
    response_duration_seconds: float
    
    # Scores
    scores: ScoreBreakdown
    
    # Feedback (hidden during interview)
    feedback: EvaluationFeedback
    
    # Follow-up decision
    needs_followup: bool = False
    followup_reason: str | None = None
    followup_type: str | None = None  # "probe", "clarify", "challenge"
    
    # Difficulty adjustment
    difficulty_delta: int = Field(
        default=0, ge=-2, le=2,
        description="How much to adjust difficulty after this response"
    )
    
    # Internal notes
    evaluator_notes: str | None = None


class SkillEvaluation(BaseModel):
    """Aggregated evaluation for a specific skill."""
    
    skill_id: str
    skill_name: str
    
    # Aggregated scores
    questions_asked: int
    average_score: float
    score_trend: str = "stable"  # "improving", "declining", "stable"
    
    # Summary feedback
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    
    # Individual question scores
    question_scores: list[float] = Field(default_factory=list)


class InterviewEvaluation(BaseModel):
    """Complete evaluation of the entire interview."""
    
    session_id: str
    
    # Overall
    overall_score: float = Field(..., ge=0, le=100)
    overall_level: ScoreLevel
    
    # Dimension averages
    avg_technical_correctness: float
    avg_depth_of_understanding: float
    avg_practical_experience: float
    avg_communication_clarity: float
    avg_confidence: float
    
    # By skill
    skill_evaluations: list[SkillEvaluation] = Field(default_factory=list)
    
    # Response evaluations
    response_evaluations: list[ResponseEvaluation] = Field(default_factory=list)
    
    # Summary
    total_questions: int
    total_followups: int
    interview_duration_seconds: float
    average_response_time_seconds: float
