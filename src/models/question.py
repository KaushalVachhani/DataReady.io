"""
Question models for DataReady.io
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from src.models.roles import Role, SkillCategory


class QuestionDifficulty(str, Enum):
    """Question difficulty levels."""
    
    EASY = "easy"        # 1-3
    MEDIUM = "medium"    # 4-6
    HARD = "hard"        # 7-8
    EXPERT = "expert"    # 9-10


class QuestionType(str, Enum):
    """Types of interview questions."""
    
    CONCEPTUAL = "conceptual"          # What is X?
    SCENARIO = "scenario"              # How would you handle X?
    DESIGN = "design"                  # Design a system for X
    TROUBLESHOOTING = "troubleshooting" # Debug this issue
    BEHAVIORAL = "behavioral"          # Tell me about a time...
    TRADEOFF = "tradeoff"              # Compare X vs Y


class QuestionCategory(str, Enum):
    """High-level question categories."""
    
    SQL = "sql"
    PYTHON = "python"
    ETL = "etl"
    SPARK = "spark"
    STREAMING = "streaming"
    CLOUD = "cloud"
    ORCHESTRATION = "orchestration"
    DATA_MODELING = "data_modeling"
    SYSTEM_DESIGN = "system_design"
    DISTRIBUTED = "distributed"
    PERFORMANCE = "performance"
    GOVERNANCE = "governance"
    OBSERVABILITY = "observability"


class Question(BaseModel):
    """A single interview question."""
    
    # Identification
    id: str = Field(..., description="Unique question ID")
    
    # Content
    text: str = Field(..., description="The question text")
    context: str | None = Field(
        default=None,
        description="Additional context for the question"
    )
    
    # Classification
    category: QuestionCategory = Field(..., description="Question category")
    skill_id: str = Field(..., description="Target skill being tested")
    question_type: QuestionType = Field(
        default=QuestionType.CONCEPTUAL,
        description="Type of question"
    )
    
    # Difficulty
    difficulty: QuestionDifficulty = Field(..., description="Difficulty level")
    difficulty_score: int = Field(
        ..., ge=1, le=10,
        description="Numeric difficulty (1-10)"
    )
    
    # Role targeting
    target_roles: list[Role] = Field(
        default_factory=list,
        description="Roles this question is appropriate for"
    )
    
    # Evaluation guidance
    expected_points: list[str] = Field(
        default_factory=list,
        description="Key points expected in a good answer"
    )
    red_flags: list[str] = Field(
        default_factory=list,
        description="Warning signs in an answer"
    )
    seniority_signals: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Signals of different seniority levels"
    )
    
    # Follow-up options
    followup_triggers: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Conditions that trigger follow-ups"
    )
    
    # Metadata
    is_generated: bool = Field(
        default=True,
        description="Whether AI generated this question"
    )
    source: str | None = Field(
        default=None,
        description="Source if from question bank"
    )


class FollowUpDecision(BaseModel):
    """Decision about whether to ask a follow-up."""
    
    should_followup: bool
    reason: str
    followup_type: str | None = None  # "probe", "clarify", "challenge", "example"
    followup_question: str | None = None
    difficulty_adjustment: int = 0  # -2 to +2


class GeneratedQuestion(BaseModel):
    """AI-generated question with metadata."""
    
    question: Question
    generation_reasoning: str
    alternative_phrasings: list[str] = Field(default_factory=list)
    estimated_response_time_seconds: int = 60
