"""
Input Validation and Sanitization for Microsoft Teams Bot
"""

import re
import html
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class InputValidator:
    """Validates and sanitizes user inputs"""

    MAX_MESSAGE_LENGTH = 4000
    MAX_USERNAME_LENGTH = 256
    MAX_METADATA_LENGTH = 1000

    SCRIPT_PATTERN = re.compile(
        r"<script[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL
    )
    HTML_TAG_PATTERN = re.compile(r"<[^>]+>")

    @staticmethod
    def sanitize_message(text: str, max_length: Optional[int] = None) -> str:
        """Sanitize user message text."""
        if not text:
            return ""

        if max_length is None:
            max_length = InputValidator.MAX_MESSAGE_LENGTH

        text = text[:max_length]
        text = text.replace("\x00", "")
        text = html.escape(text, quote=False)
        text = " ".join(text.split())
        text = InputValidator.SCRIPT_PATTERN.sub("", text)

        return text.strip()

    @staticmethod
    def sanitize_html(text: str, allow_basic_formatting: bool = False) -> str:
        """Sanitize HTML content."""
        if not text:
            return ""

        text = InputValidator.SCRIPT_PATTERN.sub("", text)

        if not allow_basic_formatting:
            text = InputValidator.HTML_TAG_PATTERN.sub("", text)

        text = html.escape(text, quote=True)

        return text.strip()

    @staticmethod
    def validate_user_id(user_id: str) -> bool:
        """Validate user ID format."""
        if not user_id:
            return False
        if len(user_id) > 256:
            return False
        if "\x00" in user_id:
            return False
        if not re.match(r"^[a-zA-Z0-9\-_:@.]+$", user_id):
            logger.warning("Invalid user ID format")
            return False
        return True

    @staticmethod
    def validate_channel_id(channel_id: str) -> bool:
        """Validate channel ID format."""
        if not channel_id:
            return False
        if len(channel_id) > 256:
            return False
        if "\x00" in channel_id:
            return False
        if not re.match(r"^[a-zA-Z0-9\-_:@.]+$", channel_id):
            logger.warning("Invalid channel ID format")
            return False
        return True

    @staticmethod
    def sanitize_user_info(user_info: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize user information dictionary."""
        if not user_info:
            return {}

        sanitized = {}
        string_fields = ["id", "name", "tenant", "channel"]
        for field_name in string_fields:
            if field_name in user_info and user_info[field_name]:
                value = str(user_info[field_name])[: InputValidator.MAX_USERNAME_LENGTH]
                sanitized[field_name] = html.escape(value, quote=False)

        return sanitized

    @staticmethod
    def validate_message_length(
        text: str, max_length: Optional[int] = None
    ) -> bool:
        """Check if message length is within acceptable limits."""
        if not text:
            return False
        if max_length is None:
            max_length = InputValidator.MAX_MESSAGE_LENGTH
        return len(text) <= max_length

    @staticmethod
    def detect_potential_injection(text: str) -> bool:
        """Detect potential injection attacks."""
        if not text:
            return False

        if InputValidator.SCRIPT_PATTERN.search(text):
            logger.warning("Potential script injection detected")
            return True

        sql_patterns = [
            r"(\bunion\b.*\bselect\b)",
            r"(\bselect\b.*\bfrom\b)",
            r"(\binsert\b.*\binto\b)",
            r"(\bdelete\b.*\bfrom\b)",
            r"(\bdrop\b.*\btable\b)",
        ]

        for pattern in sql_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                logger.warning("Potential SQL injection pattern detected")
                return True

        command_patterns = [
            r"[;&|`$]",
            r"\$\{.*\}",
            r"\$\(.*\)",
        ]

        for pattern in command_patterns:
            if re.search(pattern, text):
                logger.warning("Potential command injection pattern detected")
                return True

        return False

    @staticmethod
    def sanitize_for_adaptive_card(text: str) -> str:
        """Sanitize text for safe display in Adaptive Cards."""
        if not text:
            return ""

        text = InputValidator.SCRIPT_PATTERN.sub("", text)
        text = text.replace("\\", "\\\\")
        text = text.replace('"', '\\"')
        text = text.replace("\n", "\\n")
        text = text.replace("\r", "\\r")
        text = text.replace("\t", "\\t")

        return text
