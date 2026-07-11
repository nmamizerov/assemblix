"""Server-side voice support (speech-to-text; TTS/realtime reserved for later)."""

from assemblix_api.external.voice.transcription import Transcript, transcribe

__all__ = ["Transcript", "transcribe"]
