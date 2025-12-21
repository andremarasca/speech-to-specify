"""Unit tests for TTS models.

Per T026 [US3] and T033 [US4] from tasks.md for 008-async-audio-response.

Tests:
- TTSArtifact.is_expired() 
- TTSRequest.idempotency_key
"""

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.models.tts import TTSRequest, TTSResult, TTSArtifact


class TestTTSArtifactIsExpired:
    """Tests for TTSArtifact.is_expired() - T026 [US3]."""
    
    def test_not_expired_recent_file(self):
        """Recent file should not be expired."""
        artifact = TTSArtifact(
            file_path=Path("/tmp/test.ogg"),
            session_id="2025-12-21_12-00-00",
            sequence=1,
            oracle_id="cetico",
            created_at=datetime.now() - timedelta(hours=1),
            file_size_bytes=1024,
        )
        
        # With 24h retention, 1h old file should not be expired
        assert artifact.is_expired(retention_hours=24) is False
    
    def test_expired_old_file(self):
        """Old file should be expired."""
        artifact = TTSArtifact(
            file_path=Path("/tmp/test.ogg"),
            session_id="2025-12-21_12-00-00",
            sequence=1,
            oracle_id="cetico",
            created_at=datetime.now() - timedelta(hours=48),
            file_size_bytes=1024,
        )
        
        # With 24h retention, 48h old file should be expired
        assert artifact.is_expired(retention_hours=24) is True
    
    def test_boundary_exactly_at_retention(self):
        """File exactly at retention boundary."""
        artifact = TTSArtifact(
            file_path=Path("/tmp/test.ogg"),
            session_id="2025-12-21_12-00-00",
            sequence=1,
            oracle_id="cetico",
            created_at=datetime.now() - timedelta(hours=24, minutes=1),
            file_size_bytes=1024,
        )
        
        # Just over 24h should be expired
        assert artifact.is_expired(retention_hours=24) is True
    
    def test_boundary_just_before_retention(self):
        """File just before retention boundary."""
        artifact = TTSArtifact(
            file_path=Path("/tmp/test.ogg"),
            session_id="2025-12-21_12-00-00",
            sequence=1,
            oracle_id="cetico",
            created_at=datetime.now() - timedelta(hours=23, minutes=59),
            file_size_bytes=1024,
        )
        
        # Just under 24h should not be expired
        assert artifact.is_expired(retention_hours=24) is False
    
    def test_age_hours_calculation(self):
        """Should calculate age correctly."""
        artifact = TTSArtifact(
            file_path=Path("/tmp/test.ogg"),
            session_id="2025-12-21_12-00-00",
            sequence=1,
            oracle_id="cetico",
            created_at=datetime.now() - timedelta(hours=12),
            file_size_bytes=1024,
        )
        
        # Should be approximately 12 hours old
        assert 11.9 < artifact.age_hours < 12.1


class TestTTSRequestIdempotencyKey:
    """Tests for TTSRequest.idempotency_key - T033 [US4]."""
    
    def test_key_includes_session_id(self):
        """Same text with different session_id should produce different keys."""
        request1 = TTSRequest(
            text="Same text",
            session_id="2025-12-21_12-00-00",
            sequence=1,
            oracle_name="cético",
            oracle_id="cetico",
        )
        
        request2 = TTSRequest(
            text="Same text",
            session_id="2025-12-21_13-00-00",  # Different session
            sequence=1,
            oracle_name="cético",
            oracle_id="cetico",
        )
        
        assert request1.idempotency_key != request2.idempotency_key
    
    def test_key_includes_oracle_id(self):
        """Same text with different oracle_id should produce different keys."""
        request1 = TTSRequest(
            text="Same text",
            session_id="2025-12-21_12-00-00",
            sequence=1,
            oracle_name="cético",
            oracle_id="cetico",
        )
        
        request2 = TTSRequest(
            text="Same text",
            session_id="2025-12-21_12-00-00",
            sequence=1,
            oracle_name="pragmático",
            oracle_id="pragmatico",  # Different oracle
        )
        
        assert request1.idempotency_key != request2.idempotency_key
    
    def test_key_includes_text_hash(self):
        """Different text should produce different keys."""
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
    
    def test_key_is_deterministic(self):
        """Same inputs should always produce same key."""
        def make_request():
            return TTSRequest(
                text="Deterministic text",
                session_id="2025-12-21_12-00-00",
                sequence=1,
                oracle_name="cético",
                oracle_id="cetico",
            )
        
        key1 = make_request().idempotency_key
        key2 = make_request().idempotency_key
        key3 = make_request().idempotency_key
        
        assert key1 == key2 == key3
    
    def test_key_length(self):
        """Key should be truncated to 16 characters."""
        request = TTSRequest(
            text="Test",
            session_id="2025-12-21_12-00-00",
            sequence=1,
            oracle_name="cético",
            oracle_id="cetico",
        )
        
        assert len(request.idempotency_key) == 16
    
    def test_key_is_hexadecimal(self):
        """Key should be valid hexadecimal."""
        request = TTSRequest(
            text="Test",
            session_id="2025-12-21_12-00-00",
            sequence=1,
            oracle_name="cético",
            oracle_id="cetico",
        )
        
        # Should be valid hex
        int(request.idempotency_key, 16)


class TestTTSArtifactFromFile:
    """Tests for TTSArtifact.from_file() factory method."""
    
    def test_creates_artifact_from_existing_file(self, tmp_path):
        """Should create artifact with correct metadata from file."""
        # Create a test file
        test_file = tmp_path / "test.ogg"
        test_file.write_bytes(b"OggS" + b"\x00" * 100)
        
        artifact = TTSArtifact.from_file(
            file_path=test_file,
            session_id="2025-12-21_12-00-00",
            sequence=1,
            oracle_id="cetico",
        )
        
        assert artifact.file_path == test_file
        assert artifact.session_id == "2025-12-21_12-00-00"
        assert artifact.sequence == 1
        assert artifact.oracle_id == "cetico"
        assert artifact.file_size_bytes == 104
        assert artifact.created_at is not None
