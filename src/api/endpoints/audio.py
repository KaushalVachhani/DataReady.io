"""
Audio API endpoints

Handles:
- Text-to-speech generation
- Speech-to-text transcription
"""

import base64
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

from src.api.dependencies import get_audio_processor

router = APIRouter()


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class TTSRequest(BaseModel):
    """Request for text-to-speech."""
    text: str
    voice: str | None = None


class TTSResponse(BaseModel):
    """Response with generated audio."""
    audio_base64: str
    format: str
    duration_seconds: float
    sample_rate: int


class STTResponse(BaseModel):
    """Response with transcribed text."""
    transcript: str
    confidence: float | None = None
    duration_seconds: float | None = None


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/tts", response_model=TTSResponse)
async def text_to_speech(request: TTSRequest) -> TTSResponse:
    """
    Convert text to speech.
    
    Returns base64-encoded audio data.
    """
    try:
        processor = get_audio_processor()
        result = await processor.text_to_speech(
            text=request.text,
            voice=request.voice,
        )
        
        if result.get("error"):
            raise HTTPException(
                status_code=500,
                detail=f"TTS failed: {result['error']}"
            )
        
        return TTSResponse(
            audio_base64=result.get("audio_data", ""),
            format=result.get("format", "wav"),
            duration_seconds=result.get("duration_seconds", 0),
            sample_rate=result.get("sample_rate", 16000),
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stt", response_model=STTResponse)
async def speech_to_text(
    audio: UploadFile = File(...),
    language: str = "en"
) -> STTResponse:
    """
    Transcribe audio to text.
    
    Accepts audio file upload.
    """
    try:
        audio_data = await audio.read()
        
        processor = get_audio_processor()
        transcript = await processor.speech_to_text(
            audio_data=audio_data,
            language=language,
        )
        
        return STTResponse(
            transcript=transcript,
            confidence=None,  # Whisper doesn't provide confidence
            duration_seconds=None,
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stt/base64", response_model=STTResponse)
async def speech_to_text_base64(
    audio_base64: str,
    language: str = "en"
) -> STTResponse:
    """
    Transcribe base64-encoded audio to text.
    """
    try:
        audio_data = base64.b64decode(audio_base64)
        
        processor = get_audio_processor()
        transcript = await processor.speech_to_text(
            audio_data=audio_data,
            language=language,
        )
        
        return STTResponse(
            transcript=transcript,
            confidence=None,
            duration_seconds=None,
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validate")
async def validate_audio(audio: UploadFile = File(...)) -> dict[str, Any]:
    """
    Validate audio file format and properties.
    """
    try:
        audio_data = await audio.read()
        
        processor = get_audio_processor()
        result = await processor.validate_audio(audio_data)
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
