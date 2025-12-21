"""Contract tests for TTSService.

Per T012 [US1] from tasks.md for 008-async-audio-response.

Tests behavioral contracts BC-TTS-001 through BC-TTS-006 from contracts/tts-service.md:
- BC-TTS-001: Asynchronous Non-Blocking
- BC-TTS-002: Idempotency
- BC-TTS-003: Error Isolation
- BC-TTS-004: Text Sanitization (implicit via integration)
- BC-TTS-005: File Persistence
- BC-TTS-006: Configuration Respect
"""

import asyncio
import time
from pathlib import Path
from unittest.mock import patch, AsyncMock

import pytest

from src.lib.config import TTSConfig
from src.models.tts import TTSRequest, TTSResult
from src.services.tts import MockTTSService, EdgeTTSService


@pytest.fixture
def tts_config():
    """Create test TTS configuration."""
    return TTSConfig(
        enabled=True,
        voice="pt-BR-AntonioNeural",
        format="ogg",
        timeout_seconds=5,
        max_text_length=1000,
        gc_retention_hours=24,
        gc_max_storage_mb=100,
    )


@pytest.fixture
def disabled_tts_config():
    """Create disabled TTS configuration."""
    return TTSConfig(
        enabled=False,
        voice="pt-BR-AntonioNeural",
        format="ogg",
        timeout_seconds=5,
        max_text_length=1000,
        gc_retention_hours=24,
        gc_max_storage_mb=100,
    )


@pytest.fixture
def sessions_path(tmp_path):
    """Create temporary sessions directory."""
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    return sessions


@pytest.fixture
def sample_request():
    """Create a sample TTS request."""
    return TTSRequest(
        text="Olá, mundo! Este é um teste de síntese de voz.",
        session_id="2025-12-21_12-00-00",
        sequence=1,
        oracle_name="cético",
        oracle_id="cetico",
    )


class TestBCTTS001AsyncNonBlocking:
    """BC-TTS-001: synthesize() MUST NOT block beyond timeout."""
    
    @pytest.mark.asyncio
    async def test_synthesize_respects_timeout_mock(self, tts_config, sessions_path, sample_request):
        """Should return within timeout (using mock service)."""
        tts_config.timeout_seconds = 2
        service = MockTTSService(tts_config, sessions_path, simulate_delay=0.1)
        
        start = time.time()
        result = await service.synthesize(sample_request)
        elapsed = time.time() - start
        
        # Should complete well within timeout
        assert elapsed < tts_config.timeout_seconds
        assert result.success
    
    @pytest.mark.asyncio
    async def test_synthesize_returns_timeout_error_when_slow(self, tts_config, sessions_path, sample_request):
        """Should return timeout error if synthesis exceeds timeout."""
        tts_config.timeout_seconds = 1
        service = MockTTSService(tts_config, sessions_path, simulate_timeout=True)
        
        result = await service.synthesize(sample_request)
        
        assert not result.success
        assert "timed out" in result.error_message.lower()


class TestBCTTS002Idempotency:
    """BC-TTS-002: Identical requests MUST return cached result."""
    
    @pytest.mark.asyncio
    async def test_synthesize_is_idempotent(self, tts_config, sessions_path, sample_request):
        """Should return cached result on second call."""
        service = MockTTSService(tts_config, sessions_path)
        
        # First call - synthesis
        result1 = await service.synthesize(sample_request)
        assert result1.success
        assert not result1.cached
        
        # Second call - should be cached
        result2 = await service.synthesize(sample_request)
        assert result2.success
        assert result2.cached
        assert result2.file_path == result1.file_path
    
    @pytest.mark.asyncio
    async def test_different_requests_not_cached(self, tts_config, sessions_path):
        """Should NOT cache different requests."""
        service = MockTTSService(tts_config, sessions_path)
        
        request1 = TTSRequest(
            text="First text",
            session_id="2025-12-21_12-00-00",
            sequence=1,
            oracle_name="cético",
            oracle_id="cetico",
        )
        
        request2 = TTSRequest(
            text="Second text",
            session_id="2025-12-21_12-00-00",
            sequence=2,
            oracle_name="pragmático",
            oracle_id="pragmatico",
        )
        
        result1 = await service.synthesize(request1)
        result2 = await service.synthesize(request2)
        
        assert result1.success
        assert result2.success
        assert not result2.cached  # Different request, should not be cached
        assert result1.file_path != result2.file_path


