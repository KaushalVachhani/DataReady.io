"""
Report Generator for DataReady.io

Generates comprehensive interview reports with:
- Overall scores
- Skill breakdowns
- Strengths and weaknesses
- Hiring verdict
- Study roadmap
"""

import logging
from datetime import datetime

from src.models.interview import InterviewSession
from src.models.evaluation import InterviewEvaluation, ScoreLevel
from src.models.report import (
    InterviewReport,
    SkillScore,
    HiringVerdict,
    RoleReadiness,
    ImprovementSuggestion,
    StudyRoadmap,
    ReportSummary,
)
from src.models.roles import SKILL_CATALOG, get_role_focus_areas
from src.core.evaluation_engine import EvaluationEngine

logger = logging.getLogger(__name__)


class ReportGenerator:
    """
    Generates comprehensive interview reports.
    
    Uses evaluation data to produce actionable feedback
    and recommendations for candidates.
    """
    
    def __init__(self, ai_reasoning=None):
        """
        Initialize report generator.
        
        Args:
            ai_reasoning: AI reasoning layer for enhanced insights
        """
        self.ai_reasoning = ai_reasoning
        self.evaluation_engine = EvaluationEngine(ai_reasoning)
    
    async def generate(self, session: InterviewSession) -> InterviewReport:
        """
        Generate complete interview report.
        
        Args:
            session: Completed interview session
            
        Returns:
            Complete InterviewReport
        """
        # Generate interview evaluation
        evaluation = self.evaluation_engine.generate_interview_evaluation(session)
        
        # Calculate derived metrics
        hiring_verdict = self._determine_hiring_verdict(evaluation)
        role_readiness = self._determine_role_readiness(evaluation, session)
        
        # Generate skill scores for radar chart
        skill_scores = self._generate_skill_scores(session, evaluation)
        
        # Generate qualitative feedback
        strengths = self._identify_strengths(evaluation)
        improvement_areas = self._identify_improvement_areas(evaluation)
        missed_concepts = self._identify_missed_concepts(session, evaluation)
        
        # Generate recommendations
        suggestions = self._generate_improvement_suggestions(evaluation, session)
        roadmap = self._generate_study_roadmap(evaluation, session)
        
        # Communication feedback
        comm_feedback = self._generate_communication_feedback(evaluation)
        
        # Performance timeline
        timeline = self._generate_performance_timeline(session)
        
        # Per-question feedback
        question_feedback = self._generate_question_feedback(session, evaluation)
        
        return InterviewReport(
            session_id=session.session_id,
            generated_at=datetime.utcnow(),
            target_role=session.setup.target_role,
            years_of_experience=session.setup.years_of_experience,
            interview_duration_minutes=session.get_duration_seconds() / 60,
            overall_score=evaluation.overall_score,
            overall_score_interpretation=self._interpret_score(evaluation.overall_score),
            dimension_scores={
                "Technical Correctness": evaluation.avg_technical_correctness,
                "Depth of Understanding": evaluation.avg_depth_of_understanding,
                "Practical Experience": evaluation.avg_practical_experience,
                "Communication Clarity": evaluation.avg_communication_clarity,
                "Confidence": evaluation.avg_confidence,
            },
            skill_scores=skill_scores,
            hiring_verdict=hiring_verdict,
            role_readiness=role_readiness,
            role_readiness_explanation=self._explain_role_readiness(role_readiness, session),
            top_strengths=strengths,
            areas_for_improvement=improvement_areas,
            missed_concepts=missed_concepts,
            communication_feedback=comm_feedback,
            improvement_suggestions=suggestions,
            study_roadmap=roadmap,
            performance_timeline=timeline,
            question_feedback=question_feedback,
        )
    
    def _determine_hiring_verdict(self, evaluation: InterviewEvaluation) -> HiringVerdict:
        """Determine hiring recommendation."""
        score = evaluation.overall_score
        
        if score >= 85:
            return HiringVerdict.STRONG_HIRE
        elif score >= 70:
            return HiringVerdict.HIRE
        elif score >= 55:
            return HiringVerdict.BORDERLINE
        else:
            return HiringVerdict.NEEDS_IMPROVEMENT
    
    def _determine_role_readiness(
        self,
        evaluation: InterviewEvaluation,
        session: InterviewSession
    ) -> RoleReadiness:
        """Determine readiness for target role."""
        score = evaluation.overall_score
        
        # Adjust based on experience alignment
        expected_exp_ranges = {
            "junior_data_engineer": (0, 2),
            "mid_data_engineer": (2, 5),
            "senior_data_engineer": (5, 8),
            "staff_data_engineer": (8, 12),
            "principal_data_engineer": (12, 30),
        }
        
        role_range = expected_exp_ranges.get(
            session.setup.target_role.value,
            (0, 30)
        )
        experience = session.setup.years_of_experience
        
        # Check if experience aligns with role
        exp_aligned = role_range[0] <= experience <= role_range[1] + 2
        
        if score >= 80 and exp_aligned:
            return RoleReadiness.READY
        elif score >= 65 or (score >= 55 and exp_aligned):
            return RoleReadiness.ALMOST_READY
        elif score >= 45:
            return RoleReadiness.NEEDS_WORK
        else:
            return RoleReadiness.NOT_READY
    
    def _generate_skill_scores(
        self,
        session: InterviewSession,
        evaluation: InterviewEvaluation
    ) -> list[SkillScore]:
        """Generate skill scores for detailed breakdown."""
        skill_scores = []
        
        for skill_eval in evaluation.skill_evaluations:
            skill_info = SKILL_CATALOG.get(skill_eval.skill_id)
            
            score = SkillScore(
                skill_id=skill_eval.skill_id,
                skill_name=skill_eval.skill_name,
                category=skill_info.category.value if skill_info else "general",
                score=skill_eval.average_score,
                questions_asked=skill_eval.questions_asked,
                questions_answered_well=sum(1 for s in skill_eval.question_scores if s >= 7.0),
                summary=self._summarize_skill_performance(skill_eval),
                strengths=skill_eval.strengths[:2],
                gaps=skill_eval.weaknesses[:2],
            )
            skill_scores.append(score)
        
        return sorted(skill_scores, key=lambda x: x.score, reverse=True)
    
    def _summarize_skill_performance(self, skill_eval) -> str:
        """Generate summary for skill performance."""
        score = skill_eval.average_score
        trend = skill_eval.score_trend
        
        if score >= 8.0:
            base = "Excellent understanding demonstrated"
        elif score >= 6.5:
            base = "Good competency shown"
        elif score >= 5.0:
            base = "Adequate knowledge with room for growth"
        elif score >= 3.5:
            base = "Foundational understanding needs strengthening"
        else:
            base = "Significant gaps identified"
        
        if trend == "improving":
            base += ", showing improvement throughout"
        elif trend == "declining":
            base += ", consider reviewing fundamentals"
        
        return base
    
    def _identify_strengths(self, evaluation: InterviewEvaluation) -> list[str]:
        """Identify top strengths from evaluation."""
        strengths = []
        
        # Check dimension scores
        if evaluation.avg_technical_correctness >= 7.5:
            strengths.append("Strong technical accuracy in responses")
        if evaluation.avg_depth_of_understanding >= 7.5:
            strengths.append("Deep understanding of concepts")
        if evaluation.avg_practical_experience >= 7.5:
            strengths.append("Solid hands-on experience evident")
        if evaluation.avg_communication_clarity >= 7.5:
            strengths.append("Excellent communication skills")
        if evaluation.avg_confidence >= 7.5:
            strengths.append("Confident and composed delivery")
        
        # Add skill-specific strengths
        for skill_eval in evaluation.skill_evaluations:
            if skill_eval.average_score >= 7.5:
                strengths.append(f"Strong performance in {skill_eval.skill_name}")
        
        # Collect feedback-based strengths
        for resp_eval in evaluation.response_evaluations:
            strengths.extend(resp_eval.feedback.what_went_well[:1])
        
        # Deduplicate and limit
        unique_strengths = list(dict.fromkeys(strengths))
        return unique_strengths[:5]
    
    def _identify_improvement_areas(self, evaluation: InterviewEvaluation) -> list[str]:
        """Identify areas needing improvement."""
        areas = []
        
        # Check dimension scores
        if evaluation.avg_technical_correctness < 6.0:
            areas.append("Technical accuracy needs improvement")
        if evaluation.avg_depth_of_understanding < 6.0:
            areas.append("Deepen understanding of core concepts")
        if evaluation.avg_practical_experience < 6.0:
            areas.append("Gain more hands-on experience")
        if evaluation.avg_communication_clarity < 6.0:
            areas.append("Work on articulating ideas more clearly")
        if evaluation.avg_confidence < 6.0:
            areas.append("Build more confidence in responses")
        
        # Add skill-specific gaps
        for skill_eval in evaluation.skill_evaluations:
            if skill_eval.average_score < 5.5:
                areas.append(f"Focus on improving {skill_eval.skill_name}")
        
        # Collect feedback-based areas
        for resp_eval in evaluation.response_evaluations:
            areas.extend(resp_eval.feedback.what_was_missing[:1])
        
        unique_areas = list(dict.fromkeys(areas))
        return unique_areas[:5]
    
    def _identify_missed_concepts(
        self,
        session: InterviewSession,
        evaluation: InterviewEvaluation
    ) -> list[str]:
        """Identify concepts that were missed or poorly understood."""
        missed = []
        
        # Check skills that weren't covered
        role_focus = get_role_focus_areas(session.setup.target_role)
        covered_skills = [e.skill_id for e in evaluation.skill_evaluations]
        
        for focus in role_focus:
            if not any(focus.lower() in skill.lower() for skill in covered_skills):
                missed.append(f"Not assessed: {focus}")
        
        # Check poor performances
        for skill_eval in evaluation.skill_evaluations:
            if skill_eval.average_score < 5.0:
                missed.append(f"Weak understanding: {skill_eval.skill_name}")
        
        # Add specific gaps from feedback
        for resp_eval in evaluation.response_evaluations:
            if resp_eval.scores.overall_score < 5.0:
                missed.extend(resp_eval.feedback.what_was_missing[:1])
        
        unique_missed = list(dict.fromkeys(missed))
        return unique_missed[:5]
    
    def _generate_communication_feedback(self, evaluation: InterviewEvaluation) -> str:
        """Generate feedback on communication style."""
        clarity = evaluation.avg_communication_clarity
        confidence = evaluation.avg_confidence
        
        if clarity >= 8.0 and confidence >= 8.0:
            return ("Excellent communicator with clear, confident delivery. "
                    "Responses were well-structured and easy to follow.")
        elif clarity >= 7.0 and confidence >= 7.0:
            return ("Good communication skills overall. Responses were clear "
                    "with appropriate confidence levels.")
        elif clarity >= 6.0 or confidence >= 6.0:
            return ("Communication is adequate but could be improved. "
                    "Consider structuring answers more clearly and projecting more confidence.")
        else:
            return ("Communication needs significant improvement. "
                    "Focus on organizing thoughts before speaking and building confidence.")
    
    def _generate_improvement_suggestions(
        self,
        evaluation: InterviewEvaluation,
        session: InterviewSession
    ) -> list[ImprovementSuggestion]:
        """Generate actionable improvement suggestions."""
        suggestions = []
        
        # Technical improvement
        if evaluation.avg_technical_correctness < 7.0:
            suggestions.append(ImprovementSuggestion(
                area="Technical Knowledge",
                priority="high",
                suggestion="Review core data engineering concepts and best practices",
                resources=[
                    "Designing Data-Intensive Applications (book)",
                    "Data Engineering courses on Coursera/Udemy",
                ],
                estimated_time="4-6 weeks",
            ))
        
        # Practical experience
        if evaluation.avg_practical_experience < 7.0:
            suggestions.append(ImprovementSuggestion(
                area="Hands-on Experience",
                priority="high",
                suggestion="Build personal projects to gain practical experience",
                resources=[
                    "Kaggle datasets for pipeline projects",
                    "Cloud free tiers for practice",
                ],
                estimated_time="Ongoing",
            ))
        
        # Skill-specific suggestions
        for skill_eval in evaluation.skill_evaluations:
            if skill_eval.average_score < 6.0:
                skill_info = SKILL_CATALOG.get(skill_eval.skill_id)
                suggestions.append(ImprovementSuggestion(
                    area=skill_eval.skill_name,
                    priority="medium",
                    suggestion=f"Deep dive into {skill_eval.skill_name} concepts and practice",
                    resources=[],
                    estimated_time="2-3 weeks",
                ))
        
        return suggestions[:6]
    
    def _generate_study_roadmap(
        self,
        evaluation: InterviewEvaluation,
        session: InterviewSession
    ) -> StudyRoadmap:
        """Generate personalized study roadmap."""
        # Identify weak areas
        weak_skills = [
            e for e in evaluation.skill_evaluations
            if e.average_score < 6.5
        ]
        
        weeks = []
        week_num = 1
        
        # Focus on fundamentals first
        if evaluation.avg_technical_correctness < 7.0:
            weeks.append({
                "week": week_num,
                "focus": "Core Concepts Review",
                "activities": [
                    "Review data engineering fundamentals",
                    "Study system design patterns",
                    "Practice SQL problems",
                ],
            })
            week_num += 1
        
        # Address weak skills
        for skill in weak_skills[:3]:
            weeks.append({
                "week": week_num,
                "focus": skill.skill_name,
                "activities": [
                    f"Study {skill.skill_name} in depth",
                    "Complete hands-on exercises",
                    "Review real-world examples",
                ],
            })
            week_num += 1
        
        # Mock interview practice
        weeks.append({
            "week": week_num,
            "focus": "Interview Practice",
            "activities": [
                "Take another mock interview",
                "Practice explaining concepts aloud",
                "Review and refine weak areas",
            ],
        })
        
        return StudyRoadmap(
            timeframe=f"{len(weeks)} weeks",
            weeks=weeks,
            recommended_resources=[
                {"title": "Designing Data-Intensive Applications", "type": "Book"},
                {"title": "System Design Interview", "type": "Book"},
                {"title": "LeetCode SQL Problems", "type": "Practice"},
            ],
            practice_suggestions=[
                "Explain concepts out loud daily",
                "Build a sample data pipeline",
                "Review one system design case study per week",
            ],
        )
    
    def _generate_performance_timeline(self, session: InterviewSession) -> list[dict]:
        """Generate performance timeline showing score progression."""
        timeline = []
        
        for i, question in enumerate(session.questions):
            if question.evaluation:
                eval_data = question.evaluation
                scores = eval_data.get("scores", {})
                
                # Calculate overall for this question
                overall = (
                    scores.get("technical_correctness", 5) * 0.3 +
                    scores.get("depth_of_understanding", 5) * 0.25 +
                    scores.get("practical_experience", 5) * 0.2 +
                    scores.get("communication_clarity", 5) * 0.15 +
                    scores.get("confidence", 5) * 0.1
                )
                
                timeline.append({
                    "question_number": i + 1,
                    "is_followup": question.is_followup,
                    "score": round(overall, 1),
                    "difficulty": session.difficulty_history[i] if i < len(session.difficulty_history) else session.current_difficulty,
                })
        
        return timeline
    
    def _generate_question_feedback(
        self,
        session: InterviewSession,
        evaluation: InterviewEvaluation
    ) -> list[dict]:
        """Generate detailed feedback for each question."""
        feedback_list = []
        
        for i, question in enumerate(session.questions):
            eval_data = question.evaluation or {}
            scores = eval_data.get("scores", {})
            
            # Check if skipped
            is_skipped = (
                question.response_transcript and 
                "[Question skipped" in question.response_transcript
            ) or not question.response_transcript
            
            # Calculate overall score for this question
            if is_skipped:
                overall_score = 0
            else:
                overall_score = (
                    scores.get("technical_correctness", 0) * 0.3 +
                    scores.get("depth_of_understanding", 0) * 0.25 +
                    scores.get("practical_experience", 0) * 0.2 +
                    scores.get("communication_clarity", 0) * 0.15 +
                    scores.get("confidence", 0) * 0.1
                )
            
            # Build improvement tips
            improvements = []
            what_went_well = []
            
            if not is_skipped:
                # Extract from evaluation
                missing_points = eval_data.get("missing_points", [])
                red_flags = eval_data.get("red_flags_triggered", [])
                covered_points = eval_data.get("expected_points_covered", [])
                
                # What went well
                if covered_points:
                    what_went_well = [f"Covered: {point}" for point in covered_points[:3]]
                
                if scores.get("technical_correctness", 0) >= 7:
                    what_went_well.append("Strong technical accuracy")
                if scores.get("communication_clarity", 0) >= 7:
                    what_went_well.append("Clear communication")
                if scores.get("depth_of_understanding", 0) >= 7:
                    what_went_well.append("Good depth of understanding")
                
                # Areas for improvement
                if missing_points:
                    improvements = [f"Missing: {point}" for point in missing_points[:3]]
                
                if red_flags:
                    improvements.extend([f"Concern: {flag}" for flag in red_flags[:2]])
                
                # Score-based suggestions
                if scores.get("technical_correctness", 0) < 5:
                    improvements.append("Review core concepts for accuracy")
                if scores.get("practical_experience", 0) < 5:
                    improvements.append("Include more real-world examples")
                if scores.get("depth_of_understanding", 0) < 5:
                    improvements.append("Go deeper into underlying principles")
                if scores.get("communication_clarity", 0) < 5:
                    improvements.append("Structure your answer more clearly")
            else:
                improvements = ["Question was skipped - no assessment possible"]
            
            # Get expected answer from evaluation or generate
            expected_answer = eval_data.get("expected_answer", "")
            if not expected_answer and overall_score < 7:
                expected_points = eval_data.get("expected_points", [])
                if expected_points:
                    expected_answer = "Key points to cover:\n• " + "\n• ".join(expected_points[:5])
            
            # Get skill info
            skill_name = ""
            category = ""
            if question.skill_id:
                skill_info = SKILL_CATALOG.get(question.skill_id)
                if skill_info:
                    skill_name = skill_info.name
                    category = skill_info.category.value if skill_info.category else ""
            
            feedback_list.append({
                "question_number": i + 1,
                "question": question.question_text,
                "skill_id": question.skill_id or "",
                "skill_name": skill_name,
                "category": category,
                "is_followup": question.is_followup,
                "skipped": is_skipped,
                "score": round(overall_score, 1),
                "scores": {
                    "technical": scores.get("technical_correctness", 0),
                    "depth": scores.get("depth_of_understanding", 0),
                    "practical": scores.get("practical_experience", 0),
                    "communication": scores.get("communication_clarity", 0),
                    "confidence": scores.get("confidence", 0),
                },
                "transcript": question.response_transcript or "",
                "what_went_well": what_went_well[:4],
                "improvements": improvements[:5],
                "expected_answer": expected_answer,
                "difficulty": session.difficulty_history[i] if i < len(session.difficulty_history) else session.current_difficulty,
            })
        
        return feedback_list
    
    def _interpret_score(self, score: float) -> str:
        """Interpret overall score."""
        if score >= 90:
            return "Exceptional performance - ready for senior roles"
        elif score >= 80:
            return "Strong performance - well prepared for the target role"
        elif score >= 70:
            return "Good performance - ready with minor improvements"
        elif score >= 60:
            return "Adequate performance - some areas need strengthening"
        elif score >= 50:
            return "Below expectations - focused study recommended"
        else:
            return "Needs significant improvement before interview readiness"
    
    def _explain_role_readiness(
        self,
        readiness: RoleReadiness,
        session: InterviewSession
    ) -> str:
        """Explain role readiness assessment."""
        role_name = session.setup.target_role.display_name
        
        explanations = {
            RoleReadiness.READY: f"Demonstrates the skills and knowledge expected for a {role_name}. Ready to interview with confidence.",
            RoleReadiness.ALMOST_READY: f"Shows solid foundation for a {role_name} role. A bit more preparation in weak areas will increase success chances.",
            RoleReadiness.NEEDS_WORK: f"Has potential for a {role_name} position but requires focused improvement in key areas before interviewing.",
            RoleReadiness.NOT_READY: f"Significant gaps exist for a {role_name} role. Recommend structured learning path before attempting interviews.",
        }
        
        return explanations.get(readiness, "Assessment not available.")
    
    def generate_summary(self, report: InterviewReport) -> ReportSummary:
        """Generate condensed report summary."""
        return ReportSummary(
            session_id=report.session_id,
            overall_score=report.overall_score,
            hiring_verdict=report.hiring_verdict,
            role_readiness=report.role_readiness,
            top_strength=report.top_strengths[0] if report.top_strengths else "N/A",
            top_improvement_area=report.areas_for_improvement[0] if report.areas_for_improvement else "N/A",
            interview_duration_minutes=report.interview_duration_minutes,
        )
