"""
Interview API endpoints

Handles interview session lifecycle:
- Creating sessions
- Starting interviews
- Submitting responses
- Ending interviews
"""

from typing import Any
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from src.models.interview import InterviewSetup, InterviewSession, InterviewState
from src.core.interview_orchestrator import InterviewOrchestrator
from src.api.dependencies import get_orchestrator

router = APIRouter()


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class SetupRequest(BaseModel):
    """Request model for interview setup."""
    years_of_experience: int
    target_role: str
    cloud_preference: str = "cloud_agnostic"
    include_skills: list[str] = []
    exclude_skills: list[str] = []
    mode: str = "structured_followup"
    max_questions: int = 10


class SetupResponse(BaseModel):
    """Response model for interview setup."""
    session_id: str
    status: str
    message: str


class StartResponse(BaseModel):
    """Response after starting interview."""
    session_id: str
    state: str
    first_question: dict[str, Any] | None = None


class SubmitResponseRequest(BaseModel):
    """Request model for submitting a response."""
    transcript: str
    audio_base64: str | None = None


class SubmitResponseResponse(BaseModel):
    """Response after submitting an answer."""
    action: str  # "followup", "question", "complete"
    question_id: str | None = None
    question_text: str | None = None
    question_number: int | None = None
    total_questions: int | None = None
    message: str | None = None


class SessionStatusResponse(BaseModel):
    """Response for session status."""
    session_id: str
    state: str
    questions_asked: int
    current_difficulty: int
    duration_seconds: float


# ============================================================================
# REST ENDPOINTS
# ============================================================================

