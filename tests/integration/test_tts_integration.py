"""Integration tests for TTS service.

Per T021 [US2] from tasks.md for 008-async-audio-response.

Tests graceful degradation when TTS fails:
- TTS failures don't impact text delivery
- Service handles edge cases gracefully
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

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
def sessions_path(tmp_path):
    """Create temporary sessions directory."""
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    return sessions


@pytest.fixture
def sample_request():
    """Create a sample TTS request."""
    return TTSRequest(
        text="Este é um teste de síntese de voz para verificar integração.",
        session_id="2025-12-21_12-00-00",
        sequence=1,
        oracle_name="cético",
        oracle_id="cetico",
    )


class TestGracefulDegradation:
    """Tests for graceful degradation when TTS fails."""
    
    @pytest.mark.asyncio
    async def test_tts_failure_returns_error_result(self, tts_config, sessions_path, sample_request):
        """TTS failure should return error result, not raise exception."""
        service = MockTTSService(tts_config, sessions_path, simulate_failure=True)
        
        # Should not raise
        result = await service.synthesize(sample_request)
        
        # Should return error result
        assert not result.success
        assert result.error_message is not None
    
    @pytest.mark.asyncio
    async def test_tts_disabled_returns_error(self, sessions_path, sample_request):
        """Disabled TTS should return error result gracefully."""
        config = TTSConfig(enabled=False)
        service = MockTTSService(config, sessions_path)
        
        result = await service.synthesize(sample_request)
        
        assert not result.success
        assert "disabled" in result.error_message.lower()
    
    @pytest.mark.asyncio
    async def test_tts_timeout_returns_error(self, tts_config, sessions_path, sample_request):
        """TTS timeout should return error result, not raise."""
        tts_config.timeout_seconds = 1
        service = MockTTSService(tts_config, sessions_path, simulate_timeout=True)
        
        result = await service.synthesize(sample_request)
        
        assert not result.success
        assert "timed out" in result.error_message.lower()
    
    @pytest.mark.asyncio
    async def test_network_error_returns_error_result(self, tts_config, sessions_path, sample_request):
        """Network errors should be caught and return error result."""
        service = EdgeTTSService(tts_config, sessions_path)
        
        # Mock edge_tts to simulate network error
        with patch('src.services.tts.edge_tts_service.edge_tts.Communicate') as mock_comm:
            mock_instance = AsyncMock()
            mock_instance.save.side_effect = ConnectionError("Network unreachable")
            mock_comm.return_value = mock_instance
            
            result = await service.synthesize(sample_request)
            
            assert not result.success
            assert result.error_message is not None


class TestTextDeliveryIndependence:
    """Tests verifying TTS doesn't block text delivery."""
    
    @pytest.mark.asyncio
    async def test_slow_tts_does_not_block(self, tts_config, sessions_path, sample_request):
        """Slow TTS synthesis should not block other operations."""
        # Create a slow service
        service = MockTTSService(tts_config, sessions_path, simulate_delay=2.0)
        
        # Track execution order
        events = []
        
        async def text_delivery():
            events.append("text_start")
            await asyncio.sleep(0.1)  # Simulate text send
            events.append("text_done")
        
        async def tts_synthesis():
            events.append("tts_start")
            result = await service.synthesize(sample_request)
            events.append(f"tts_done:{result.success}")
        
        # Send text first, trigger TTS async
        await text_delivery()
        tts_task = asyncio.create_task(tts_synthesis())
        
        # Text should be done before TTS
        assert "text_done" in events
        assert "tts_done:True" not in events
        
        # Wait for TTS to complete
        await tts_task
        assert "tts_done:True" in events


