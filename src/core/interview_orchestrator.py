"""
Interview Orchestrator - State machine for managing interview lifecycle.

This is the central coordinator for the entire interview process.
It manages state transitions, coordinates between components, and
ensures a smooth interview experience.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Callable, Awaitable
from uuid import uuid4

from src.models.interview import (
    InterviewSession,
    InterviewSetup,
    InterviewState,
    InterviewContext,
    QuestionResponse,
)
from src.models.question import Question, FollowUpDecision
from src.models.evaluation import ResponseEvaluation
from src.models.roles import get_skills_for_role, SKILL_CATALOG

logger = logging.getLogger(__name__)


class StateTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""
    pass


class InterviewOrchestrator:
    """
    Manages the interview lifecycle using a state machine pattern.
    
    States:
        SETUP → READY → ASKING → LISTENING → PROCESSING → EVALUATING → DECIDING
                                                                           ↓
                                                                   (ASKING | COMPLETE)
    
    The orchestrator coordinates between:
    - AI Reasoning Layer (question generation, evaluation)
    - Audio Processing (STT, TTS)
    - Session Storage
    """
    
    # Valid state transitions
    # Note: COMPLETE is allowed from most active states to support user-initiated ending
    VALID_TRANSITIONS: dict[InterviewState, list[InterviewState]] = {
        InterviewState.SETUP: [InterviewState.READY, InterviewState.CANCELLED],
        InterviewState.READY: [InterviewState.ASKING, InterviewState.CANCELLED, InterviewState.COMPLETE],
        InterviewState.ASKING: [InterviewState.LISTENING, InterviewState.PAUSED, InterviewState.ERROR, InterviewState.COMPLETE],
        InterviewState.LISTENING: [InterviewState.PROCESSING, InterviewState.PAUSED, InterviewState.ERROR, InterviewState.COMPLETE],
        InterviewState.PROCESSING: [InterviewState.EVALUATING, InterviewState.ERROR, InterviewState.COMPLETE],
        InterviewState.EVALUATING: [InterviewState.DECIDING, InterviewState.ERROR, InterviewState.COMPLETE],
        InterviewState.DECIDING: [InterviewState.ASKING, InterviewState.COMPLETE, InterviewState.ERROR],
        InterviewState.COMPLETE: [InterviewState.GENERATING_REPORT],
        InterviewState.GENERATING_REPORT: [InterviewState.FINISHED, InterviewState.ERROR],
        InterviewState.PAUSED: [InterviewState.ASKING, InterviewState.LISTENING, InterviewState.CANCELLED, InterviewState.COMPLETE],
        InterviewState.ERROR: [InterviewState.CANCELLED],
        InterviewState.FINISHED: [],  # Terminal state
        InterviewState.CANCELLED: [],  # Terminal state
    }
    
    def __init__(
        self,
        ai_reasoning: Any = None,  # AIReasoningLayer
        audio_processor: Any = None,  # AudioProcessor
        evaluation_engine: Any = None,  # EvaluationEngine
        report_generator: Any = None,  # ReportGenerator
    ):
        """
        Initialize the orchestrator with component dependencies.
        
        Args:
            ai_reasoning: AI reasoning layer for questions and evaluation
            audio_processor: Audio processing for STT/TTS
            evaluation_engine: Response evaluation engine
            report_generator: Report generation component
        """
        self.ai_reasoning = ai_reasoning
        self.audio_processor = audio_processor
        self.evaluation_engine = evaluation_engine
        self.report_generator = report_generator
        
        # Session storage (in-memory for now, Redis for production)
        self._sessions: dict[str, InterviewSession] = {}
        
        # Event callbacks
        self._state_change_callbacks: list[Callable[[str, InterviewState, InterviewState], Awaitable[None]]] = []
        self._question_callbacks: list[Callable[[str, Question], Awaitable[None]]] = []
        self._evaluation_callbacks: list[Callable[[str, ResponseEvaluation], Awaitable[None]]] = []
    
    # =========================================================================
    # SESSION MANAGEMENT
    # =========================================================================
    
    async def create_session(self, setup: InterviewSetup) -> InterviewSession:
        """
        Create a new interview session from setup configuration.
        
        Args:
            setup: User's interview configuration
            
        Returns:
            New InterviewSession instance
        """
        session = InterviewSession(setup=setup)
        
        # Determine skills to cover
        role_skills = get_skills_for_role(setup.target_role)
        skill_ids = [s.id for s in role_skills]
        
        # Apply include/exclude filters
        if setup.include_skills:
            skill_ids = [s for s in skill_ids if s in setup.include_skills]
        if setup.exclude_skills:
            skill_ids = [s for s in skill_ids if s not in setup.exclude_skills]
        
        # Initialize skill tracking
        session.skill_scores = {skill_id: [] for skill_id in skill_ids}
        
        # Set initial difficulty based on role
        difficulty_map = {
            "junior_data_engineer": 3,
            "mid_data_engineer": 5,
            "senior_data_engineer": 7,
            "staff_data_engineer": 8,
            "principal_data_engineer": 9,
        }
        session.current_difficulty = difficulty_map.get(setup.target_role.value, 5)
        
        # Store session
        self._sessions[session.session_id] = session
        
        logger.info(f"Created interview session: {session.session_id}")
        return session
    
    def get_session(self, session_id: str) -> InterviewSession | None:
        """Get a session by ID."""
        return self._sessions.get(session_id)
    
    async def update_session(self, session: InterviewSession) -> None:
        """Update a session in storage."""
        self._sessions[session.session_id] = session
    
    # =========================================================================
    # STATE MACHINE
    # =========================================================================
    
    async def transition_state(
        self,
        session_id: str,
        new_state: InterviewState,
        error_message: str | None = None
    ) -> InterviewSession:
        """
        Transition a session to a new state.
        
        Args:
            session_id: Session ID
            new_state: Target state
            error_message: Error message if transitioning to ERROR state
            
        Returns:
            Updated session
            
        Raises:
            StateTransitionError: If transition is invalid
        """
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")
        
        old_state = session.state
        
        # Validate transition
        valid_next_states = self.VALID_TRANSITIONS.get(old_state, [])
        if new_state not in valid_next_states:
            raise StateTransitionError(
                f"Invalid transition from {old_state} to {new_state}. "
                f"Valid transitions: {valid_next_states}"
            )
        
        # Update state
        session.state = new_state
        
        # Handle special state transitions
        if new_state == InterviewState.READY:
            session.started_at = datetime.utcnow()
        elif new_state == InterviewState.COMPLETE:
            session.completed_at = datetime.utcnow()
            # End Langfuse trace when interview completes (from any path)
            if self.ai_reasoning:
                self.ai_reasoning.end_interview_trace(
                    session_id=session_id,
                    metadata={
                        "questions_completed": len(session.questions),
                        "total_core_questions": session.total_core_questions_asked,
                        "total_followups": session.total_followups_asked,
                        "final_state": "complete",
                    }
                )
        elif new_state == InterviewState.ERROR:
            session.error_message = error_message
            # End Langfuse trace on error
            if self.ai_reasoning:
                self.ai_reasoning.end_interview_trace(
                    session_id=session_id,
                    metadata={"final_state": "error", "error": error_message}
                )
        
        # Save session
        await self.update_session(session)
        
        # Notify callbacks
        for callback in self._state_change_callbacks:
            try:
                await callback(session_id, old_state, new_state)
            except Exception as e:
                logger.error(f"State change callback error: {e}")
        
        logger.info(f"Session {session_id}: {old_state} → {new_state}")
        return session
    
    # =========================================================================
    # INTERVIEW FLOW
    # =========================================================================
    
    async def start_interview(self, session_id: str) -> dict[str, Any]:
        """
        Start the interview - transition to READY and ask first question.
        
        Returns:
            First question data
        """
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")
        
        # Start Langfuse trace for the entire interview
        if self.ai_reasoning:
            self.ai_reasoning.start_interview_trace(
                session_id=session_id,
                metadata={
                    "target_role": session.setup.target_role.value,
                    "cloud_preference": session.setup.cloud_preference.value,
                    "years_of_experience": session.setup.years_of_experience,
                    "mode": session.setup.mode.value,
                    "max_questions": session.setup.max_questions,
                }
            )
        
        # Transition to READY
        await self.transition_state(session_id, InterviewState.READY)
        
        # Generate and ask first question
        return await self.ask_next_question(session_id)
    
    async def ask_next_question(self, session_id: str) -> dict[str, Any]:
        """
        Generate and deliver the next question.
        
        Returns:
            Question data including text and audio
        """
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")
        
        # Check if interview should end
        if session.should_end_interview():
            await self.transition_state(session_id, InterviewState.COMPLETE)
            return {"action": "complete", "message": "Interview complete"}
        
        # Transition to ASKING
        await self.transition_state(session_id, InterviewState.ASKING)
        
        # Build context for AI
        context = self._build_context(session)
        
        # Generate question using AI
        if self.ai_reasoning:
            question = await self.ai_reasoning.generate_question(context)
        else:
            # Fallback for testing
            question = self._generate_mock_question(session)
        
        # Create question response record
        question_response = QuestionResponse(
            question_id=question.id,
            question_text=question.text,
            skill_id=question.skill_id,
            asked_at=datetime.utcnow(),
        )
        
        # Generate audio for question
        audio_data = None
        if self.audio_processor:
            audio_data = await self.audio_processor.text_to_speech(question.text)
            question_response.question_audio_url = audio_data.get("url")
        
        # Add to session
        session.add_question(question_response)
        await self.update_session(session)
        
        # Notify callbacks
        for callback in self._question_callbacks:
            try:
                await callback(session_id, question)
            except Exception as e:
                logger.error(f"Question callback error: {e}")
        
        # Transition to LISTENING
        await self.transition_state(session_id, InterviewState.LISTENING)
        
        return {
            "action": "question",
            "question_id": question.id,
            "question_text": question.text,
            "question_number": session.total_core_questions_asked,
            "total_questions": session.setup.max_questions,
            "difficulty": session.current_difficulty,
            "audio_data": audio_data,
        }
    
    async def submit_response(
        self,
        session_id: str,
        audio_data: bytes | None = None,
        transcript: str | None = None
    ) -> dict[str, Any]:
        """
        Process a user's response to the current question.
        
        Args:
            session_id: Session ID
            audio_data: Raw audio bytes (if not already transcribed)
            transcript: Pre-transcribed text (if available)
            
        Returns:
            Next action (follow-up, next question, or complete)
        """
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")
        
        current_question = session.get_current_question()
        if not current_question:
            raise ValueError("No active question")
        
        # Transition to PROCESSING
        await self.transition_state(session_id, InterviewState.PROCESSING)
        
        # Transcribe audio if needed
        if not transcript and audio_data:
            if self.audio_processor:
                transcript = await self.audio_processor.speech_to_text(audio_data)
            else:
                transcript = "[Transcription unavailable]"
        
        # Update question response
        current_question.response_transcript = transcript
        current_question.response_completed_at = datetime.utcnow()
        
        # Add response to conversation context for follow-up handling
        session.add_response_to_context(transcript or "")
        
        # Transition to EVALUATING
        await self.transition_state(session_id, InterviewState.EVALUATING)
        
        # Evaluate response
        if self.evaluation_engine:
            evaluation = await self.evaluation_engine.evaluate_response(
                question_id=current_question.question_id,
                transcript=transcript or "",
                context=self._build_context(session)
            )
        else:
            evaluation = self._generate_mock_evaluation(current_question, transcript)
        
        # Store evaluation (hidden from user)
        current_question.evaluation = evaluation.model_dump()
        
        # Update running scores
        self._update_running_scores(session, evaluation)
        
        await self.update_session(session)
        
        # Notify callbacks
        for callback in self._evaluation_callbacks:
            try:
                await callback(session_id, evaluation)
            except Exception as e:
                logger.error(f"Evaluation callback error: {e}")
        
        # Transition to DECIDING
        await self.transition_state(session_id, InterviewState.DECIDING)
        
        # Decide next action
        return await self._decide_next_action(session, evaluation)
    
    async def _decide_next_action(
        self,
        session: InterviewSession,
        evaluation: ResponseEvaluation
    ) -> dict[str, Any]:
        """
        Decide what to do after evaluating a response.
        
        Options:
        1. Ask follow-up question
        2. Ask next core question
        3. End interview
        """
        # Check if we need a follow-up
        if (
            evaluation.needs_followup and
            session.setup.mode.value == "structured_followup" and
            session.total_followups_asked < session.setup.max_questions * 2  # Max 2 follow-ups per question
        ):
            return await self._ask_followup(session, evaluation)
        
        # Adjust difficulty based on evaluation
        session.current_difficulty = max(1, min(10, 
            session.current_difficulty + evaluation.difficulty_delta
        ))
        session.difficulty_history.append(session.current_difficulty)
        await self.update_session(session)
        
        # Ask next question or end
        if session.should_end_interview():
            await self.transition_state(session.session_id, InterviewState.COMPLETE)
            return {"action": "complete", "message": "Interview complete"}
        
        return await self.ask_next_question(session.session_id)
    
    async def _ask_followup(
        self,
        session: InterviewSession,
        evaluation: ResponseEvaluation
    ) -> dict[str, Any]:
        """Generate and ask a follow-up question."""
        
        # Generate follow-up using AI
        if self.ai_reasoning:
            followup = await self.ai_reasoning.generate_followup(
                context=self._build_context(session),
                evaluation=evaluation
            )
        else:
            followup = self._generate_mock_followup(evaluation)
        
        # Create question response record
        current_question = session.get_current_question()
        
        # Validate the follow-up question text (avoid displaying JSON or malformed text)
        followup_text = followup.followup_question or "Can you elaborate on that?"
        if followup_text.strip().startswith("{") or followup_text.strip().startswith("["):
            logger.warning("Follow-up question looks like JSON, using fallback")
            followup_text = "Can you provide a specific example from your experience?"
        
        followup_response = QuestionResponse(
            question_id=f"{current_question.question_id}_followup_{session.total_followups_asked + 1}",
            question_text=followup_text,
            skill_id=current_question.skill_id,  # Inherit from parent question
            asked_at=datetime.utcnow(),
            is_followup=True,
            parent_question_id=current_question.question_id,
            followup_reason=followup.reason,
        )
        
        # Generate audio
        audio_data = None
        if self.audio_processor:
            audio_data = await self.audio_processor.text_to_speech(followup_response.question_text)
            followup_response.question_audio_url = audio_data.get("url")
        
        # Add to session
        session.add_question(followup_response)
        await self.update_session(session)
        
        # Transition states
        await self.transition_state(session.session_id, InterviewState.ASKING)
        await self.transition_state(session.session_id, InterviewState.LISTENING)
        
        return {
            "action": "followup",
            "question_id": followup_response.question_id,
            "question_text": followup_response.question_text,
            "followup_reason": followup.reason,
            "audio_data": audio_data,
        }
    
    async def end_interview(self, session_id: str, reason: str = "user_ended") -> dict[str, Any]:
        """
        End the interview early.
        
        Args:
            session_id: Session ID
            reason: Reason for ending
            
        Returns:
            Completion status
        """
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")
        
        session.completed_at = datetime.utcnow()
        await self.update_session(session)
        
        # Trace is ended automatically in transition_state when moving to COMPLETE
        await self.transition_state(session_id, InterviewState.COMPLETE)
        
        return {
            "action": "ended",
            "reason": reason,
            "questions_completed": len(session.questions),
        }
    
    async def generate_report(self, session_id: str) -> dict[str, Any]:
        """
        Generate the final interview report.
        
        Returns:
            Complete interview report
        """
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")
        
        if session.state not in [InterviewState.COMPLETE, InterviewState.GENERATING_REPORT]:
            raise ValueError("Interview must be complete to generate report")
        
        await self.transition_state(session_id, InterviewState.GENERATING_REPORT)
        
        if self.report_generator:
            report = await self.report_generator.generate(session)
        else:
            report = self._generate_mock_report(session)
        
        await self.transition_state(session_id, InterviewState.FINISHED)
        
        return report.model_dump()
    
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    def _build_context(self, session: InterviewSession) -> InterviewContext:
        """Build context for AI operations."""
        # Get covered skills (either asked or has scores)
        # Use asked_skills for immediate tracking, skill_scores for evaluated tracking
        skills_covered = list(
            session.asked_skills | 
            {skill_id for skill_id, scores in session.skill_scores.items() if scores}
        )
        
        # Skills remaining = all skills minus covered
        skills_remaining = [
            skill_id for skill_id in session.skill_scores.keys()
            if skill_id not in skills_covered
        ]
        
        # Calculate performance trend
        if len(session.difficulty_history) >= 3:
            recent = session.difficulty_history[-3:]
            if recent[-1] > recent[0]:
                trend = "improving"
            elif recent[-1] < recent[0]:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "stable"
        
        return InterviewContext(
            session=session,
            recent_responses=session.questions[-3:] if session.questions else [],
            skills_covered=skills_covered,
            skills_remaining=skills_remaining,
            performance_trend=trend,
        )
    
    def _update_running_scores(
        self,
        session: InterviewSession,
        evaluation: ResponseEvaluation
    ) -> None:
        """Update running scores after evaluation."""
        # Add score to skill tracking
        if evaluation.skill_id in session.skill_scores:
            session.skill_scores[evaluation.skill_id].append(
                evaluation.scores.overall_score
            )
        
        # Update running average
        all_scores = [
            score
            for scores in session.skill_scores.values()
            for score in scores
        ]
        if all_scores:
            session.running_score = sum(all_scores) / len(all_scores)
    
    # =========================================================================
    # MOCK METHODS (for testing without AI integration)
    # =========================================================================
    
    def _generate_mock_question(self, session: InterviewSession) -> Question:
        """Generate a mock question for testing, avoiding duplicates."""
        from src.models.question import Question, QuestionCategory, QuestionDifficulty, QuestionType
        import random
        
        # Larger pool of questions organized by category
        question_pool = [
            # SQL
            ("How would you optimize a complex SQL query that's running slowly on a large dataset?", QuestionCategory.SQL, "sql_optimization_basics"),
            ("Explain window functions and provide an example of when you'd use them.", QuestionCategory.SQL, "sql_window_functions"),
            ("How do you handle NULL values in SQL aggregations?", QuestionCategory.SQL, "sql_aggregations"),
            
            # ETL
            ("Design an ETL pipeline for processing 10 million records daily.", QuestionCategory.ETL, "etl_pipeline_design"),
            ("What's your approach to handling schema changes in a production pipeline?", QuestionCategory.ETL, "schema_evolution"),
            ("How would you implement idempotent data loading?", QuestionCategory.ETL, "incremental_loads"),
            
            # Spark
            ("How would you optimize a slow-running Spark job?", QuestionCategory.SPARK, "spark_tuning"),
            ("Explain how Spark handles data partitioning and why it matters.", QuestionCategory.SPARK, "spark_partitioning"),
            ("What strategies do you use for handling data skew in Spark?", QuestionCategory.SPARK, "data_skew_handling"),
            
            # System Design
            ("Design a real-time analytics system for an e-commerce platform.", QuestionCategory.SYSTEM_DESIGN, "data_platform_design"),
            ("How would you architect a data platform that scales from 100GB to 10TB daily?", QuestionCategory.SYSTEM_DESIGN, "data_platform_design"),
            ("What are the key considerations when choosing between batch and streaming?", QuestionCategory.SYSTEM_DESIGN, "stream_processing"),
            
            # Distributed Systems
            ("Explain the CAP theorem and how it applies to data systems.", QuestionCategory.DISTRIBUTED, "cap_theorem"),
            ("How do you ensure data consistency in an event-driven architecture?", QuestionCategory.DISTRIBUTED, "distributed_computing"),
            ("Describe strategies for handling failures in distributed pipelines.", QuestionCategory.DISTRIBUTED, "distributed_computing"),
            
            # Data Quality
            ("Describe your approach to data quality validation in production.", QuestionCategory.DATA_MODELING, "data_quality_concepts"),
            ("How would you implement data lineage tracking?", QuestionCategory.OBSERVABILITY, "lineage_tracking"),
            
            # Cloud
            ("What factors do you consider when optimizing cloud costs for data workloads?", QuestionCategory.CLOUD, "cloud_cost_optimization"),
            ("Compare data lakes and data warehouses - when would you use each?", QuestionCategory.CLOUD, "cloud_data_services"),
            
            # Orchestration
            ("How do you design reliable DAGs in Airflow?", QuestionCategory.ORCHESTRATION, "dag_design"),
            ("What's your approach to monitoring and alerting for data pipelines?", QuestionCategory.OBSERVABILITY, "pipeline_monitoring"),
        ]
        
        # Find questions not yet asked
        available_questions = []
        for q_text, category, skill_id in question_pool:
            if not session.is_question_asked(q_text):
                available_questions.append((q_text, category, skill_id))
        
        # If all questions used, pick any (shouldn't happen with 20+ questions)
        if not available_questions:
            available_questions = question_pool
        
        # Pick a random question from available
        q_text, category, skill_id = random.choice(available_questions)
        
        return Question(
            id=f"q_{uuid4().hex[:8]}",
            text=q_text,
            category=category,
            skill_id=skill_id,
            question_type=QuestionType.SCENARIO,
            difficulty=QuestionDifficulty.MEDIUM,
            difficulty_score=session.current_difficulty,
            target_roles=[session.setup.target_role],
            expected_points=["Clear explanation", "Practical considerations", "Trade-offs"],
        )
    
    def _generate_mock_evaluation(
        self,
        question: QuestionResponse,
        transcript: str | None
    ) -> ResponseEvaluation:
        """Generate a mock evaluation for testing."""
        from src.models.evaluation import (
            ResponseEvaluation,
            ScoreBreakdown,
            EvaluationFeedback,
        )
        
        # Simple scoring based on response length
        length = len(transcript or "")
        base_score = min(8, max(3, length / 100))
        
        return ResponseEvaluation(
            question_id=question.question_id,
            skill_id="data_platform_design",
            transcript=transcript or "",
            response_duration_seconds=30.0,
            scores=ScoreBreakdown(
                technical_correctness=base_score,
                depth_of_understanding=base_score - 0.5,
                practical_experience=base_score - 1,
                communication_clarity=base_score + 0.5,
                confidence=base_score,
            ),
            feedback=EvaluationFeedback(
                what_went_well=["Clear communication"],
                what_was_missing=["Could elaborate more on trade-offs"],
                red_flags=[],
                seniority_signals=["Shows practical experience"],
            ),
            needs_followup=base_score < 6,
            followup_reason="Response could use more depth" if base_score < 6 else None,
            difficulty_delta=1 if base_score > 7 else (-1 if base_score < 4 else 0),
        )
    
    def _generate_mock_followup(self, evaluation: ResponseEvaluation) -> FollowUpDecision:
        """Generate a mock follow-up decision for testing."""
        return FollowUpDecision(
            should_followup=True,
            reason=evaluation.followup_reason or "Need more depth",
            followup_type="probe",
            followup_question="Can you provide a specific example from your experience?",
            difficulty_adjustment=0,
        )
    
    def _generate_mock_report(self, session: InterviewSession):
        """Generate a mock report for testing."""
        from src.models.report import (
            InterviewReport,
            HiringVerdict,
            RoleReadiness,
            SkillScore,
            ImprovementSuggestion,
        )
        
        return InterviewReport(
            session_id=session.session_id,
            target_role=session.setup.target_role,
            years_of_experience=session.setup.years_of_experience,
            interview_duration_minutes=session.get_duration_seconds() / 60,
            overall_score=session.running_score * 10,
            overall_score_interpretation="Good performance with room for improvement",
            dimension_scores={
                "Technical Correctness": 7.5,
                "Depth of Understanding": 7.0,
                "Practical Experience": 6.5,
                "Communication": 8.0,
                "Confidence": 7.5,
            },
            hiring_verdict=HiringVerdict.HIRE,
            role_readiness=RoleReadiness.ALMOST_READY,
            role_readiness_explanation="Shows solid fundamentals with some gaps in advanced topics.",
            top_strengths=["Clear communication", "Good practical examples"],
            areas_for_improvement=["Deeper understanding of distributed systems"],
            missed_concepts=["CAP theorem nuances"],
            communication_feedback="Communicates clearly and concisely.",
        )
    
    # =========================================================================
    # EVENT CALLBACKS
    # =========================================================================
    
    def on_state_change(
        self,
        callback: Callable[[str, InterviewState, InterviewState], Awaitable[None]]
    ) -> None:
        """Register a callback for state changes."""
        self._state_change_callbacks.append(callback)
    
    def on_question(
        self,
        callback: Callable[[str, Question], Awaitable[None]]
    ) -> None:
        """Register a callback for new questions."""
        self._question_callbacks.append(callback)
    
    def on_evaluation(
        self,
        callback: Callable[[str, ResponseEvaluation], Awaitable[None]]
    ) -> None:
        """Register a callback for evaluations."""
        self._evaluation_callbacks.append(callback)
