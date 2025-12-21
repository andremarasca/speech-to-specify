"""TTS (Text-to-Speech) service package.

Per plan.md for 008-async-audio-response.

This package provides text-to-speech synthesis services with:
- Async, non-blocking synthesis
- Idempotent request handling
- Error isolation (never propagates exceptions)
- Configurable voice and format
- Garbage collection for audio artifacts

Example:
    >>> from src.services.tts import EdgeTTSService
    >>> from src.lib.config import get_tts_config, get_session_config
    >>> 
    >>> config = get_tts_config()
    >>> sessions_path = get_session_config().sessions_path
    >>> service = EdgeTTSService(config, sessions_path)
    >>> 
    >>> request = TTSRequest(
    ...     text="Olá, mundo!",
    ...     session_id="2025-12-21_12-00-00",
    ...     sequence=1,
    ...     oracle_name="cético",
    ...     oracle_id="cetico",
    ... )
    >>> result = await service.synthesize(request)
    >>> if result.success:
    ...     print(f"Audio saved to {result.file_path}")
"""

from src.services.tts.base import TTSService
from src.services.tts.text_sanitizer import TextSanitizer
from src.services.tts.mock_service import MockTTSService
from src.services.tts.edge_tts_service import EdgeTTSService
from src.services.tts.garbage_collector import TTSGarbageCollector

__all__ = [
    "TTSService",
    "TextSanitizer",
    "MockTTSService",
    "EdgeTTSService",
    "TTSGarbageCollector",
]
