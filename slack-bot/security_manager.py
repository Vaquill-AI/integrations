"""
Security Manager for Vaquill Slack Bot.

Handles user authorization, input validation, and request verification.
"""

import re
import logging
import hashlib
import hmac
import time
from typing import Optional, List, Dict, Any

from config import Config

logger = logging.getLogger(__name__)


class SecurityManager:
    """Authorization, input validation, and Slack request verification."""

    def __init__(self) -> None:
        self.allowed_channels = Config.get_allowed_channels()
        self.blocked_users = Config.get_blocked_users()

        self._harmful_patterns = [
            re.compile(p)
            for p in [
                r"(?i)(drop\s+table|delete\s+from|insert\s+into)",
                r"<script[^>]*>.*?</script>",
                r"(?i)(api[_\s-]?key|secret|token|password)\s*[:=]\s*[\"']?[\w-]+",
                r"(?i)(eval|exec|__import__|compile)\s*\(",
            ]
        ]

    async def is_user_allowed(self, user_id: str) -> bool:
        if self.blocked_users and user_id in self.blocked_users:
            logger.warning("Blocked user attempted access: %s", user_id)
            return False
        return True

    async def is_channel_allowed(self, channel_id: str) -> bool:
        if not self.allowed_channels:
            return True
        if channel_id not in self.allowed_channels:
            logger.warning("Unauthorized channel access attempt: %s", channel_id)
            return False
        return True

    def validate_input(self, text: str) -> bool:
        if not text:
            return True
        if len(text) > Config.MAX_MESSAGE_LENGTH:
            logger.warning("Message too long: %d characters", len(text))
            return False
        for regex in self._harmful_patterns:
            if regex.search(text):
                logger.warning("Potentially harmful content detected")
                return False
        return True

    def sanitize_input(self, text: str) -> str:
        if not text:
            return text
        if len(text) > Config.MAX_MESSAGE_LENGTH:
            text = text[: Config.MAX_MESSAGE_LENGTH] + "..."
        for regex in self._harmful_patterns:
            text = regex.sub("[REDACTED]", text)
        text = "".join(ch for ch in text if ch.isprintable() or ch in "\n\t")
        return text.strip()

    def verify_slack_request(
        self, timestamp: str, signature: str, body: bytes
    ) -> bool:
        if abs(time.time() - float(timestamp)) > 300:
            logger.warning("Request timestamp too old")
            return False
        sig_base = f"v0:{timestamp}:{body.decode('utf-8')}"
        expected = "v0=" + hmac.new(
            Config.SLACK_SIGNING_SECRET.encode(),
            sig_base.encode(),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, signature):
            logger.warning("Invalid request signature")
            return False
        return True

    def get_safe_error_message(self, error: Exception) -> str:
        err = str(error).lower()
        if "rate limit" in err:
            return "Rate limit exceeded. Please try again later."
        if "unauthorized" in err or "401" in err:
            return "Authentication error. Please contact your administrator."
        if "not found" in err or "404" in err:
            return "The requested resource was not found."
        if "timeout" in err:
            return "Request timed out. Please try again."
        return "An error occurred while processing your request. Please try again later."

    @staticmethod
    def mask_sensitive_data(data: Dict[str, Any]) -> Dict[str, Any]:
        sensitive_keys = {
            "token", "api_key", "secret", "password", "auth",
            "authorization", "x-api-key", "bearer",
        }

        def _mask(value: Any) -> Any:
            if isinstance(value, str) and len(value) > 4:
                return f"{value[:2]}{'*' * (len(value) - 4)}{value[-2:]}"
            if isinstance(value, dict):
                return _mask_dict(value)
            if isinstance(value, list):
                return [_mask(item) for item in value]
            return value

        def _mask_dict(d: Dict[str, Any]) -> Dict[str, Any]:
            out = {}
            for k, v in d.items():
                if any(s in k.lower() for s in sensitive_keys):
                    out[k] = _mask(v) if v else None
                elif isinstance(v, dict):
                    out[k] = _mask_dict(v)
                elif isinstance(v, list):
                    out[k] = [_mask(i) if isinstance(i, dict) else i for i in v]
                else:
                    out[k] = v
            return out

        return _mask_dict(data)

    def log_security_event(
        self, event_type: str, user_id: str, details: Dict[str, Any]
    ) -> None:
        masked = self.mask_sensitive_data(details)
        logger.warning(
            "Security event — type=%s user=%s details=%s",
            event_type,
            user_id,
            masked,
        )
