"""
Evaluation Engine for DataReady.io

Handles scoring and feedback generation for candidate responses.
Works in conjunction with AI Reasoning Layer for detailed evaluation.
"""

import logging
from typing import Any

from src.models.interview import InterviewContext, InterviewSession
from src.models.question import Question
from src.models.evaluation import (
    ResponseEvaluation,
    ScoreBreakdown,
    EvaluationFeedback,
    SkillEvaluation,
    InterviewEvaluation,
    ScoreLevel,
)
from src.models.roles import SKILL_CATALOG

logger = logging.getLogger(__name__)


class EvaluationEngine:
    """
    Central evaluation component for interview responses.
    
    Responsibilities:
    - Score individual responses
    - Aggregate scores by skill
    - Generate feedback
    - Calculate overall performance
    """
    
    def __init__(self, ai_reasoning: Any = None):
        """
        Initialize evaluation engine.
        
        Args:
            ai_reasoning: AI reasoning layer for detailed evaluation
        """
        self.ai_reasoning = ai_reasoning
    
    # =========================================================================
    # RESPONSE EVALUATION
    # =========================================================================
    
    async def evaluate_response(
        self,
        question_id: str,
        transcript: str,
        context: InterviewContext,
        question: Question | None = None
    ) -> ResponseEvaluation:
        """
        Evaluate a single response.
        
        If AI reasoning is available, uses it for detailed evaluation.
        Otherwise, uses heuristic-based evaluation.
        
        Args:
            question_id: ID of the question
            transcript: Transcribed response
            context: Current interview context
            question: Question object (if available)
            
        Returns:
            Complete ResponseEvaluation
        """
        if self.ai_reasoning and question:
            return await self.ai_reasoning.evaluate_response(
                question=question,
                transcript=transcript,
                context=context
            )
        
        # Fallback to heuristic evaluation
        return self._heuristic_evaluation(question_id, transcript, context)
    
    def _heuristic_evaluation(
        self,
        question_id: str,
        transcript: str,
        context: InterviewContext
    ) -> ResponseEvaluation:
        """
        Heuristic-based evaluation when AI is not available.
        
        Uses text analysis to generate approximate scores.
        """
        # Analyze response
        analysis = self._analyze_response(transcript)
        
        # Calculate scores based on analysis
        scores = ScoreBreakdown(
            technical_correctness=analysis["technical_score"],
            depth_of_understanding=analysis["depth_score"],
            practical_experience=analysis["practical_score"],
            communication_clarity=analysis["clarity_score"],
            confidence=analysis["confidence_score"],
        )
        
        # Generate feedback
        feedback = self._generate_heuristic_feedback(analysis)
        
        # Determine if follow-up is needed
        needs_followup = scores.overall_score < 6.0
        
        return ResponseEvaluation(
            question_id=question_id,
            skill_id=context.skills_remaining[0] if context.skills_remaining else "general",
            transcript=transcript,
            response_duration_seconds=analysis["estimated_duration"],
            scores=scores,
            feedback=feedback,
            needs_followup=needs_followup,
            followup_reason="Response could use more depth" if needs_followup else None,
            difficulty_delta=self._calculate_difficulty_delta(scores.overall_score),
        )
    
    def _analyze_response(self, transcript: str) -> dict[str, Any]:
        """Analyze response text for scoring signals."""
        words = transcript.split()
        word_count = len(words)
        sentence_count = transcript.count(".") + transcript.count("?") + transcript.count("!")
        
        # Technical keywords
        technical_keywords = [
            "architecture", "system", "design", "pipeline", "data",
            "performance", "scalability", "distributed", "consistency",
            "availability", "latency", "throughput", "batch", "streaming",
            "partition", "replication", "fault-tolerant", "redundancy",
            "optimization", "index", "query", "transformation", "etl",
            "spark", "kafka", "airflow", "sql", "python", "cloud",
        ]
        
        # Experience keywords
        experience_keywords = [
            "experience", "worked", "implemented", "built", "designed",
            "led", "managed", "optimized", "improved", "solved",
            "production", "deployed", "migrated", "scaled",
        ]
        
        # Structure keywords
        structure_keywords = [
            "first", "second", "third", "finally", "additionally",
            "however", "therefore", "because", "in my experience",
            "for example", "specifically", "in conclusion",
        ]
        
        # Count keywords
        tech_count = sum(1 for w in words if w.lower() in technical_keywords)
        exp_count = sum(1 for kw in experience_keywords if kw.lower() in transcript.lower())
        struct_count = sum(1 for kw in structure_keywords if kw.lower() in transcript.lower())
        
        # Calculate scores
        # Length-based base score (optimal: 100-300 words)
        if word_count < 30:
            length_score = 3.0
        elif word_count < 50:
            length_score = 4.0
        elif word_count < 100:
            length_score = 5.0
        elif word_count < 200:
            length_score = 6.5
        elif word_count < 300:
            length_score = 7.0
        elif word_count < 500:
            length_score = 6.5
        else:
            length_score = 5.5  # Too verbose
        
        # Technical depth score
        tech_ratio = tech_count / max(word_count, 1) * 100
        if tech_ratio > 5:
            tech_score = min(9.0, 6.0 + tech_ratio / 2)
        else:
            tech_score = max(3.0, 5.0 + tech_ratio)
        
        # Practical experience score
        practical_score = min(8.0, 4.0 + exp_count * 0.8)
        
        # Clarity score (based on structure)
        clarity_score = min(8.0, 5.0 + struct_count * 0.5 + min(sentence_count / 3, 2))
        
        # Confidence score (based on assertive language)
        hedging_words = ["maybe", "perhaps", "might", "possibly", "i think", "i guess"]
        hedge_count = sum(1 for hw in hedging_words if hw in transcript.lower())
        confidence_score = max(4.0, 7.0 - hedge_count * 0.5)
        
        # Depth score (combination)
        depth_score = (tech_score + length_score) / 2
        
        return {
            "word_count": word_count,
            "sentence_count": sentence_count,
            "technical_keywords": tech_count,
            "experience_keywords": exp_count,
            "structure_keywords": struct_count,
            "technical_score": min(10.0, tech_score),
            "depth_score": min(10.0, depth_score),
            "practical_score": min(10.0, practical_score),
            "clarity_score": min(10.0, clarity_score),
            "confidence_score": min(10.0, confidence_score),
            "estimated_duration": word_count / 2.5,  # ~150 wpm speaking
        }
    
    def _generate_heuristic_feedback(self, analysis: dict[str, Any]) -> EvaluationFeedback:
        """Generate feedback based on heuristic analysis."""
        what_went_well = []
        what_was_missing = []
        improvement_suggestions = []
        
        # Positive feedback
        if analysis["technical_keywords"] > 5:
            what_went_well.append("Good use of technical terminology")
        if analysis["experience_keywords"] > 2:
            what_went_well.append("Drew from practical experience")
        if analysis["structure_keywords"] > 2:
            what_went_well.append("Well-structured response")
        if 100 <= analysis["word_count"] <= 300:
            what_went_well.append("Appropriate level of detail")
        
        # Areas for improvement
        if analysis["technical_keywords"] < 3:
            what_was_missing.append("Could include more technical details")
            improvement_suggestions.append("Use specific technical terms and concepts")
        if analysis["experience_keywords"] < 2:
            what_was_missing.append("Limited evidence of hands-on experience")
            improvement_suggestions.append("Include specific examples from your work")
        if analysis["word_count"] < 50:
            what_was_missing.append("Response was too brief")
            improvement_suggestions.append("Elaborate on your points with examples")
        if analysis["word_count"] > 400:
            what_was_missing.append("Response was too verbose")
            improvement_suggestions.append("Be more concise and focused")
        if analysis["structure_keywords"] < 2:
            what_was_missing.append("Could be better structured")
            improvement_suggestions.append("Organize your answer with clear sections")
        
        return EvaluationFeedback(
            what_went_well=what_went_well or ["Response provided"],
            what_was_missing=what_was_missing,
            red_flags=[],
            seniority_signals=[],
            improvement_suggestions=improvement_suggestions,
        )
    
    def _calculate_difficulty_delta(self, overall_score: float) -> int:
        """Calculate difficulty adjustment based on score."""
        if overall_score >= 8.5:
            return 2
        elif overall_score >= 7.0:
            return 1
        elif overall_score >= 5.0:
            return 0
        elif overall_score >= 3.0:
            return -1
        else:
            return -2
    
    # =========================================================================
    # AGGREGATED EVALUATION
    # =========================================================================
    
    def aggregate_skill_evaluation(
        self,
        session: InterviewSession,
        skill_id: str
    ) -> SkillEvaluation:
        """
        Aggregate evaluation for a specific skill.
        
        Args:
            session: Interview session
            skill_id: Skill to aggregate
            
        Returns:
            SkillEvaluation with aggregated data
        """
        # Get all evaluations for this skill
        skill_evaluations = []
        for q in session.questions:
            if q.evaluation and q.evaluation.get("skill_id") == skill_id:
                skill_evaluations.append(q.evaluation)
        
        if not skill_evaluations:
            return SkillEvaluation(
                skill_id=skill_id,
                skill_name=SKILL_CATALOG.get(skill_id, {}).name if skill_id in SKILL_CATALOG else skill_id,
                questions_asked=0,
                average_score=0.0,
            )
        
        # Calculate average score
        scores = [e.get("scores", {}).get("overall_score", 5.0) for e in skill_evaluations]
        if not scores:
            scores = [
                sum([
                    e.get("scores", {}).get("technical_correctness", 5.0) * 0.3,
                    e.get("scores", {}).get("depth_of_understanding", 5.0) * 0.25,
                    e.get("scores", {}).get("practical_experience", 5.0) * 0.2,
                    e.get("scores", {}).get("communication_clarity", 5.0) * 0.15,
                    e.get("scores", {}).get("confidence", 5.0) * 0.1,
                ])
                for e in skill_evaluations
            ]
        
        avg_score = sum(scores) / len(scores)
        
        # Determine trend
        if len(scores) >= 2:
            if scores[-1] > scores[0] + 0.5:
                trend = "improving"
            elif scores[-1] < scores[0] - 0.5:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "stable"
        
        # Aggregate feedback
        strengths = []
        weaknesses = []
        for e in skill_evaluations:
            feedback = e.get("feedback", {})
            strengths.extend(feedback.get("what_went_well", []))
            weaknesses.extend(feedback.get("what_was_missing", []))
        
        # Deduplicate
        strengths = list(set(strengths))[:3]
        weaknesses = list(set(weaknesses))[:3]
        
        skill_name = skill_id
        if skill_id in SKILL_CATALOG:
            skill_name = SKILL_CATALOG[skill_id].name
        
        return SkillEvaluation(
            skill_id=skill_id,
            skill_name=skill_name,
            questions_asked=len(skill_evaluations),
            average_score=avg_score,
            score_trend=trend,
            strengths=strengths,
            weaknesses=weaknesses,
            question_scores=scores,
        )
    
    def generate_interview_evaluation(
        self,
        session: InterviewSession
    ) -> InterviewEvaluation:
        """
        Generate complete interview evaluation.
        
        Args:
            session: Completed interview session
            
        Returns:
            Complete InterviewEvaluation
        """
        # Collect all response evaluations
        response_evaluations = []
        for q in session.questions:
            if q.evaluation:
                response_evaluations.append(
                    ResponseEvaluation(**q.evaluation) if isinstance(q.evaluation, dict) else q.evaluation
                )
        
        if not response_evaluations:
            # Return empty evaluation if no responses
            return InterviewEvaluation(
                session_id=session.session_id,
                overall_score=0.0,
                overall_level=ScoreLevel.POOR,
                avg_technical_correctness=0.0,
                avg_depth_of_understanding=0.0,
                avg_practical_experience=0.0,
                avg_communication_clarity=0.0,
                avg_confidence=0.0,
                total_questions=0,
                total_followups=0,
                interview_duration_seconds=session.get_duration_seconds(),
                average_response_time_seconds=0.0,
            )
        
        # Calculate dimension averages
        avg_technical = sum(e.scores.technical_correctness for e in response_evaluations) / len(response_evaluations)
        avg_depth = sum(e.scores.depth_of_understanding for e in response_evaluations) / len(response_evaluations)
        avg_practical = sum(e.scores.practical_experience for e in response_evaluations) / len(response_evaluations)
        avg_clarity = sum(e.scores.communication_clarity for e in response_evaluations) / len(response_evaluations)
        avg_confidence = sum(e.scores.confidence for e in response_evaluations) / len(response_evaluations)
        
        # Calculate overall score (0-100)
        dimension_avg = (avg_technical + avg_depth + avg_practical + avg_clarity + avg_confidence) / 5
        overall_score = dimension_avg * 10  # Scale to 0-100
        
        # Determine level
        if overall_score >= 90:
            level = ScoreLevel.EXCEPTIONAL
        elif overall_score >= 70:
            level = ScoreLevel.STRONG
        elif overall_score >= 50:
            level = ScoreLevel.ADEQUATE
        elif overall_score >= 30:
            level = ScoreLevel.WEAK
        else:
            level = ScoreLevel.POOR
        
        # Generate skill evaluations
        skill_ids = list(set(e.skill_id for e in response_evaluations))
        skill_evaluations = [
            self.aggregate_skill_evaluation(session, skill_id)
            for skill_id in skill_ids
        ]
        
        # Calculate average response time
        response_times = [e.response_duration_seconds for e in response_evaluations]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0.0
        
        return InterviewEvaluation(
            session_id=session.session_id,
            overall_score=overall_score,
            overall_level=level,
            avg_technical_correctness=avg_technical,
            avg_depth_of_understanding=avg_depth,
            avg_practical_experience=avg_practical,
            avg_communication_clarity=avg_clarity,
            avg_confidence=avg_confidence,
            skill_evaluations=skill_evaluations,
            response_evaluations=response_evaluations,
            total_questions=session.total_core_questions_asked,
            total_followups=session.total_followups_asked,
            interview_duration_seconds=session.get_duration_seconds(),
            average_response_time_seconds=avg_response_time,
        )
