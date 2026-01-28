"""
Interview session and state models for DataReady.io
"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from src.models.roles import Role, Experience, CloudPreference, Skill


class InterviewMode(str, Enum):
    """Interview mode options."""
    
    STRUCTURED = "structured"  # Fixed questions only
    STRUCTURED_FOLLOWUP = "structured_followup"  # Questions + follow-ups
    STRESS = "stress"  # Stress interview (future)


class InterviewState(str, Enum):
    """Interview state machine states."""
    
    # Pre-interview
    SETUP = "setup"  # User configuring interview
    READY = "ready"  # Ready to start
    
    # During interview
    ASKING = "asking"  # AI is asking a question
    LISTENING = "listening"  # Recording user response
    PROCESSING = "processing"  # Transcribing audio
    EVALUATING = "evaluating"  # AI evaluating response
    DECIDING = "deciding"  # Deciding next action
    
    # Post-interview
    COMPLETE = "complete"  # Interview finished
    GENERATING_REPORT = "generating_report"  # Creating report
    FINISHED = "finished"  # Report ready
    
    # Error states
    PAUSED = "paused"  # Temporarily paused
    ERROR = "error"  # Error occurred
    CANCELLED = "cancelled"  # User cancelled


class InterviewSetup(BaseModel):
    """User's interview configuration."""
    
    # Experience
    years_of_experience: int = Field(
        ..., ge=0, le=30,
        description="Years of experience in data engineering"
    )
    
    # Target role
    target_role: Role = Field(
        ...,
        description="Target role for the interview"
    )
    
    # Cloud preference
    cloud_preference: CloudPreference = Field(
        default=CloudPreference.AGNOSTIC,
        description="Preferred cloud platform for questions"
    )
    
    # Skills
    include_skills: list[str] = Field(
        default_factory=list,
        description="Skills to focus on (empty = all applicable)"
    )
    exclude_skills: list[str] = Field(
        default_factory=list,
        description="Skills to exclude from questioning"
    )
    
    # Interview mode
    mode: InterviewMode = Field(
        default=InterviewMode.STRUCTURED_FOLLOWUP,
        description="Interview mode"
    )
    
    # Optional settings
    max_questions: int = Field(
        default=10, ge=5, le=15,
        description="Maximum number of core questions"
    )


class QuestionResponse(BaseModel):
    """A question-response pair during the interview."""
    
    question_id: str
    question_text: str
    question_audio_url: str | None = None
    
    # Skill tracking
    skill_id: str | None = None
    
    # Expected answer points (for feedback generation)
    expected_points: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    
    # Timing
    asked_at: datetime
    response_started_at: datetime | None = None
    response_completed_at: datetime | None = None
    
    # Response
    response_audio_chunks: list[str] = Field(default_factory=list)
    response_transcript: str | None = None
    
    # Evaluation (hidden from user during interview)
    evaluation: dict[str, Any] | None = None
    
    # Follow-up tracking
    is_followup: bool = False
    parent_question_id: str | None = None
    followup_reason: str | None = None


