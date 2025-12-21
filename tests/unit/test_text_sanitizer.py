"""Unit tests for TextSanitizer.

Per T011 [US1] from tasks.md for 008-async-audio-response.

Tests text sanitization including:
- Markdown headers, bold, italic removal
- Code blocks removal
- Emoji handling
- URL handling
- Special unicode character conversion
"""

import pytest

from src.services.tts.text_sanitizer import TextSanitizer


class TestStripMarkdown:
    """Tests for TextSanitizer.strip_markdown()."""
    
    def test_strip_headers(self):
        """Should remove markdown headers (# ## ### etc.)."""
        text = "# Header 1\n## Header 2\n### Header 3\nRegular text"
        result = TextSanitizer.strip_markdown(text)
        assert "# " not in result
        assert "## " not in result
        assert "### " not in result
        assert "Header 1" in result
        assert "Header 2" in result
        assert "Header 3" in result
        assert "Regular text" in result
    
    def test_strip_bold(self):
        """Should remove bold formatting (**text** and __text__)."""
        text = "This is **bold** and __also bold__"
        result = TextSanitizer.strip_markdown(text)
        assert "**" not in result
        assert "__" not in result
        assert "bold" in result
        assert "also bold" in result
    
    def test_strip_italic(self):
        """Should remove italic formatting (*text* and _text_)."""
        text = "This is *italic* and _also italic_"
        result = TextSanitizer.strip_markdown(text)
        assert "italic" in result
        assert "also italic" in result
    
    def test_strip_code_blocks(self):
        """Should remove fenced code blocks."""
        text = "Text before\n```python\nprint('hello')\n```\nText after"
        result = TextSanitizer.strip_markdown(text)
        assert "```" not in result
        assert "print" not in result
        assert "Text before" in result
        assert "Text after" in result
    
    def test_strip_inline_code(self):
        """Should remove inline code but keep text."""
        text = "Use the `command` to run"
        result = TextSanitizer.strip_markdown(text)
        assert "`" not in result
        assert "command" in result
    
    def test_strip_links(self):
        """Should remove link syntax but keep text."""
        text = "Visit [Google](https://google.com) for more"
        result = TextSanitizer.strip_markdown(text)
        assert "[" not in result
        assert "](" not in result
        assert "https://google.com" not in result
        assert "Google" in result
    
    def test_strip_images(self):
        """Should remove image syntax."""
        text = "See ![alt text](image.png) here"
        result = TextSanitizer.strip_markdown(text)
        assert "![" not in result
        assert "image.png" not in result
        assert "alt text" in result
    
    def test_strip_strikethrough(self):
        """Should remove strikethrough formatting."""
        text = "This is ~~deleted~~ text"
        result = TextSanitizer.strip_markdown(text)
        assert "~~" not in result
        assert "deleted" in result
    
    def test_strip_blockquotes(self):
        """Should remove blockquote markers."""
        text = "> This is quoted\n> Another quote"
        result = TextSanitizer.strip_markdown(text)
        assert "> " not in result
        assert "quoted" in result
    
    def test_strip_horizontal_rules(self):
        """Should remove horizontal rules."""
        text = "Before\n---\nAfter"
        result = TextSanitizer.strip_markdown(text)
        assert "---" not in result
        assert "Before" in result
        assert "After" in result
    
    def test_strip_unordered_lists(self):
        """Should remove unordered list markers."""
        text = "- Item 1\n* Item 2\n+ Item 3"
        result = TextSanitizer.strip_markdown(text)
        assert "Item 1" in result
        assert "Item 2" in result
        assert "Item 3" in result
    
    def test_strip_ordered_lists(self):
        """Should remove ordered list markers."""
        text = "1. First\n2. Second\n3. Third"
        result = TextSanitizer.strip_markdown(text)
        assert "1. " not in result
        assert "First" in result
        assert "Second" in result
    
    def test_strip_html_tags(self):
        """Should remove HTML tags."""
        text = "Text <br> with <strong>HTML</strong> tags"
        result = TextSanitizer.strip_markdown(text)
        assert "<" not in result
        assert ">" not in result
        assert "HTML" in result


class TestStripSpecialCharacters:
    """Tests for TextSanitizer.strip_special_characters()."""
    
    def test_replace_ampersand(self):
        """Should replace & with 'e'."""
        text = "Tom & Jerry"
        result = TextSanitizer.strip_special_characters(text)
        assert "&" not in result
        assert "e" in result
    
    def test_replace_at_symbol(self):
        """Should replace @ with 'arroba'."""
        text = "email@domain.com"
        result = TextSanitizer.strip_special_characters(text)
        assert "@" not in result
        assert "arroba" in result
    
    def test_replace_percent(self):
        """Should replace % with 'por cento'."""
        text = "100% complete"
        result = TextSanitizer.strip_special_characters(text)
        assert "%" not in result
        assert "por cento" in result
    
    def test_replace_currency_symbols(self):
        """Should replace currency symbols with spoken equivalents."""
        text = "$100 €50 £30"
        result = TextSanitizer.strip_special_characters(text)
        assert "$" not in result
        assert "€" not in result
        assert "£" not in result
        assert "dólares" in result
        assert "euros" in result
        assert "libras" in result
    
    def test_remove_brackets(self):
        """Should remove brackets."""
        text = "Text [in] {brackets} (here)"
        result = TextSanitizer.strip_special_characters(text)
        assert "[" not in result
        assert "]" not in result
        assert "{" not in result
        assert "}" not in result
        assert "in" in result
        assert "brackets" in result
        assert "here" in result
    
    def test_replace_math_symbols(self):
        """Should replace math symbols with spoken equivalents."""
        text = "5 × 3 = 15 and 10 ÷ 2 = 5"
        result = TextSanitizer.strip_special_characters(text)
        assert "×" not in result
        assert "÷" not in result
        assert "vezes" in result
        assert "dividido por" in result
    
    def test_remove_arrows(self):
        """Should remove arrow characters."""
        text = "Go → here or ← there"
        result = TextSanitizer.strip_special_characters(text)
        assert "→" not in result
        assert "←" not in result
    
    def test_remove_quotes(self):
        """Should remove various quote characters."""
        text = '"Double" and \'single\' and «guillemets»'
        result = TextSanitizer.strip_special_characters(text)
        assert '"' not in result
        assert "'" not in result
        assert "«" not in result
        assert "»" not in result
    
    def test_preserve_portuguese_accents(self):
        """Should preserve Portuguese accented characters."""
        text = "Olá, como você está? Ação imediata!"
        result = TextSanitizer.strip_special_characters(text)
        assert "Olá" in result
        assert "você" in result
        assert "está" in result
        assert "Ação" in result
    
    def test_preserve_basic_punctuation(self):
        """Should preserve basic punctuation marks."""
        text = "Hello, world! How are you? Fine: thanks."
        result = TextSanitizer.strip_special_characters(text)
        assert "," in result
        assert "!" in result
        assert "?" in result
        assert ":" in result
        assert "." in result


