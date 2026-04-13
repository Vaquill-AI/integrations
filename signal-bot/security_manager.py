"""
Security manager for Signal bot.

Input sanitization, content filtering, and sensitive data masking.
"""

from __future__ import annotations

import re
import logging

logger = logging.getLogger(__name__)

# Patterns that indicate potentially harmful content
_INJECTION_PATTERNS = [
    re.compile(r"<script[\s>]", re.IGNORECASE),
    re.compile(r"javascript:", re.IGNORECASE),
    re.compile(r"on\w+\s*=", re.IGNORECASE),
    re.compile(r"\{\{.*\}\}"),  # Template injection
    re.compile(r"\$\{.*\}"),  # Expression injection
]

# Sensitive data patterns to mask in logs
_SENSITIVE_PATTERNS = [
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"), "[EMAIL]"),
    (re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"), "[CARD]"),
    (re.compile(r"\b\d{12}\b"), "[AADHAAR]"),
    (re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"), "[PAN]"),
]


def sanitize_input(text: str) -> str:
    """Sanitize user input by stripping control characters and trimming.

    Does NOT strip markdown since Signal uses it for formatting.
    """
    if not text:
        return ""

    # Remove null bytes and control characters (except newline, tab)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    # Collapse excessive whitespace (but preserve single newlines)
    text = re.sub(r"[^\S\n]+", " ", text)
    text = re.sub(r"\n{4,}", "\n\n\n", text)

    return text.strip()


def contains_injection(text: str) -> bool:
    """Check if text contains potential injection patterns."""
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            return True
    return False


def mask_sensitive_data(text: str) -> str:
    """Mask sensitive data (emails, card numbers, Aadhaar, PAN) for logging."""
    for pattern, replacement in _SENSITIVE_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def mask_phone(phone: str) -> str:
    """Mask a phone number for logging. Shows country code + first digit only."""
    if len(phone) > 4:
        return phone[:4] + "****"
    return phone


def validate_message(text: str, max_length: int = 5000) -> tuple[bool, str]:
    """Validate a message. Returns (is_valid, error_message)."""
    if not text or not text.strip():
        return False, ""

    if len(text) > max_length:
        return False, f"Message too long (max {max_length} characters)."

    if contains_injection(text):
        logger.warning("injection_attempt_detected", extra={"text_preview": text[:50]})
        return False, "Message contains invalid characters."

    return True, ""