class InterviewSession(BaseModel):
    """Complete interview session state."""
    
    # Identification
    session_id: str = Field(default_factory=lambda: str(uuid4()))
    
    # Setup
    setup: InterviewSetup
    
    # State
    state: InterviewState = Field(default=InterviewState.SETUP)
    
    # Timing
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    
    # Questions & Responses
    questions: list[QuestionResponse] = Field(default_factory=list)
    current_question_index: int = 0
    total_core_questions_asked: int = 0
    total_followups_asked: int = 0
    current_question_followups: int = 0  # Follow-ups for current core question
    
    # Question deduplication - track asked question texts (normalized)
    asked_question_hashes: set[str] = Field(default_factory=set)
    
    # Track which skills have already been targeted by questions
    asked_skills: set[str] = Field(default_factory=set)
    
    # Conversation context for current question thread
    current_question_context: list[dict[str, str]] = Field(
        default_factory=list,
        description="Conversation history for current question (for follow-ups/clarifications)"
    )
    
    # Difficulty tracking
    current_difficulty: int = Field(
        default=5, ge=1, le=10,
        description="Current difficulty level (1-10)"
    )
    difficulty_history: list[int] = Field(default_factory=list)
    
    # Performance tracking (internal)
    running_score: float = 0.0
    skill_scores: dict[str, list[float]] = Field(default_factory=dict)
    
    # Metadata
    error_message: str | None = None
    
    def get_current_question(self) -> QuestionResponse | None:
        """Get the current active question."""
        if self.questions and self.current_question_index < len(self.questions):
            return self.questions[self.current_question_index]
        return None
    
    def add_question(self, question: QuestionResponse) -> None:
        """Add a new question to the session."""
        self.questions.append(question)
        self.current_question_index = len(self.questions) - 1
        
        # Track for deduplication (normalize the question text)
        question_hash = self._normalize_question(question.question_text)
        self.asked_question_hashes.add(question_hash)
        
        # Track asked skill
        if question.skill_id:
            self.asked_skills.add(question.skill_id)
        
        if not question.is_followup:
            self.total_core_questions_asked += 1
            # Clear conversation context for new core question
            self.current_question_context = []
            # Reset per-question follow-up counter
            self.current_question_followups = 0
        else:
            self.total_followups_asked += 1
            self.current_question_followups += 1
        
        # Add to conversation context
        self.current_question_context.append({
            "role": "interviewer",
            "content": question.question_text
        })
    
    def add_response_to_context(self, response: str) -> None:
        """Add user response to current conversation context."""
        self.current_question_context.append({
            "role": "candidate",
            "content": response
        })
    
    def is_question_asked(self, question_text: str) -> bool:
        """Check if a similar question has already been asked."""
        question_hash = self._normalize_question(question_text)
        return question_hash in self.asked_question_hashes
    
    def is_skill_asked(self, skill_id: str) -> bool:
        """Check if a skill has already been targeted by a question."""
        return skill_id in self.asked_skills
    
    def get_asked_question_count(self) -> int:
        """Get total number of unique questions asked."""
        return len(self.asked_question_hashes)
    
    def _normalize_question(self, text: str) -> str:
        """Normalize question text for comparison using semantic hashing."""
        import re
        text = text.lower()
        text = re.sub(r'[^\w\s]', '', text)
        # Remove common filler words
        stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 
                      'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
                      'would', 'could', 'should', 'may', 'might', 'can', 'you',
                      'your', 'me', 'my', 'how', 'what', 'when', 'where', 'why',
                      'which', 'this', 'that', 'these', 'those', 'tell', 'explain',
                      'describe', 'about', 'give', 'example', 'walk', 'through'}
        words = [w for w in text.split() if w not in stop_words and len(w) > 2]
        # Use more words and don't sort (preserve order for better matching)
        return ' '.join(words[:15])
    
    def should_end_interview(self) -> bool:
        """Check if interview should end."""
        return (
            self.total_core_questions_asked >= self.setup.max_questions or
            self.state in [
                InterviewState.COMPLETE,
                InterviewState.CANCELLED,
                InterviewState.ERROR
            ]
        )
    
    def get_duration_seconds(self) -> float:
        """Get interview duration in seconds."""
        if not self.started_at:
            return 0.0
        end = self.completed_at or datetime.utcnow()
        return (end - self.started_at).total_seconds()
    
    def get_conversation_context_str(self) -> str:
        """Get current conversation context as a string for AI prompts."""
        if not self.current_question_context:
            return ""
        
        lines = []
        for entry in self.current_question_context:
            role = "Interviewer" if entry["role"] == "interviewer" else "Candidate"
            lines.append(f"{role}: {entry['content']}")
        return "\n".join(lines)


class InterviewContext(BaseModel):
    """Context passed to AI for decision making."""
    
    session: InterviewSession
    recent_responses: list[QuestionResponse] = Field(default_factory=list)
    skills_covered: list[str] = Field(default_factory=list)
    skills_remaining: list[str] = Field(default_factory=list)
    performance_trend: str = "stable"  # "improving", "declining", "stable"
    
    def to_prompt_context(self) -> str:
        """Convert context to a string for AI prompts."""
        return f"""
Interview Context:
- Role: {self.session.setup.target_role.display_name}
- Experience: {self.session.setup.years_of_experience} years
- Cloud: {self.session.setup.cloud_preference.value}
- Mode: {self.session.setup.mode.value}
- Questions Asked: {self.session.total_core_questions_asked}/{self.session.setup.max_questions}
- Follow-ups Asked: {self.session.total_followups_asked}
- Current Difficulty: {self.session.current_difficulty}/10
- Performance Trend: {self.performance_trend}
- Skills Covered: {', '.join(self.skills_covered) or 'None yet'}
- Skills Remaining: {', '.join(self.skills_remaining[:5])}...
"""