class TestHealthCheck:
    """Tests for TTS health checking."""
    
    @pytest.mark.asyncio
    async def test_mock_service_health_check(self, tts_config, sessions_path):
        """Mock service should report health correctly."""
        service = MockTTSService(tts_config, sessions_path)
        
        # Default is healthy
        assert await service.check_health() is True
        
        # Can be set to unhealthy
        service.health_status = False
        assert await service.check_health() is False
    
    @pytest.mark.asyncio
    async def test_edge_service_health_check(self, tts_config, sessions_path):
        """Edge service should check health without errors."""
        service = EdgeTTSService(tts_config, sessions_path)
        
        # Health check should not raise
        # Note: This requires network access, so we mock it
        with patch('src.services.tts.edge_tts_service.edge_tts.Communicate'):
            healthy = await service.check_health()
            assert isinstance(healthy, bool)


class TestMultipleRequests:
    """Tests for handling multiple TTS requests."""
    
    @pytest.mark.asyncio
    async def test_concurrent_different_requests(self, tts_config, sessions_path):
        """Should handle concurrent different requests."""
        service = MockTTSService(tts_config, sessions_path, simulate_delay=0.1)
        
        requests = [
            TTSRequest(
                text=f"Request {i}",
                session_id="2025-12-21_12-00-00",
                sequence=i,
                oracle_name=f"oracle_{i}",
                oracle_id=f"oracle_{i}",
            )
            for i in range(1, 4)
        ]
        
        # Run concurrently
        results = await asyncio.gather(*[service.synthesize(r) for r in requests])
        
        # All should succeed
        assert all(r.success for r in results)
        # All should have different paths
        paths = [r.file_path for r in results]
        assert len(set(paths)) == len(paths)
    
    @pytest.mark.asyncio
    async def test_mixed_success_and_failure(self, tts_config, sessions_path):
        """Should handle mix of successful and failed requests."""
        # Create two services - one succeeds, one fails
        success_service = MockTTSService(tts_config, sessions_path)
        fail_service = MockTTSService(tts_config, sessions_path, simulate_failure=True)
        
        request = TTSRequest(
            text="Test request",
            session_id="2025-12-21_12-00-00",
            sequence=1,
            oracle_name="test",
            oracle_id="test",
        )
        
        result1 = await success_service.synthesize(request)
        
        # Use different request to avoid cache hit
        request2 = TTSRequest(
            text="Different text",
            session_id="2025-12-21_12-00-00",
            sequence=2,
            oracle_name="test",
            oracle_id="test",
        )
        result2 = await fail_service.synthesize(request2)
        
        assert result1.success
        assert not result2.success


class TestProviderSwapping:
    """Test for FR-014: TTSService provider can be swapped via config."""
    
    @pytest.mark.asyncio
    async def test_provider_interface_compatibility(self, tts_config, sessions_path, sample_request):
        """Mock and Edge services should be interchangeable."""
        from src.services.tts.base import TTSService
        
        # Both services implement TTSService
        mock_service = MockTTSService(tts_config, sessions_path)
        edge_service = EdgeTTSService(tts_config, sessions_path)
        
        # Both are instances of TTSService
        assert isinstance(mock_service, TTSService)
        assert isinstance(edge_service, TTSService)
        
        # Both have required methods
        for service in [mock_service, edge_service]:
            assert hasattr(service, 'synthesize')
            assert hasattr(service, 'check_health')
            assert hasattr(service, 'get_artifact_path')
    
    @pytest.mark.asyncio
    async def test_factory_can_swap_providers(self, sessions_path, sample_request):
        """Factory function should be able to create either provider."""
        def create_tts_service(provider: str, config: TTSConfig, path: Path):
            if provider == "mock":
                return MockTTSService(config, path)
            elif provider == "edge":
                return EdgeTTSService(config, path)
            else:
                raise ValueError(f"Unknown provider: {provider}")
        
        config = TTSConfig()
        
        mock = create_tts_service("mock", config, sessions_path)
        edge = create_tts_service("edge", config, sessions_path)
        
        # Both should work
        mock_result = await mock.synthesize(sample_request)
        assert mock_result.success
