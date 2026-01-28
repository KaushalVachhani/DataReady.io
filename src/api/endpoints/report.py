"""
Report API endpoints

Handles:
- Report generation
- Report retrieval
"""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.models.interview import InterviewState
from src.models.report import HiringVerdict, RoleReadiness
from src.api.dependencies import get_orchestrator

router = APIRouter()


# ============================================================================
# RESPONSE MODELS
# ============================================================================

class ReportSummaryResponse(BaseModel):
    """Condensed report response."""
    session_id: str
    overall_score: float
    hiring_verdict: str
    role_readiness: str
    top_strength: str
    top_improvement_area: str
    interview_duration_minutes: float


class ReportResponse(BaseModel):
    """Full report response."""
    session_id: str
    overall_score: float
    overall_score_interpretation: str
    dimension_scores: dict[str, float]
    skill_scores: list[dict[str, Any]]
    hiring_verdict: str
    hiring_verdict_description: str
    role_readiness: str
    role_readiness_explanation: str
    top_strengths: list[str]
    areas_for_improvement: list[str]
    missed_concepts: list[str]
    communication_feedback: str
    improvement_suggestions: list[dict[str, Any]]
    study_roadmap: dict[str, Any] | None
    performance_timeline: list[dict[str, Any]]
    interview_duration_minutes: float
    # Question-level feedback
    question_feedback: list[dict[str, Any]] = []
    total_questions: int = 0
    total_followups: int = 0


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("/{session_id}", response_model=ReportResponse)
async def get_report(session_id: str) -> ReportResponse:
    """
    Get the full interview report.
    
    Report is generated after interview completion.
    """
    orchestrator = get_orchestrator()
    session = orchestrator.get_session(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Check if interview is complete
    if session.state not in [
        InterviewState.COMPLETE,
        InterviewState.GENERATING_REPORT,
        InterviewState.FINISHED
    ]:
        raise HTTPException(
            status_code=400,
            detail=f"Interview not complete. Current state: {session.state.value}"
        )
    
    try:
        # Generate report
        report_data = await orchestrator.generate_report(session_id)
        
        # Get question feedback from session for stats
        question_feedback = report_data.get("question_feedback", [])
        total_questions = len(question_feedback)
        total_followups = len([q for q in question_feedback if q.get("is_followup", False)])
        
        # Format for response
        return ReportResponse(
            session_id=report_data["session_id"],
            overall_score=report_data["overall_score"],
            overall_score_interpretation=report_data["overall_score_interpretation"],
            dimension_scores=report_data["dimension_scores"],
            skill_scores=[s for s in report_data.get("skill_scores", [])],
            hiring_verdict=report_data["hiring_verdict"],
            hiring_verdict_description=HiringVerdict(report_data["hiring_verdict"]).description,
            role_readiness=report_data["role_readiness"],
            role_readiness_explanation=report_data["role_readiness_explanation"],
            top_strengths=report_data["top_strengths"],
            areas_for_improvement=report_data["areas_for_improvement"],
            missed_concepts=report_data["missed_concepts"],
            communication_feedback=report_data["communication_feedback"],
            improvement_suggestions=[
                s if isinstance(s, dict) else s.model_dump()
                for s in report_data.get("improvement_suggestions", [])
            ],
            study_roadmap=report_data.get("study_roadmap"),
            performance_timeline=report_data.get("performance_timeline", []),
            interview_duration_minutes=report_data["interview_duration_minutes"],
            question_feedback=question_feedback,
            total_questions=total_questions,
            total_followups=total_followups,
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}/summary", response_model=ReportSummaryResponse)
async def get_report_summary(session_id: str) -> ReportSummaryResponse:
    """
    Get a condensed report summary.
    
    Useful for quick overview before viewing full report.
    """
    orchestrator = get_orchestrator()
    session = orchestrator.get_session(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if session.state not in [
        InterviewState.COMPLETE,
        InterviewState.GENERATING_REPORT,
        InterviewState.FINISHED
    ]:
        raise HTTPException(
            status_code=400,
            detail=f"Interview not complete. Current state: {session.state.value}"
        )
    
    try:
        report_data = await orchestrator.generate_report(session_id)
        
        return ReportSummaryResponse(
            session_id=report_data["session_id"],
            overall_score=report_data["overall_score"],
            hiring_verdict=report_data["hiring_verdict"],
            role_readiness=report_data["role_readiness"],
            top_strength=report_data["top_strengths"][0] if report_data["top_strengths"] else "N/A",
            top_improvement_area=report_data["areas_for_improvement"][0] if report_data["areas_for_improvement"] else "N/A",
            interview_duration_minutes=report_data["interview_duration_minutes"],
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}/questions")
async def get_question_details(session_id: str) -> dict[str, Any]:
    """
    Get detailed per-question feedback.
    
    Shows each question with scores and feedback.
    """
    orchestrator = get_orchestrator()
    session = orchestrator.get_session(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    questions = []
    for i, q in enumerate(session.questions):
        question_data = {
            "number": i + 1,
            "question_id": q.question_id,
            "question_text": q.question_text,
            "is_followup": q.is_followup,
            "response_transcript": q.response_transcript,
            "asked_at": q.asked_at.isoformat() if q.asked_at else None,
        }
        
        if q.evaluation:
            eval_data = q.evaluation
            question_data["scores"] = eval_data.get("scores", {})
            question_data["feedback"] = eval_data.get("feedback", {})
        
        questions.append(question_data)
    
    return {
        "session_id": session_id,
        "total_questions": len(questions),
        "questions": questions,
    }
