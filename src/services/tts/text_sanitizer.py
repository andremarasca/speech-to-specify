"""Text sanitization utilities for TTS.

Per plan.md for 008-async-audio-response.

This module provides text cleaning functions for TTS synthesis:
- strip_markdown: Remove Markdown formatting
- strip_special_characters: Replace symbols with spoken equivalents

Reference implementation: .local/edge_tts_generate.py
"""

import re
from typing import Optional


class TextSanitizer:
    """Sanitizes text for TTS synthesis.
    
    Removes or replaces text elements that are not suitable for
    spoken audio, such as Markdown formatting and special symbols.
    
    Example:
        >>> sanitizer = TextSanitizer()
        >>> clean = sanitizer.sanitize("**Bold** and `code`")
        >>> print(clean)  # "Bold and code"
    """
    
    # Symbols and their spoken equivalents (Portuguese)
    SYMBOL_REPLACEMENTS = {
        "&": " e ",
        "@": " arroba ",
        "#": "",
        "$": " dólares ",
        "%": " por cento ",
        "€": " euros ",
        "£": " libras ",
        "¥": " ienes ",
        "©": "",
        "®": "",
        "™": "",
        "°": " graus ",
        "±": " mais ou menos ",
        "×": " vezes ",
        "÷": " dividido por ",
        "≈": " aproximadamente ",
        "≠": " diferente de ",
        "≤": " menor ou igual a ",
        "≥": " maior ou igual a ",
        "→": "",
        "←": "",
        "↑": "",
        "↓": "",
        "•": "",
        "·": "",
        "…": "...",
        "—": ", ",
        "–": ", ",
        "\"": "",
        "'": "",
        "'": "",
        "'": "",
        """: "",
        """: "",
        "«": "",
        "»": "",
        "[": "",
        "]": "",
        "{": "",
        "}": "",
        "(": ", ",
        ")": ", ",
        "/": " ou ",
        "\\": "",
        "|": "",
        "^": "",
        "~": "",
        "*": "",
        "_": " ",
        "=": " igual a ",
        "+": " mais ",
        "<": " menor que ",
        ">": " maior que ",
    }
    
    @classmethod
    def strip_markdown(cls, text: str) -> str:
        """Remove Markdown formatting from text.
        
        Handles:
        - Code blocks (``` ... ```)
        - Inline code (`code`)
        - Images ![alt](url)
        - Links [text](url)
        - Headers (# ## ### etc.)
        - Bold/italic (**, *, __, _)
        - Strikethrough (~~text~~)
        - Blockquotes (> )
        - Horizontal rules (---, ***, ___)
        - List markers (-, *, +, 1., 2.)
        - HTML tags
        
        Args:
            text: Text potentially containing Markdown syntax.
            
        Returns:
            Clean text without Markdown formatting.
        """
        # Remove code blocks (``` ... ```)
        text = re.sub(r"```[\s\S]*?```", "", text)
        
        # Remove inline code (`code`)
        text = re.sub(r"`([^`]+)`", r"\1", text)
        
        # Remove images ![alt](url)
        text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
        
        # Remove links [text](url) -> keep text
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        
        # Remove reference links [text][ref]
        text = re.sub(r"\[([^\]]+)\]\[[^\]]*\]", r"\1", text)
        
        # Remove headers (# ## ### etc.)
        text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
        
        # Remove bold/italic (*** ** * ___ __ _)
        text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)
        text = re.sub(r"_{1,3}([^_]+)_{1,3}", r"\1", text)
        
        # Remove strikethrough (~~text~~)
        text = re.sub(r"~~([^~]+)~~", r"\1", text)
        
        # Remove blockquotes (> )
        text = re.sub(r"^>\s+", "", text, flags=re.MULTILINE)
        
        # Remove horizontal rules (---, ***, ___)
        text = re.sub(r"^[-*_]{3,}\s*$", "", text, flags=re.MULTILINE)
        
        # Remove unordered list markers (- * +)
        text = re.sub(r"^[\-\*\+]\s+", "", text, flags=re.MULTILINE)
        
        # Remove ordered list markers (1. 2. etc.)
        text = re.sub(r"^\d+\.\s+", "", text, flags=re.MULTILINE)
        
        # Remove HTML tags
        text = re.sub(r"<[^>]+>", "", text)
        
        return text
    
    @classmethod
    def strip_special_characters(cls, text: str) -> str:
        """Remove or replace special characters for TTS.
        
        Replaces symbols with their spoken Portuguese equivalents
        or removes them entirely if not suitable for speech.
        
        Args:
            text: Text potentially containing special characters.
            
        Returns:
            Clean text suitable for TTS.
        """
        for char, replacement in cls.SYMBOL_REPLACEMENTS.items():
            text = text.replace(char, replacement)
        
        # Remove any remaining non-printable or unusual characters
        # Keep letters, numbers, basic punctuation (. , ! ? : ;) and spaces
        text = re.sub(r"[^\w\s.,!?:;\-áàâãéèêíìîóòôõúùûçÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇ]", "", text)
        
        return text
    
    @classmethod
    def normalize_whitespace(cls, text: str) -> str:
        """Normalize whitespace in text.
        
        Collapses multiple spaces/newlines to single spaces
        and removes leading/trailing whitespace.
        
        Args:
            text: Text with potentially irregular whitespace.
            
        Returns:
            Text with normalized whitespace.
        """
        # Remove excessive whitespace and collapse to single spaces
        text = " ".join(text.split())
        
        # Remove leading/trailing whitespace
        return text.strip()
    
    @classmethod
    def sanitize(cls, text: str, max_length: Optional[int] = None) -> str:
        """Perform full text sanitization for TTS.
        
        Applies all sanitization steps in order:
        1. Strip Markdown formatting
        2. Strip special characters
        3. Normalize whitespace
        4. Truncate to max_length if specified
        
        Args:
            text: Raw text content.
            max_length: Optional maximum length (will truncate with "...").
            
        Returns:
            Sanitized text string ready for TTS.
        """
        if not text:
            return ""
        
        # Apply sanitization steps
        text = cls.strip_markdown(text)
        text = cls.strip_special_characters(text)
        text = cls.normalize_whitespace(text)
        
        # Truncate if needed
        if max_length and len(text) > max_length:
            text = text[:max_length - 3] + "..."
        
        return text
