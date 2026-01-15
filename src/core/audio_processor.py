"""
Audio Processing Layer for DataReady.io

Handles:
- Speech-to-Text (STT) using Whisper
- Text-to-Speech (TTS) using open-source models

Designed for:
- Low-latency transcription of user responses
- Natural-sounding AI interviewer voice
"""

import asyncio
import base64
import io
import logging
import tempfile
from pathlib import Path
from typing import Any

import httpx

from src.config.settings import get_settings

logger = logging.getLogger(__name__)


class AudioProcessor:
    """
    Central audio processing component.
    
    STT: Uses Whisper (local or API) for transcription
    TTS: Uses Kokoro/Piper (local) or Edge-TTS for synthesis
    """
    
    def __init__(self):
        """Initialize audio processor."""
        self.settings = get_settings()
        
        # Lazy-loaded models
        self._whisper_model = None
        self._tts_model = None
        
        # HTTP client for API-based services
        self.client = httpx.AsyncClient(timeout=60.0)
    
    async def close(self):
        """Clean up resources."""
        await self.client.aclose()
    
    # =========================================================================
    # SPEECH-TO-TEXT (Whisper)
    # =========================================================================
    
    async def speech_to_text(
        self,
        audio_data: bytes,
        language: str = "en"
    ) -> str:
        """
        Transcribe audio to text using Whisper.
        
        Args:
            audio_data: Raw audio bytes (WAV or similar)
            language: Language code
            
        Returns:
            Transcribed text
        """
        if self.settings.use_local_whisper:
            return await self._transcribe_local(audio_data, language)
        else:
            return await self._transcribe_api(audio_data, language)
    
    async def _transcribe_local(self, audio_data: bytes, language: str) -> str:
        """Transcribe using local Whisper model."""
        try:
            # Lazy load the model
            if self._whisper_model is None:
                await self._load_whisper_model()
            
            # Save audio to temp file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(audio_data)
                temp_path = f.name
            
            try:
                # Run transcription in thread pool to avoid blocking
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    self._run_whisper_transcription,
                    temp_path,
                    language,
                )
                return result
            finally:
                # Clean up temp file
                Path(temp_path).unlink(missing_ok=True)
                
        except Exception as e:
            logger.error(f"Local transcription failed: {e}")
            raise
    
    async def _load_whisper_model(self):
        """Load Whisper model lazily."""
        try:
            import whisper
            
            logger.info(f"Loading Whisper model: {self.settings.whisper_model}")
            
            # Run model loading in thread pool
            loop = asyncio.get_event_loop()
            self._whisper_model = await loop.run_in_executor(
                None,
                whisper.load_model,
                self.settings.whisper_model.replace("whisper-", "").replace("-v3", ""),
            )
            
            logger.info("Whisper model loaded successfully")
            
        except ImportError:
            logger.error("Whisper not installed. Install with: pip install openai-whisper")
            raise
    
    def _run_whisper_transcription(self, audio_path: str, language: str) -> str:
        """Run Whisper transcription (blocking, runs in thread pool)."""
        result = self._whisper_model.transcribe(
            audio_path,
            language=language,
            fp16=False,  # Use FP32 for better compatibility
        )
        return result.get("text", "").strip()
    
    async def _transcribe_api(self, audio_data: bytes, language: str) -> str:
        """Transcribe using Whisper API."""
        try:
            # Prepare request
            files = {
                "file": ("audio.wav", audio_data, "audio/wav"),
            }
            data = {
                "language": language,
            }
            
            response = await self.client.post(
                self.settings.whisper_api_url,
                files=files,
                data=data,
            )
            response.raise_for_status()
            
            result = response.json()
            return result.get("text", "").strip()
            
        except httpx.HTTPError as e:
            logger.error(f"Whisper API error: {e}")
            raise
    
    # =========================================================================
    # TEXT-TO-SPEECH
    # =========================================================================
    
    async def text_to_speech(
        self,
        text: str,
        voice: str | None = None,
    ) -> dict[str, Any]:
        """
        Convert text to speech.
        
        Args:
            text: Text to synthesize
            voice: Voice to use (optional, uses default)
            
        Returns:
            Dict with audio_data (base64), duration, and url (if applicable)
        """
        tts_model = self.settings.tts_model.lower()
        voice = voice or self.settings.tts_voice
        
        if tts_model == "kokoro":
            return await self._tts_kokoro(text, voice)
        elif tts_model == "piper":
            return await self._tts_piper(text, voice)
        elif tts_model == "edge-tts":
            return await self._tts_edge(text, voice)
        else:
            # Fallback to edge-tts
            return await self._tts_edge(text, voice)
    
    async def _tts_kokoro(self, text: str, voice: str) -> dict[str, Any]:
        """Generate speech using Kokoro TTS."""
        try:
            import kokoro
            
            # Lazy load model
            if self._tts_model is None:
                logger.info("Loading Kokoro TTS model")
                self._tts_model = kokoro.KokoroTTS()
            
            # Generate audio
            loop = asyncio.get_event_loop()
            audio_data = await loop.run_in_executor(
                None,
                lambda: self._tts_model.generate(text, voice=voice)
            )
            
            # Encode to base64
            audio_b64 = base64.b64encode(audio_data).decode("utf-8")
            
            # Estimate duration (rough: 150 words per minute)
            word_count = len(text.split())
            duration = word_count / 150 * 60  # seconds
            
            return {
                "audio_data": audio_b64,
                "format": "wav",
                "sample_rate": self.settings.tts_rate,
                "duration_seconds": duration,
                "url": None,  # In-memory audio
            }
            
        except ImportError:
            logger.warning("Kokoro not available, falling back to edge-tts")
            return await self._tts_edge(text, voice)
        except Exception as e:
            logger.error(f"Kokoro TTS failed: {e}")
            return await self._tts_edge(text, voice)
    
    async def _tts_piper(self, text: str, voice: str) -> dict[str, Any]:
        """Generate speech using Piper TTS."""
        try:
            import subprocess
            import tempfile
            
            # Create temp file for output
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                output_path = f.name
            
            try:
                # Run piper command
                process = await asyncio.create_subprocess_exec(
                    "piper",
                    "--model", voice,
                    "--output_file", output_path,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                
                await process.communicate(input=text.encode())
                
                # Read output file
                with open(output_path, "rb") as f:
                    audio_data = f.read()
                
                audio_b64 = base64.b64encode(audio_data).decode("utf-8")
                
                # Estimate duration
                word_count = len(text.split())
                duration = word_count / 150 * 60
                
                return {
                    "audio_data": audio_b64,
                    "format": "wav",
                    "sample_rate": self.settings.tts_rate,
                    "duration_seconds": duration,
                    "url": None,
                }
                
            finally:
                Path(output_path).unlink(missing_ok=True)
                
        except Exception as e:
            logger.error(f"Piper TTS failed: {e}")
            return await self._tts_edge(text, voice)
    
    async def _tts_edge(self, text: str, voice: str) -> dict[str, Any]:
        """Generate speech using Edge TTS (Microsoft)."""
        try:
            import edge_tts
            
            # Map voice names to Edge TTS voices
            edge_voices = {
                "male": "en-US-GuyNeural",
                "female": "en-US-JennyNeural",
                "professional": "en-US-AriaNeural",
                "default": "en-US-GuyNeural",
            }
            
            edge_voice = edge_voices.get(voice, edge_voices["default"])
            
            # Generate audio
            communicate = edge_tts.Communicate(text, edge_voice)
            
            # Collect audio chunks
            audio_chunks = []
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_chunks.append(chunk["data"])
            
            audio_data = b"".join(audio_chunks)
            audio_b64 = base64.b64encode(audio_data).decode("utf-8")
            
            # Estimate duration
            word_count = len(text.split())
            duration = word_count / 150 * 60
            
            return {
                "audio_data": audio_b64,
                "format": "mp3",
                "sample_rate": 24000,
                "duration_seconds": duration,
                "url": None,
            }
            
        except ImportError:
            logger.error("edge-tts not installed. Install with: pip install edge-tts")
            # Return empty audio as fallback
            return {
                "audio_data": "",
                "format": "wav",
                "sample_rate": self.settings.tts_rate,
                "duration_seconds": 0,
                "url": None,
                "error": "TTS not available",
            }
        except Exception as e:
            logger.error(f"Edge TTS failed: {e}")
            return {
                "audio_data": "",
                "format": "wav",
                "sample_rate": self.settings.tts_rate,
                "duration_seconds": 0,
                "url": None,
                "error": str(e),
            }
    
    # =========================================================================
    # AUDIO UTILITIES
    # =========================================================================
    
    async def validate_audio(self, audio_data: bytes) -> dict[str, Any]:
        """
        Validate audio data.
        
        Returns:
            Validation result with duration, format, etc.
        """
        try:
            import wave
            
            with io.BytesIO(audio_data) as audio_io:
                with wave.open(audio_io, "rb") as wav:
                    frames = wav.getnframes()
                    rate = wav.getframerate()
                    duration = frames / float(rate)
                    
                    return {
                        "valid": True,
                        "format": "wav",
                        "duration_seconds": duration,
                        "sample_rate": rate,
                        "channels": wav.getnchannels(),
                        "sample_width": wav.getsampwidth(),
                    }
                    
        except Exception as e:
            return {
                "valid": False,
                "error": str(e),
            }
    
    async def convert_to_wav(
        self,
        audio_data: bytes,
        source_format: str
    ) -> bytes:
        """
        Convert audio to WAV format.
        
        Args:
            audio_data: Source audio bytes
            source_format: Source format (mp3, webm, etc.)
            
        Returns:
            WAV audio bytes
        """
        try:
            from pydub import AudioSegment
            
            # Load audio
            audio = AudioSegment.from_file(
                io.BytesIO(audio_data),
                format=source_format,
            )
            
            # Convert to WAV
            output = io.BytesIO()
            audio.export(output, format="wav")
            return output.getvalue()
            
        except ImportError:
            logger.error("pydub not installed for audio conversion")
            raise
        except Exception as e:
            logger.error(f"Audio conversion failed: {e}")
            raise
    
    async def chunk_audio(
        self,
        audio_data: bytes,
        chunk_duration_ms: int = 100
    ) -> list[bytes]:
        """
        Split audio into chunks for streaming.
        
        Args:
            audio_data: Full audio bytes
            chunk_duration_ms: Chunk duration in milliseconds
            
        Returns:
            List of audio chunks
        """
        try:
            from pydub import AudioSegment
            
            audio = AudioSegment.from_file(io.BytesIO(audio_data), format="wav")
            chunks = []
            
            for i in range(0, len(audio), chunk_duration_ms):
                chunk = audio[i:i + chunk_duration_ms]
                chunk_io = io.BytesIO()
                chunk.export(chunk_io, format="wav")
                chunks.append(chunk_io.getvalue())
            
            return chunks
            
        except ImportError:
            # Return whole audio as single chunk
            return [audio_data]
