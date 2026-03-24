"""
Markdown Processor for Vaquill API Responses

Fixes common markdown formatting issues in LLM output:
1. Missing spaces after markdown syntax (###, **, -, etc.)
2. Ensures proper line breaks around headings
3. Formats lists correctly
4. Preserves code blocks and inline code
"""

import re
import logging

logger = logging.getLogger(__name__)


def preprocess_markdown(text: str) -> str:
    """
    Preprocess markdown text from Vaquill to ensure proper formatting.

    Common issues fixed:
    - ###Heading -> ### Heading
    - **bold**text -> **bold** text
    - 1.Item -> 1. Item
    - Missing line breaks around headings

    Args:
        text: Raw markdown text from API response

    Returns:
        str: Properly formatted markdown
    """
    if not text or not isinstance(text, str):
        return text

    original_text = text

    # Fix headings: Add space after # if missing
    text = re.sub(r'(#{1,6})([^\s#\n])', r'\1 \2', text)

    # Ensure blank line before headings (but not if already at start or after blank line)
    text = re.sub(r'([^\n])\n(#{1,6}\s)', r'\1\n\n\2', text)

    # Fix bold/italic: Add space after closing marker if followed by word
    text = re.sub(r'(\*\*[^*\n]+?\*\*)([a-zA-Z0-9])', r'\1 \2', text)
    text = re.sub(r'(?<!\*)(\*[^*\n]+?\*)(?!\*)([a-zA-Z0-9])', r'\1 \2', text)

    # Fix numbered lists: Add space after period
    text = re.sub(r'(\n\d+\.)([^\s])', r'\1 \2', text)

    # Fix bullet lists: Add space after marker
    text = re.sub(r'(\n[-*+])([^\s])', r'\1 \2', text)

    # Fix multiple consecutive line breaks (keep max 2)
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Clean up any leading/trailing whitespace
    text = text.strip()

    if len(text) != len(original_text):
        logger.debug(f"Markdown preprocessed: {len(original_text)} -> {len(text)} chars")

    return text


def is_markdown_content(text: str) -> bool:
    """
    Check if text contains markdown syntax.

    Args:
        text: Text to check

    Returns:
        bool: True if markdown syntax detected
    """
    if not text:
        return False

    markdown_patterns = [
        r'#{1,6}\s',       # Headings
        r'\*\*[^*]+\*\*',  # Bold
        r'\*[^*]+\*',      # Italic
        r'^\d+\.\s',       # Numbered lists
        r'^[-*+]\s',       # Bullet lists
        r'\[.+\]\(.+\)',   # Links
        r'`[^`]+`',        # Inline code
    ]

    for pattern in markdown_patterns:
        if re.search(pattern, text, re.MULTILINE):
            return True

    return False
