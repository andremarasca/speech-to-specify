"""Unit tests for TelegramBotAdapter message splitting functionality."""

import pytest
from src.services.telegram.bot import TelegramBotAdapter, TELEGRAM_MESSAGE_LIMIT


class TestMessageSplitting:
    """Tests for _split_message method."""

    @pytest.fixture
    def bot(self):
        """Create a bot instance for testing (without starting it)."""
        from src.lib.config import TelegramConfig
        config = TelegramConfig(token="test_token")
        return TelegramBotAdapter(config)

    def test_short_message_not_split(self, bot):
        """Messages under limit should not be split."""
        text = "Short message"
        chunks = bot._split_message(text)
        assert chunks == [text]

    def test_exact_limit_not_split(self, bot):
        """Message at exact limit should not be split."""
        text = "a" * TELEGRAM_MESSAGE_LIMIT
        chunks = bot._split_message(text)
        assert chunks == [text]

    def test_over_limit_splits(self, bot):
        """Message over limit should be split."""
        text = "a" * (TELEGRAM_MESSAGE_LIMIT + 100)
        chunks = bot._split_message(text)
        assert len(chunks) == 2
        assert all(len(c) <= TELEGRAM_MESSAGE_LIMIT for c in chunks)

    def test_split_at_paragraph(self, bot):
        """Should prefer splitting at paragraph boundaries."""
        para1 = "a" * 2000
        para2 = "b" * 2000
        para3 = "c" * 2000
        text = f"{para1}\n\n{para2}\n\n{para3}"
        
        chunks = bot._split_message(text)
        
        assert len(chunks) == 2
        assert para1 in chunks[0]
        assert para2 in chunks[0]
        assert para3 in chunks[1]

    def test_split_at_newline(self, bot):
        """Should split at newline when no paragraph break available."""
        line1 = "a" * 3000
        line2 = "b" * 3000
        text = f"{line1}\n{line2}"
        
        chunks = bot._split_message(text)
        
        assert len(chunks) == 2
        assert chunks[0].strip() == line1
        assert chunks[1].strip() == line2

    def test_split_at_space(self, bot):
        """Should split at space when no newline available."""
        # Create text without newlines
        word = "word "
        text = word * (TELEGRAM_MESSAGE_LIMIT // len(word) + 100)
        
        chunks = bot._split_message(text)
        
        assert len(chunks) >= 2
        # Each chunk should end cleanly (not mid-word)
        for chunk in chunks[:-1]:
            assert not chunk.endswith("wor")  # Not cut mid-word

    def test_hard_split_when_necessary(self, bot):
        """Should hard split when no good break point."""
        # Text with no spaces or newlines
        text = "a" * (TELEGRAM_MESSAGE_LIMIT + 100)
        
        chunks = bot._split_message(text)
        
        assert len(chunks) == 2
        assert len(chunks[0]) == TELEGRAM_MESSAGE_LIMIT
        assert len(chunks[1]) == 100

    def test_empty_message(self, bot):
        """Empty message should return single empty chunk."""
        chunks = bot._split_message("")
        assert chunks == [""]

    def test_multiple_splits(self, bot):
        """Very long message should split into multiple chunks."""
        text = "a" * (TELEGRAM_MESSAGE_LIMIT * 3 + 100)
        
        chunks = bot._split_message(text)
        
        assert len(chunks) == 4
        for i, chunk in enumerate(chunks[:-1]):
            assert len(chunk) == TELEGRAM_MESSAGE_LIMIT
        assert len(chunks[-1]) == 100

    def test_strips_whitespace_at_boundaries(self, bot):
        """Leading whitespace from next chunk should be stripped."""
        line1 = "a" * 3000
        line2 = "b" * 3000
        text = f"{line1}\n   {line2}"  # Leading spaces after newline
        
        chunks = bot._split_message(text)
        
        assert len(chunks) == 2
        # Second chunk should not have leading whitespace
        assert not chunks[1].startswith(" ")
