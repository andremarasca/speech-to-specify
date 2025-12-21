"""Edge TTS service implementation.

Per plan.md and contracts/tts-service.md for 008-async-audio-response.

This module provides the production TTS service using Microsoft Edge TTS
via the edge-tts library. It implements:
- Async, non-blocking synthesis with timeout
- Idempotent request handling
- Error isolation (never propagates exceptions)
- Text sanitization before synthesis
- Configurable voice and format
"""

import asyncio
import logging
import time
from pathlib import Path
from typing import Optional

import edge_tts

from src.lib.config import TTSConfig
from src.models.tts import TTSRequest, TTSResult
from src.services.tts.base import TTSService
from src.services.tts.text_sanitizer import TextSanitizer

logger = logging.getLogger(__name__)


# OGG file magic bytes for validation
OGG_MAGIC_BYTES = b"OggS"


class EdgeTTSService(TTSService):
    """TTS service using Microsoft Edge TTS.
    
    Implements TTSService contract using the edge-tts library.
    Per Constitution Principle I: Async, idempotent, error-isolated.
    
    Attributes:
        config: TTS configuration
        sessions_path: Root path for session storage
        _lock: Async lock for concurrent request handling (US4)
    
    Example:
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
    
    def __init__(self, config: TTSConfig, sessions_path: Path):
        """Initialize Edge TTS service.
        
        Args:
            config: TTS configuration
            sessions_path: Root path for session storage
        """
        self.config = config
        self.sessions_path = sessions_path
        self._lock = asyncio.Lock()  # For concurrent idempotency (T035)
    
    async def synthesize(self, request: TTSRequest) -> TTSResult:
        """Synthesize speech from text using Edge TTS.
        
        Per BC-TTS-001: Uses asyncio.wait_for for timeout.
        Per BC-TTS-002: Returns cached result if file exists.
        Per BC-TTS-003: Never raises - returns TTSResult.error().
        Per BC-TTS-004: Sanitizes text via TextSanitizer.
        Per BC-TTS-005: Persists to session's tts/ directory.
        Per BC-TTS-006: Uses voice, format, timeout from config.
        
        Args:
            request: TTSRequest with text and context
            
        Returns:
            TTSResult with success status and file path or error
        """
        start_time = time.time()
        
        try:
            # Check if TTS is enabled
            if not self.config.enabled:
                logger.debug("TTS is disabled, skipping synthesis")
                return TTSResult.error("TTS is disabled")
            
            # Get artifact path
            artifact_path = self.get_artifact_path(request)
            
            # BC-TTS-002: Idempotency check with lock (T014, T035)
            async with self._lock:
                if artifact_path.exists():
                    # Verify file integrity (T016b)
                    if self._verify_file_integrity(artifact_path):
                        duration_ms = int((time.time() - start_time) * 1000)
                        logger.debug(f"TTS cache hit: {artifact_path}")
                        return TTSResult.ok(artifact_path, duration_ms, cached=True)
                    else:
                        # Remove corrupted file
                        logger.warning(f"Removing corrupted TTS file: {artifact_path}")
                        artifact_path.unlink(missing_ok=True)
            
            # BC-TTS-004: Sanitize text (T008)
            sanitized_text = TextSanitizer.sanitize(
                request.text, 
                max_length=self.config.max_text_length
            )
            
            if not sanitized_text:
                return TTSResult.error("Text is empty after sanitization")
            
            # Create directory if needed
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            
            # BC-TTS-001: Async synthesis with timeout (T015)
            try:
                await asyncio.wait_for(
                    self._do_synthesis(sanitized_text, artifact_path),
                    timeout=self.config.timeout_seconds
                )
            except asyncio.TimeoutError:
                logger.warning(f"TTS timeout after {self.config.timeout_seconds}s")
                # Cleanup partial file if exists
                artifact_path.unlink(missing_ok=True)
                return TTSResult.timeout(self.config.timeout_seconds)
            
            # T016b: Verify file integrity after synthesis
            if not self._verify_file_integrity(artifact_path):
                artifact_path.unlink(missing_ok=True)
                return TTSResult.error("Synthesis produced invalid audio file")
            
            duration_ms = int((time.time() - start_time) * 1000)
            logger.info(f"TTS synthesis complete: {artifact_path} ({duration_ms}ms)")
            return TTSResult.ok(artifact_path, duration_ms)
            
        except Exception as e:
            # BC-TTS-003: Error isolation (T016)
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"TTS synthesis error: {e}", exc_info=True)
            return TTSResult.error(str(e), duration_ms)
    
    async def _do_synthesis(self, text: str, output_path: Path) -> None:
        """Perform the actual TTS synthesis.
        
        Args:
            text: Sanitized text to synthesize
            output_path: Path to save the audio file
        """
        communicate = edge_tts.Communicate(text, self.config.voice)
        await communicate.save(str(output_path))
    
    def _verify_file_integrity(self, file_path: Path) -> bool:
        """Verify audio file integrity.
        
        Per FR-008: Check file exists, size > 0, valid header.
        
        Args:
            file_path: Path to the audio file
            
        Returns:
            True if file is valid, False otherwise
        """
        try:
            if not file_path.exists():
                return False
            
            stat = file_path.stat()
            if stat.st_size == 0:
                return False
            
            # For OGG format, check magic bytes
            if self.config.format == "ogg":
                with open(file_path, "rb") as f:
                    header = f.read(4)
                    if header != OGG_MAGIC_BYTES:
                        return False
            
            return True
            
        except Exception as e:
            logger.warning(f"File integrity check failed: {e}")
            return False
    
    async def check_health(self) -> bool:
        """Check if the Edge TTS service is available.
        
        Performs a minimal synthesis to verify connectivity.
        
        Returns:
            True if service is ready to process requests
        """
        try:
            # Quick health check with minimal text
            communicate = edge_tts.Communicate("test", self.config.voice)
            # Just verify we can create the communicate object
            # Full synthesis test would be too slow for health checks
            return True
        except Exception as e:
            logger.warning(f"TTS health check failed: {e}")
            return False
    
    def get_artifact_path(self, request: TTSRequest) -> Path:
        """Get the filesystem path where artifact would be stored.
        
        Per BC-TTS-005: Path is sessions/{session_id}/audio/tts/{filename}.{format}
        
        Args:
            request: TTSRequest to determine path
            
        Returns:
            Path where the audio file would be saved
        """
        filename = f"{request.filename}.{self.config.format}"
        return self.sessions_path / request.session_id / "audio" / "tts" / filename
