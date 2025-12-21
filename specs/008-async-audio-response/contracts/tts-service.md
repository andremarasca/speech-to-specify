# Contract: TTS Service

**Feature**: 008-async-audio-response  
**Date**: 2025-12-21  
**Location**: `src/services/tts/base.py`

## Interface Definition

```python
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

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
        >>> service = EdgeTTSService(config, sessions_path)
        >>> result = await service.synthesize(request)
        >>> if result.success:
        ...     print(f"Audio saved to {result.file_path}")
    """
    
    @abstractmethod
    async def synthesize(self, request: TTSRequest) -> TTSResult:
        """Synthesize speech from text.
        
        This method MUST be idempotent: identical requests return
        cached results without re-processing.
        
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
```

## Behavioral Contract

### BC-TTS-001: Asynchronous Non-Blocking

**Rule**: `synthesize()` MUST NOT block the calling coroutine beyond timeout.

**Test**:
```python
async def test_synthesize_respects_timeout():
    config = TTSConfig(timeout_seconds=5)
    service = EdgeTTSService(config, sessions_path)
    
    start = time.time()
    result = await service.synthesize(long_text_request)
    elapsed = time.time() - start
    
    # Either succeeds within timeout or returns timeout error
    assert elapsed <= config.timeout_seconds + 1
    if not result.success:
        assert "timeout" in result.error_message.lower()
```

### BC-TTS-002: Idempotency

**Rule**: Identical requests MUST return cached result without re-synthesis.

**Test**:
```python
async def test_synthesize_is_idempotent():
    service = EdgeTTSService(config, sessions_path)
    request = TTSRequest(text="Hello", session_id="...", ...)
    
    # First call - synthesis
    result1 = await service.synthesize(request)
    assert result1.success
    assert not result1.cached
    
    # Second call - cached
    result2 = await service.synthesize(request)
    assert result2.success
    assert result2.cached
    assert result2.file_path == result1.file_path
```

### BC-TTS-003: Error Isolation

**Rule**: Synthesis failures MUST NOT raise exceptions to caller.

**Test**:
```python
async def test_synthesize_returns_error_not_exception():
    service = EdgeTTSService(config, sessions_path)
    
    # Invalid request that would fail
    request = TTSRequest(text="", ...)  # Empty text
    
    # Should not raise, should return error result
    result = await service.synthesize(request)
    assert not result.success
    assert result.error_message is not None
```

### BC-TTS-004: Text Sanitization

**Rule**: Input text MUST be sanitized before synthesis (markdown removed, special chars replaced).

**Test**:
```python
async def test_synthesize_sanitizes_markdown():
    service = EdgeTTSService(config, sessions_path)
    
    # Text with markdown
    request = TTSRequest(text="**Bold** and `code`", ...)
    result = await service.synthesize(request)
    
    assert result.success
    # Audio should not contain markdown artifacts
    # (verified by listening or speech-to-text validation)
```

### BC-TTS-005: File Persistence

**Rule**: Successful synthesis MUST persist audio to session's tts/ directory.

**Test**:
```python
async def test_synthesize_persists_to_correct_path():
    service = EdgeTTSService(config, sessions_path)
    request = TTSRequest(
        text="Test",
        session_id="2025-12-21_12-00-00",
        sequence=1,
        oracle_name="cetico",
        oracle_id="cetico",
    )
    
    result = await service.synthesize(request)
    
    assert result.success
    expected_path = sessions_path / "2025-12-21_12-00-00" / "audio" / "tts" / "001_cetico.ogg"
    assert result.file_path == expected_path
    assert result.file_path.exists()
```

### BC-TTS-006: Configuration Respect

**Rule**: Service MUST use voice, format, and timeout from TTSConfig.

**Test**:
```python
async def test_synthesize_uses_configured_voice():
    config = TTSConfig(voice="pt-BR-FranciscaNeural", format="mp3")
    service = EdgeTTSService(config, sessions_path)
    request = TTSRequest(text="Test", ...)
    
    result = await service.synthesize(request)
    
    assert result.success
    assert result.file_path.suffix == ".mp3"
    # Voice verified by audio content characteristics
```

## Implementation: EdgeTTSService

```python
# src/services/tts/edge_tts_service.py

import asyncio
import logging
import time
from pathlib import Path

import edge_tts

from src.models.tts import TTSRequest, TTSResult
from src.services.tts.base import TTSService
from src.services.tts.text_sanitizer import sanitize_for_speech
from src.lib.config import TTSConfig

logger = logging.getLogger(__name__)


class EdgeTTSService(TTSService):
    """TTS implementation using Microsoft Edge TTS.
    
    Per research.md: edge-tts selected for quality, cost (free),
    and native pt-BR support.
    """
    
    def __init__(self, config: TTSConfig, sessions_path: Path):
        self._config = config
        self._sessions_path = sessions_path
    
    async def synthesize(self, request: TTSRequest) -> TTSResult:
        start_time = time.time()
        
        # Check if disabled
        if not self._config.enabled:
            return TTSResult.error("TTS is disabled")
        
        # Check idempotency
        artifact_path = self.get_artifact_path(request)
        if artifact_path.exists():
            duration_ms = int((time.time() - start_time) * 1000)
            return TTSResult.ok(artifact_path, duration_ms, cached=True)
        
        # Sanitize text
        clean_text = sanitize_for_speech(request.text)
        if not clean_text.strip():
            return TTSResult.error("Text is empty after sanitization")
        
        # Validate length
        if len(clean_text) > self._config.max_text_length:
            return TTSResult.error(
                f"Text exceeds maximum length ({len(clean_text)} > {self._config.max_text_length})"
            )
        
        # Ensure directory exists
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            # Synthesize with timeout
            communicate = edge_tts.Communicate(clean_text, self._config.voice)
            await asyncio.wait_for(
                communicate.save(str(artifact_path)),
                timeout=self._config.timeout_seconds,
            )
            
            duration_ms = int((time.time() - start_time) * 1000)
            logger.info(f"TTS synthesis complete: {artifact_path} ({duration_ms}ms)")
            return TTSResult.ok(artifact_path, duration_ms)
            
        except asyncio.TimeoutError:
            logger.warning(f"TTS synthesis timed out after {self._config.timeout_seconds}s")
            return TTSResult.timeout(self._config.timeout_seconds)
            
        except Exception as e:
            logger.error(f"TTS synthesis failed: {e}")
            return TTSResult.error(str(e))
    
    async def check_health(self) -> bool:
        if not self._config.enabled:
            return False
        try:
            # Quick synthesis test
            communicate = edge_tts.Communicate("test", self._config.voice)
            async for _ in communicate.stream():
                return True
            return True
        except Exception:
            return False
    
    def get_artifact_path(self, request: TTSRequest) -> Path:
        session_path = self._sessions_path / request.session_id
        tts_dir = session_path / "audio" / "tts"
        return tts_dir / request.filename
```

## Test File Location

Tests implementing these contracts go in:
- `tests/contract/test_tts_service_contract.py`
