"""
Security management for the Vaquill WhatsApp bot.

Handles phone-number allowlisting / blocklisting, message validation,
injection-pattern detection, and profanity filtering.
"""

import re
from typing import Dict, List, Optional, Tuple

import structlog

from config import Config

logger = structlog.get_logger()


class SecurityManager:
    def __init__(self, config: Config):
        self.config = config
        self.allowed_numbers: List[str] = config.ALLOWED_NUMBERS or []
        self.blocked_numbers: List[str] = config.BLOCKED_NUMBERS or []
        self.max_message_length: int = config.MAX_MESSAGE_LENGTH
        self.enable_profanity_filter: bool = config.ENABLE_PROFANITY_FILTER

        if self.enable_profanity_filter:
            try:
                from better_profanity import profanity

                profanity.load_censor_words()
                self.profanity_filter = profanity
            except ImportError:
                logger.warning("profanity_filter_unavailable")
                self.profanity_filter = None
                self.enable_profanity_filter = False

        # Injection patterns
        self.sql_patterns = [
            r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|CREATE|ALTER)\b)",
            r"(--|#|/\*|\*/)",
            r"(\bOR\b\s*\d+\s*=\s*\d+)",
            r"(\bAND\b\s*\d+\s*=\s*\d+)",
            r"(';|';--|';#)",
            r"(\bEXEC\b|\bEXECUTE\b)",
        ]
        self.xss_patterns = [
            r"<script[^>]*>.*?</script>",
            r"javascript:",
            r"on\w+\s*=",
            r"<iframe[^>]*>",
            r"<object[^>]*>",
            r"<embed[^>]*>",
        ]
        self.command_patterns = [
            r"(\||&&|;|\n|\r)",
            r"(`|\$\()",
            r"(rm\s+-rf|format\s+c:|del\s+/f)",
        ]

    # -- phone number checks ----------------------------------------------

    def is_allowed_number(self, phone_number: str) -> bool:
        phone_number = self._clean_phone_number(phone_number)
        if not self.allowed_numbers:
            return True
        return any(
            self._match_phone_number(phone_number, a)
            for a in self.allowed_numbers
        )

    def is_blocked_number(self, phone_number: str) -> bool:
        phone_number = self._clean_phone_number(phone_number)
        return any(
            self._match_phone_number(phone_number, b)
            for b in self.blocked_numbers
        )

    def is_admin_number(self, phone_number: str) -> bool:
        if not self.config.ADMIN_NUMBERS:
            return False
        phone_number = self._clean_phone_number(phone_number)
        return any(
            self._match_phone_number(phone_number, a)
            for a in (self.config.ADMIN_NUMBERS or [])
        )

    # -- message validation -----------------------------------------------

    def validate_message(self, message: str) -> Tuple[bool, Optional[str]]:
        if len(message) > self.max_message_length:
            return False, f"Message too long. Maximum {self.max_message_length} characters allowed."

        if not message or not message.strip():
            return False, "Empty message not allowed."

        for pattern in self.sql_patterns:
            if re.search(pattern, message, re.IGNORECASE):
                logger.warning("sql_injection_attempt", message=message[:50])
                return False, "Invalid message format detected."

        for pattern in self.xss_patterns:
            if re.search(pattern, message, re.IGNORECASE):
                logger.warning("xss_attempt", message=message[:50])
                return False, "Invalid message format detected."

        for pattern in self.command_patterns:
            if re.search(pattern, message, re.IGNORECASE):
                logger.warning("command_injection_attempt", message=message[:50])
                return False, "Invalid message format detected."

        if self.enable_profanity_filter and self.profanity_filter:
            if self.profanity_filter.contains_profanity(message):
                return False, "Please keep the conversation respectful."

        return True, None

    def sanitize_message(self, message: str) -> str:
        message = re.sub(r"<[^>]+>", "", message)
        message = re.sub(
            r"<script[^>]*>.*?</script>", "", message,
            flags=re.IGNORECASE | re.DOTALL,
        )
        message = re.sub(r'[<>"\'`;]', "", message)
        message = message.strip()
        if len(message) > self.max_message_length:
            message = message[: self.max_message_length]
        return message

    def validate_command(self, command: str) -> Tuple[bool, Optional[str]]:
        if not command.startswith("/"):
            return False, "Commands must start with /"
        parts = command.split()
        if not parts:
            return False, "Empty command"
        name = parts[0][1:]
        if not re.match(r"^[a-zA-Z0-9_]+$", name):
            return False, "Invalid command format"
        if len(name) > 20:
            return False, "Command name too long"
        return True, None

    # -- helpers ----------------------------------------------------------

    def _clean_phone_number(self, phone_number: str) -> str:
        if phone_number.startswith("whatsapp:"):
            phone_number = phone_number[9:]
        phone_number = re.sub(r"[^\d+]", "", phone_number)
        if phone_number and not phone_number.startswith("+"):
            if len(phone_number) == 10:
                phone_number = "+91" + phone_number  # India default
        return phone_number

    def _match_phone_number(self, number1: str, number2: str) -> bool:
        number1 = self._clean_phone_number(number1)
        number2 = self._clean_phone_number(number2)
        if number1 == number2:
            return True
        if number1 and number2:
            n1 = re.sub(r"^\+\d{1,3}", "", number1)
            n2 = re.sub(r"^\+\d{1,3}", "", number2)
            if n1 == n2 and n1:
                return True
            if len(n1) >= 10 and len(n2) >= 10:
                return n1[-10:] == n2[-10:]
        return False

    def get_rate_limit_multiplier(self, phone_number: str) -> float:
        if self.is_admin_number(phone_number):
            return 10.0
        return 1.0

    def log_security_event(
        self, event_type: str, phone_number: str, details: Optional[Dict] = None
    ):
        logger.warning(
            "security_event",
            event_type=event_type,
            phone_number=self._clean_phone_number(phone_number),
            details=details or {},
        )