@router.post("/setup", response_model=SetupResponse)
async def setup_interview(request: SetupRequest) -> SetupResponse:
    """
    Create a new interview session.
    
    This initializes the interview with user preferences
    but does not start the interview yet.
    """
    try:
        from src.models.interview import InterviewSetup, InterviewMode
        from src.models.roles import Role, CloudPreference
        
        # Map strings to enums
        role_map = {
            "junior_data_engineer": Role.JUNIOR_DE,
            "mid_data_engineer": Role.MID_DE,
            "senior_data_engineer": Role.SENIOR_DE,
            "staff_data_engineer": Role.STAFF_DE,
            "principal_data_engineer": Role.PRINCIPAL_DE,
        }
        
        cloud_map = {
            "aws": CloudPreference.AWS,
            "gcp": CloudPreference.GCP,
            "azure": CloudPreference.AZURE,
            "multi_cloud": CloudPreference.MULTI,
            "cloud_agnostic": CloudPreference.AGNOSTIC,
        }
        
        mode_map = {
            "structured": InterviewMode.STRUCTURED,
            "structured_followup": InterviewMode.STRUCTURED_FOLLOWUP,
            "stress": InterviewMode.STRESS,
        }
        
        # Create setup
        setup = InterviewSetup(
            years_of_experience=request.years_of_experience,
            target_role=role_map.get(request.target_role, Role.MID_DE),
            cloud_preference=cloud_map.get(request.cloud_preference, CloudPreference.AGNOSTIC),
            include_skills=request.include_skills,
            exclude_skills=request.exclude_skills,
            mode=mode_map.get(request.mode, InterviewMode.STRUCTURED_FOLLOWUP),
            max_questions=request.max_questions,
        )
        
        # Create session
        orchestrator = get_orchestrator()
        session = await orchestrator.create_session(setup)
        
        return SetupResponse(
            session_id=session.session_id,
            status="created",
            message="Interview session created. Call /start to begin.",
        )
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{session_id}/start", response_model=StartResponse)
async def start_interview(session_id: str) -> StartResponse:
    """
    Start the interview.
    
    This transitions the session to READY and delivers the first question.
    """
    orchestrator = get_orchestrator()
    session = orchestrator.get_session(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if session.state != InterviewState.SETUP:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot start interview in state: {session.state}"
        )
    
    try:
        result = await orchestrator.start_interview(session_id)
        
        return StartResponse(
            session_id=session_id,
            state=InterviewState.LISTENING.value,
            first_question=result if result.get("action") == "question" else None,
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{session_id}/respond", response_model=SubmitResponseResponse)
async def submit_response(
    session_id: str,
    request: SubmitResponseRequest
) -> SubmitResponseResponse:
    """
    Submit a response to the current question.
    
    The response is evaluated and the next action is determined.
    """
    orchestrator = get_orchestrator()
    session = orchestrator.get_session(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if session.state != InterviewState.LISTENING:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot submit response in state: {session.state}"
        )
    
    try:
        # Convert base64 audio if provided
        audio_data = None
        if request.audio_base64:
            import base64
            audio_data = base64.b64decode(request.audio_base64)
        
        result = await orchestrator.submit_response(
            session_id=session_id,
            transcript=request.transcript,
            audio_data=audio_data,
        )
        
        return SubmitResponseResponse(
            action=result.get("action", "unknown"),
            question_id=result.get("question_id"),
            question_text=result.get("question_text"),
            question_number=result.get("question_number"),
            total_questions=result.get("total_questions"),
            message=result.get("message"),
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{session_id}/end")
async def end_interview(session_id: str) -> dict[str, Any]:
    """
    End the interview early.
    
    Transitions to COMPLETE state and prepares for report generation.
    """
    orchestrator = get_orchestrator()
    session = orchestrator.get_session(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if session.state in [InterviewState.COMPLETE, InterviewState.FINISHED]:
        return {"status": "already_ended", "session_id": session_id}
    
    try:
        result = await orchestrator.end_interview(session_id)
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}/status", response_model=SessionStatusResponse)
async def get_session_status(session_id: str) -> SessionStatusResponse:
    """Get the current status of an interview session."""
    orchestrator = get_orchestrator()
    session = orchestrator.get_session(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return SessionStatusResponse(
        session_id=session.session_id,
        state=session.state.value,
        questions_asked=session.total_core_questions_asked,
        current_difficulty=session.current_difficulty,
        duration_seconds=session.get_duration_seconds(),
    )


# ============================================================================
# WEBSOCKET ENDPOINT
# ============================================================================

@router.websocket("/ws/{session_id}")
async def websocket_interview(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for real-time interview interaction.
    
    Message types:
    - start: Start the interview
    - audio_chunk: Stream audio data
    - transcript: Submit transcribed text
    - end: End the interview
    
    Server sends:
    - state_change: Interview state updated
    - question: New question (with audio)
    - evaluation_complete: Response evaluated
    - error: Error occurred
    """
    await websocket.accept()
    
    orchestrator = get_orchestrator()
    session = orchestrator.get_session(session_id)
    
    if not session:
        await websocket.close(code=4004, reason="Session not found")
        return
    
    try:
        while True:
            data = await websocket.receive_json()
            message_type = data.get("type")
            
            if message_type == "start":
                # Start the interview
                result = await orchestrator.start_interview(session_id)
                await websocket.send_json({
                    "type": "question",
                    "data": result,
                })
                
            elif message_type == "transcript":
                # Process transcribed response
                transcript = data.get("transcript", "")
                result = await orchestrator.submit_response(
                    session_id=session_id,
                    transcript=transcript,
                )
                
                if result.get("action") == "complete":
                    await websocket.send_json({
                        "type": "complete",
                        "data": result,
                    })
                else:
                    await websocket.send_json({
                        "type": "question",
                        "data": result,
                    })
                
            elif message_type == "end":
                # End interview
                result = await orchestrator.end_interview(session_id)
                await websocket.send_json({
                    "type": "ended",
                    "data": result,
                })
                break
                
            elif message_type == "ping":
                await websocket.send_json({"type": "pong"})
                
    except WebSocketDisconnect:
        # Client disconnected
        pass
    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "message": str(e),
        })