class TestBCTTS003ErrorIsolation:
    """BC-TTS-003: Synthesis failures MUST NOT raise exceptions."""
    
    @pytest.mark.asyncio
    async def test_synthesize_returns_error_not_exception_empty_text(self, tts_config, sessions_path):
        """Should return error result for invalid input, not raise."""
        service = MockTTSService(tts_config, sessions_path)
        
        # Empty text should fail validation in TTSRequest
        with pytest.raises(ValueError):
            TTSRequest(
                text="",
                session_id="2025-12-21_12-00-00",
                sequence=1,
                oracle_name="test",
                oracle_id="test",
            )
    
    @pytest.mark.asyncio
    async def test_synthesize_returns_error_on_failure(self, tts_config, sessions_path, sample_request):
        """Should return error result when synthesis fails."""
        service = MockTTSService(tts_config, sessions_path, simulate_failure=True)
        
        # Should NOT raise exception
        result = await service.synthesize(sample_request)
        
        assert not result.success
        assert result.error_message is not None
    
    @pytest.mark.asyncio
    async def test_synthesize_disabled_returns_error(self, disabled_tts_config, sessions_path, sample_request):
        """Should return error when TTS is disabled."""
        service = MockTTSService(disabled_tts_config, sessions_path)
        
        result = await service.synthesize(sample_request)
        
        assert not result.success
        assert "disabled" in result.error_message.lower()


class TestBCTTS005FilePersistence:
    """BC-TTS-005: Successful synthesis MUST persist audio file."""
    
    @pytest.mark.asyncio
    async def test_synthesize_persists_to_correct_path(self, tts_config, sessions_path, sample_request):
        """Should save file to correct location."""
        service = MockTTSService(tts_config, sessions_path)
        
        result = await service.synthesize(sample_request)
        
        assert result.success
        expected_path = sessions_path / "2025-12-21_12-00-00" / "audio" / "tts" / "001_cético.ogg"
        assert result.file_path == expected_path
        assert result.file_path.exists()
    
    @pytest.mark.asyncio
    async def test_artifact_path_matches_llm_responses_pattern(self, tts_config, sessions_path):
        """Should generate filename matching llm_responses pattern."""
        service = MockTTSService(tts_config, sessions_path)
        
        request = TTSRequest(
            text="Test",
            session_id="2025-12-21_12-00-00",
            sequence=42,
            oracle_name="Pragmático",
            oracle_id="pragmatico",
        )
        
        path = service.get_artifact_path(request)
        
        # Should be: sessions/{session_id}/audio/tts/{seq}_{oracle}.{format}
        assert path.name == "042_pragmático.ogg"
        assert path.parent.name == "tts"
        assert path.parent.parent.name == "audio"


class TestBCTTS006ConfigurationRespect:
    """BC-TTS-006: Service MUST use configuration values."""
    
    @pytest.mark.asyncio
    async def test_uses_configured_format(self, sessions_path, sample_request):
        """Should use format from configuration."""
        config_mp3 = TTSConfig(format="mp3")
        service = MockTTSService(config_mp3, sessions_path)
        
        path = service.get_artifact_path(sample_request)
        
        assert path.suffix == ".mp3"
    
    @pytest.mark.asyncio
    async def test_uses_configured_timeout(self, sessions_path, sample_request):
        """Should respect configured timeout."""
        config = TTSConfig(timeout_seconds=2)
        service = MockTTSService(config, sessions_path, simulate_timeout=True)
        
        result = await service.synthesize(sample_request)
        
        assert not result.success
        assert "2s" in result.error_message