class TestNormalizeWhitespace:
    """Tests for TextSanitizer.normalize_whitespace()."""
    
    def test_collapse_multiple_spaces(self):
        """Should collapse multiple spaces to single space."""
        text = "Multiple    spaces    here"
        result = TextSanitizer.normalize_whitespace(text)
        assert "    " not in result
        assert "Multiple spaces here" == result
    
    def test_collapse_newlines(self):
        """Should collapse newlines to single space."""
        text = "Line 1\n\n\nLine 2"
        result = TextSanitizer.normalize_whitespace(text)
        assert "\n" not in result
        assert "Line 1 Line 2" == result
    
    def test_strip_leading_trailing(self):
        """Should strip leading and trailing whitespace."""
        text = "   Text with spaces   "
        result = TextSanitizer.normalize_whitespace(text)
        assert result == "Text with spaces"
    
    def test_handle_tabs(self):
        """Should handle tab characters."""
        text = "Tab\there\tand\tthere"
        result = TextSanitizer.normalize_whitespace(text)
        assert "\t" not in result


class TestSanitize:
    """Tests for TextSanitizer.sanitize() - full pipeline."""
    
    def test_full_sanitization(self):
        """Should apply all sanitization steps."""
        text = "# Header\n\n**Bold** text with `code` and [link](url)\n\n100% awesome @ domain"
        result = TextSanitizer.sanitize(text)
        
        # No markdown
        assert "# " not in result
        assert "**" not in result
        assert "`" not in result
        assert "[" not in result
        assert "](" not in result
        
        # Symbols replaced
        assert "%" not in result
        assert "@" not in result
        
        # Content preserved
        assert "Header" in result
        assert "Bold" in result
        assert "text" in result
        assert "code" in result
        assert "link" in result
    
    def test_empty_string(self):
        """Should handle empty string."""
        assert TextSanitizer.sanitize("") == ""
        assert TextSanitizer.sanitize(None) == ""  # type: ignore
    
    def test_max_length_truncation(self):
        """Should truncate to max_length with ellipsis."""
        text = "This is a very long text that should be truncated"
        result = TextSanitizer.sanitize(text, max_length=20)
        assert len(result) == 20
        assert result.endswith("...")
    
    def test_max_length_no_truncation(self):
        """Should not truncate if under max_length."""
        text = "Short text"
        result = TextSanitizer.sanitize(text, max_length=100)
        assert result == "Short text"
    
    def test_complex_markdown_document(self):
        """Should handle complex markdown with mixed formatting."""
        text = """
# Título Principal

Este é um parágrafo com **texto em negrito** e *itálico*.

## Seção 2

```python
print("código")
```

Lista:
- Item 1
- Item 2
- Item 3

> Uma citação importante

Visite [nosso site](https://example.com) para mais informações.

---

Fim do documento.
"""
        result = TextSanitizer.sanitize(text)
        
        # Verify content preserved
        assert "Título Principal" in result
        assert "texto em negrito" in result
        assert "itálico" in result
        assert "Seção 2" in result
        assert "Item 1" in result
        assert "Item 2" in result
        assert "citação importante" in result
        assert "nosso site" in result
        assert "Fim do documento" in result
        
        # Verify markdown removed
        assert "```" not in result
        assert "# " not in result
        assert "**" not in result
        assert "[nosso site](" not in result
        assert "---" not in result


class TestUnicodeHandling:
    """Tests for unicode and emoji handling."""
    
    def test_common_emojis(self):
        """Should remove common emojis."""
        text = "Hello 👋 World 🌍"
        result = TextSanitizer.sanitize(text)
        # Emojis should be removed by the character filter
        assert "👋" not in result
        assert "🌍" not in result
        assert "Hello" in result
        assert "World" in result
    
    def test_url_handling(self):
        """Should handle URLs in markdown context."""
        text = "Check [this link](https://example.com/path?query=value)"
        result = TextSanitizer.sanitize(text)
        assert "https://" not in result
        assert "example.com" not in result
        assert "this link" in result
    
    def test_mixed_languages(self):
        """Should handle mixed language content."""
        text = "English text com português e 日本語"
        result = TextSanitizer.sanitize(text)
        assert "English" in result
        assert "português" in result
        # Japanese characters may be removed by the filter
