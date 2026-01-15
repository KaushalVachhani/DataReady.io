"""
Report models for DataReady.io

Defines the structure of the final interview report card.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from src.models.roles import Role


class HiringVerdict(str, Enum):
    """Final hiring recommendation."""
    
    STRONG_HIRE = "strong_hire"
    HIRE = "hire"
    BORDERLINE = "borderline"
    NEEDS_IMPROVEMENT = "needs_improvement"
    
    @property
    def display_text(self) -> str:
        """Human-readable verdict."""
        texts = {
            "strong_hire": "Strong Hire",
            "hire": "Hire",
            "borderline": "Borderline",
            "needs_improvement": "Needs Improvement",
        }
        return texts.get(self.value, self.value)
    
    @property
    def description(self) -> str:
        """Verdict description."""
        descriptions = {
            "strong_hire": "Demonstrates exceptional skill and would be a strong addition to any team.",
            "hire": "Shows solid competence and would perform well in the role.",
            "borderline": "Has potential but may need additional support or training.",
            "needs_improvement": "Requires significant development before being ready for this role.",
        }
        return descriptions.get(self.value, "")


class RoleReadiness(str, Enum):
    """Readiness for the target role."""
    
    READY = "ready"
    ALMOST_READY = "almost_ready"
    NEEDS_WORK = "needs_work"
    NOT_READY = "not_ready"


class SkillScore(BaseModel):
    """Score for a specific skill category."""
    
    skill_id: str
    skill_name: str
    category: str
    
    # Scores
    score: float = Field(..., ge=0, le=10)
    max_score: float = 10.0
    
    # Details
    questions_asked: int
    questions_answered_well: int
    
    # Feedback
    summary: str
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)


class ImprovementSuggestion(BaseModel):
    """A specific improvement suggestion."""
    
    area: str
    priority: str  # "high", "medium", "low"
    suggestion: str
    resources: list[str] = Field(default_factory=list)
    estimated_time: str = ""  # "2-4 weeks"


class StudyRoadmap(BaseModel):
    """Personalized study roadmap."""
    
    timeframe: str  # "30 days", "60 days", etc.
    
    # Weekly breakdown
    weeks: list[dict[str, Any]] = Field(default_factory=list)
    
    # Resources
    recommended_resources: list[dict[str, str]] = Field(default_factory=list)
    
    # Practice suggestions
    practice_suggestions: list[str] = Field(default_factory=list)


class InterviewReport(BaseModel):
    """Complete interview report card."""
    
    # Metadata
    session_id: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Candidate info (from setup)
    target_role: Role
    years_of_experience: int
    interview_duration_minutes: float
    
    # === SCORES ===
    
    # Overall
    overall_score: float = Field(..., ge=0, le=100)
    overall_score_interpretation: str
    
    # Dimension scores (for radar chart)
    dimension_scores: dict[str, float] = Field(
        default_factory=dict,
        description="Scores for each evaluation dimension"
    )
    
    # Skill scores (for breakdown)
    skill_scores: list[SkillScore] = Field(default_factory=list)
    
    # === VERDICTS ===
    
    hiring_verdict: HiringVerdict
    role_readiness: RoleReadiness
    role_readiness_explanation: str
    
    # === QUALITATIVE FEEDBACK ===
    
    # Strengths
    top_strengths: list[str] = Field(
        default_factory=list,
        description="Top 3-5 strengths demonstrated"
    )
    
    # Weaknesses
    areas_for_improvement: list[str] = Field(
        default_factory=list,
        description="Top 3-5 areas needing improvement"
    )
    
    # Missed concepts
    missed_concepts: list[str] = Field(
        default_factory=list,
        description="Important concepts the candidate missed"
    )
    
    # Communication feedback
    communication_feedback: str = ""
    
    # === RECOMMENDATIONS ===
    
    # Improvement suggestions
    improvement_suggestions: list[ImprovementSuggestion] = Field(
        default_factory=list
    )
    
    # Study roadmap
    study_roadmap: StudyRoadmap | None = None
    
    # === DETAILED BREAKDOWN ===
    
    # Per-question feedback (optional, detailed view)
    question_feedback: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Detailed feedback for each question"
    )
    
    # Performance timeline
    performance_timeline: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Score progression throughout interview"
    )
    
    # === AI INSIGHTS ===
    
    interviewer_notes: str = ""
    standout_moments: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)


class ReportSummary(BaseModel):
    """Condensed report for quick view."""
    
    session_id: str
    overall_score: float
    hiring_verdict: HiringVerdict
    role_readiness: RoleReadiness
    top_strength: str
    top_improvement_area: str
    interview_duration_minutes: float