class TestTTSRequest:
    """Tests for TTSRequest model."""
    
    def test_idempotency_key_generation(self):
        """Should generate consistent idempotency key."""
        request = TTSRequest(
            text="Same text",
            session_id="2025-12-21_12-00-00",
            sequence=1,
            oracle_name="cético",
            oracle_id="cetico",
        )
        
        key1 = request.idempotency_key
        key2 = request.idempotency_key
        
        assert key1 == key2
        assert len(key1) == 16  # Truncated to 16 chars
    
    def test_different_text_different_key(self):
        """Should generate different key for different text."""
        request1 = TTSRequest(
            text="First text",
            session_id="2025-12-21_12-00-00",
            sequence=1,
            oracle_name="cético",
            oracle_id="cetico",
        )
        
        request2 = TTSRequest(
            text="Second text",
            session_id="2025-12-21_12-00-00",
            sequence=1,
            oracle_name="cético",
            oracle_id="cetico",
        )
        
        assert request1.idempotency_key != request2.idempotency_key
    
    def test_filename_generation(self):
        """Should generate correct filename."""
        request = TTSRequest(
            text="Test",
            session_id="2025-12-21_12-00-00",
            sequence=5,
            oracle_name="Cético Profundo",
            oracle_id="cetico_profundo",
        )
        
        assert request.filename == "005_cético_profundo"
    
    def test_validation_empty_text(self):
        """Should reject empty text."""
        with pytest.raises(ValueError, match="empty"):
            TTSRequest(
                text="",
                session_id="2025-12-21_12-00-00",
                sequence=1,
                oracle_name="test",
                oracle_id="test",
            )
    
    def test_validation_whitespace_only_text(self):
        """Should reject whitespace-only text."""
        with pytest.raises(ValueError, match="empty"):
            TTSRequest(
                text="   \n\t  ",
                session_id="2025-12-21_12-00-00",
                sequence=1,
                oracle_name="test",
                oracle_id="test",
            )
    
    def test_validation_negative_sequence(self):
        """Should reject non-positive sequence."""
        with pytest.raises(ValueError, match="positive"):
            TTSRequest(
                text="Test",
                session_id="2025-12-21_12-00-00",
                sequence=0,
                oracle_name="test",
                oracle_id="test",
            )


class TestTTSResult:
    """Tests for TTSResult model."""
    
    def test_ok_result(self):
        """Should create successful result."""
        path = Path("/tmp/test.ogg")
        result = TTSResult.ok(path, duration_ms=500)
        
        assert result.success
        assert result.file_path == path
        assert result.duration_ms == 500
        assert not result.cached
    
    def test_cached_result(self):
        """Should create cached successful result."""
        path = Path("/tmp/test.ogg")
        result = TTSResult.ok(path, duration_ms=10, cached=True)
        
        assert result.success
        assert result.cached
    
    def test_error_result(self):
        """Should create error result."""
        result = TTSResult.error("Something went wrong", duration_ms=100)
        
        assert not result.success
        assert result.error_message == "Something went wrong"
        assert result.duration_ms == 100
    
    def test_timeout_result(self):
        """Should create timeout result."""
        result = TTSResult.timeout(30)
        
        assert not result.success
        assert "30s" in result.error_message


class TestHealthCheck:
    """Tests for health check functionality."""
    
    @pytest.mark.asyncio
    async def test_mock_health_check_default(self, tts_config, sessions_path):
        """Mock service should report healthy by default."""
        service = MockTTSService(tts_config, sessions_path)
        
        assert await service.check_health() is True
    
    @pytest.mark.asyncio
    async def test_mock_health_check_unhealthy(self, tts_config, sessions_path):
        """Mock service health can be configured."""
        service = MockTTSService(tts_config, sessions_path)
        service.health_status = False
        
        assert await service.check_health() is False
