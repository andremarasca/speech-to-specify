"""Abstract base class for Text-to-Speech services.

Per contracts/tts-service.md for 008-async-audio-response.

This module defines the TTSService interface that all TTS implementations
must follow. The interface enforces:
- Async, non-blocking synthesis
- Idempotency (identical requests return cached results)
- Error isolation (never raises exceptions to caller)
"""

from abc import ABC, abstractmethod
from pathlib import Path

from src.models.tts import TTSRequest, TTSResult


class TTSService(ABC):
    """Abstract base class for Text-to-Speech services.
    
    Per Constitution Principle I (Excelência Estrutural):
    The TTS service operates as an async, idempotent component
    isolated by clear interface contracts.
    
    Implementations:
        - EdgeTTSService: Microsoft Edge TTS via edge-tts library
        - MockTTSService: For testing without network calls
    
    Example:
        >>> from src.services.tts import EdgeTTSService
        >>> from src.lib.config import get_tts_config, get_session_config
        >>> 
        >>> config = get_tts_config()
        >>> sessions_path = get_session_config().sessions_path
        >>> service = EdgeTTSService(config, sessions_path)
        >>> 
        >>> result = await service.synthesize(request)
        >>> if result.success:
        ...     print(f"Audio saved to {result.file_path}")
    """
    
    @abstractmethod
    async def synthesize(self, request: TTSRequest) -> TTSResult:
        """Synthesize speech from text.
        
        This method MUST be idempotent: identical requests return
        cached results without re-processing.
        
        Per BC-TTS-001: MUST NOT block beyond timeout.
        Per BC-TTS-002: MUST return cached result if file exists.
        Per BC-TTS-003: MUST NOT raise exceptions - return TTSResult.error().
        Per BC-TTS-004: MUST sanitize text before synthesis.
        Per BC-TTS-005: MUST persist audio to session's tts/ directory.
        Per BC-TTS-006: MUST use voice, format, timeout from TTSConfig.
        
        Args:
            request: TTSRequest with text and context
            
        Returns:
            TTSResult with success status and file path or error
            
        Raises:
            Does NOT raise exceptions - all errors returned in TTSResult
        """
        pass
    
    @abstractmethod
    async def check_health(self) -> bool:
        """Check if the TTS service is available.
        
        Returns:
            True if service is ready to process requests
        """
        pass
    
    @abstractmethod
    def get_artifact_path(self, request: TTSRequest) -> Path:
        """Get the filesystem path where artifact would be stored.
        
        Used for idempotency checks and pre-existence validation.
        
        Args:
            request: TTSRequest to determine path
            
        Returns:
            Path where the audio file would be saved
        """
        pass
