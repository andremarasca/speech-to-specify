"""Mock TTS service for testing.

Per plan.md for 008-async-audio-response.

This module provides a mock implementation of TTSService
that can be used in tests without making network calls.
"""

import asyncio
import time
from pathlib import Path
from typing import Optional

from src.lib.config import TTSConfig
from src.models.tts import TTSRequest, TTSResult
from src.services.tts.base import TTSService


class MockTTSService(TTSService):
    """Mock TTS service for testing without network calls.
    
    This service simulates TTS synthesis by creating small
    placeholder audio files. Useful for:
    - Unit tests
    - Integration tests
    - Development without edge-tts
    
    Attributes:
        config: TTS configuration
        sessions_path: Root path for session storage
        simulate_delay: Delay in seconds to simulate processing
        simulate_failure: If True, always return error
        simulate_timeout: If True, simulate timeout
        health_status: Current health check result
    
    Example:
        >>> config = TTSConfig()
        >>> service = MockTTSService(config, Path("./sessions"))
        >>> result = await service.synthesize(request)
        >>> assert result.success
    """
    
    def __init__(
        self,
        config: TTSConfig,
        sessions_path: Path,
        simulate_delay: float = 0.1,
        simulate_failure: bool = False,
        simulate_timeout: bool = False,
    ):
        """Initialize mock TTS service.
        
        Args:
            config: TTS configuration
            sessions_path: Root path for session storage
            simulate_delay: Delay in seconds to simulate processing
            simulate_failure: If True, always return error
            simulate_timeout: If True, simulate timeout
        """
        self.config = config
        self.sessions_path = sessions_path
        self.simulate_delay = simulate_delay
        self.simulate_failure = simulate_failure
        self.simulate_timeout = simulate_timeout
        self.health_status = True
        self._synthesis_count = 0
        self._cache_hits = 0
    
    async def synthesize(self, request: TTSRequest) -> TTSResult:
        """Synthesize speech from text (mock implementation).
        
        Creates a small placeholder file instead of actual audio.
        Implements idempotency: returns cached result if file exists.
        
        Args:
            request: TTSRequest with text and context
            
        Returns:
            TTSResult with success status and file path or error
        """
        start_time = time.time()
        
        try:
            # Check if TTS is enabled
            if not self.config.enabled:
                return TTSResult.error("TTS is disabled")
            
            # Get artifact path
            artifact_path = self.get_artifact_path(request)
            
            # BC-TTS-002: Idempotency check - return cached if exists
            if artifact_path.exists():
                self._cache_hits += 1
                duration_ms = int((time.time() - start_time) * 1000)
                return TTSResult.ok(artifact_path, duration_ms, cached=True)
            
            # Simulate delay
            if self.simulate_delay:
                await asyncio.sleep(self.simulate_delay)
            
            # Simulate timeout
            if self.simulate_timeout:
                return TTSResult.timeout(self.config.timeout_seconds)
            
            # Simulate failure
            if self.simulate_failure:
                duration_ms = int((time.time() - start_time) * 1000)
                return TTSResult.error("Simulated TTS failure", duration_ms)
            
            # Create directory if needed
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create placeholder file (not actual audio)
            # In tests, this is sufficient to verify file creation
            placeholder_content = f"MOCK_TTS_AUDIO:{request.text[:100]}"
            artifact_path.write_bytes(placeholder_content.encode())
            
            self._synthesis_count += 1
            duration_ms = int((time.time() - start_time) * 1000)
            return TTSResult.ok(artifact_path, duration_ms)
            
        except Exception as e:
            # BC-TTS-003: Error isolation - never raise, return error result
            duration_ms = int((time.time() - start_time) * 1000)
            return TTSResult.error(str(e), duration_ms)
    
    async def check_health(self) -> bool:
        """Check if the mock TTS service is available.
        
        Returns:
            Current health_status value (configurable for tests)
        """
        return self.health_status
    
    def get_artifact_path(self, request: TTSRequest) -> Path:
        """Get the filesystem path where artifact would be stored.
        
        Args:
            request: TTSRequest to determine path
            
        Returns:
            Path where the audio file would be saved
        """
        # Path: sessions/{session_id}/audio/tts/{sequence}_{oracle_name}.{format}
        filename = f"{request.filename}.{self.config.format}"
        return self.sessions_path / request.session_id / "audio" / "tts" / filename
    
    # Test helper methods
    
    def reset_stats(self) -> None:
        """Reset synthesis statistics (for testing)."""
        self._synthesis_count = 0
        self._cache_hits = 0
    
    @property
    def synthesis_count(self) -> int:
        """Number of successful syntheses (excluding cache hits)."""
        return self._synthesis_count
    
    @property
    def cache_hits(self) -> int:
        """Number of cache hits (idempotent returns)."""
        return self._cache_hits
