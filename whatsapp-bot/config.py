"""
Configuration for Vaquill WhatsApp Bot.
"""

import os
from typing import List, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Config(BaseSettings):
    """Bot configuration loaded from environment variables."""

    # Vaquill API settings
    VAQUILL_API_KEY: str
    VAQUILL_API_URL: str = "https://api.vaquill.ai/api/v1"
    VAQUILL_MODE: str = "standard"  # "standard" or "deep"
    VAQUILL_COUNTRY_CODE: str = "IN"  # Default jurisdiction

    # Twilio settings
    TWILIO_ACCOUNT_SID: str
    TWILIO_AUTH_TOKEN: str
    TWILIO_WHATSAPP_NUMBER: str  # Format: whatsapp:+14155238886

    # Rate limiting
    RATE_LIMIT_DAILY: int = 100
    RATE_LIMIT_MINUTE: int = 5
    RATE_LIMIT_HOUR: int = 30

    # Security
    ALLOWED_NUMBERS: Optional[List[str]] = None
    BLOCKED_NUMBERS: Optional[List[str]] = None
    MAX_MESSAGE_LENGTH: int = 1000
    ENABLE_PROFANITY_FILTER: bool = False

    # Features
    ENABLE_VOICE_MESSAGES: bool = True
    ENABLE_MEDIA_RESPONSES: bool = True
    ENABLE_LOCATION_SHARING: bool = False
    ENABLE_THINKING_MESSAGE: bool = False
    DEFAULT_LANGUAGE: str = "en"

    # Redis (optional — in-memory fallback when not set)
    REDIS_URL: Optional[str] = None

    # Admin
    ADMIN_API_KEY: Optional[str] = None
    ADMIN_NUMBERS: Optional[List[str]] = None

    # Session
    SESSION_TIMEOUT_MINUTES: int = 30
    SESSION_CONTEXT_MESSAGES: int = 10

    # Analytics
    ENABLE_ANALYTICS: bool = True
    ANALYTICS_RETENTION_DAYS: int = 30

    # Logging
    LOG_LEVEL: str = "INFO"

    # Server
    PORT: int = 8000
    DEBUG: bool = False

    @field_validator("ALLOWED_NUMBERS", "BLOCKED_NUMBERS", "ADMIN_NUMBERS", mode="before")
    @classmethod
    def split_numbers(cls, v):
        if v:
            return [num.strip() for num in v.split(",")]
        return []

    @field_validator("TWILIO_WHATSAPP_NUMBER", mode="before")
    @classmethod
    def validate_whatsapp_number(cls, v):
        if v and not v.startswith("whatsapp:"):
            return f"whatsapp:{v}"
        return v

    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
    }


# ---------------------------------------------------------------------------
# Starter questions — legal domain
# ---------------------------------------------------------------------------

STARTER_QUESTIONS = {
    "general": [
        "What is Section 302 of the Indian Penal Code?",
        "Explain the difference between bail and anticipatory bail",
        "What are the grounds for divorce under Hindu Marriage Act?",
        "How does Article 21 protect fundamental rights?",
    ],
    "criminal": [
        "What is the procedure for filing an FIR?",
        "Explain the concept of mens rea in Indian criminal law",
        "What are the stages of a criminal trial?",
        "When can police arrest without a warrant?",
    ],
    "civil": [
        "What is the limitation period for a civil suit?",
        "How do I file a consumer complaint?",
        "What are the remedies for breach of contract?",
        "Explain the process of executing a court decree",
    ],
    "constitutional": [
        "What are the Fundamental Rights under the Indian Constitution?",
        "Explain the concept of judicial review",
        "What is a PIL and who can file one?",
        "How does the separation of powers work in India?",
    ],
}

# ---------------------------------------------------------------------------
# Response templates
# ---------------------------------------------------------------------------

RESPONSE_TEMPLATES = {
    "welcome": """Welcome to *Vaquill Legal AI* on WhatsApp!

I can help you research Indian law — statutes, case law, and legal concepts.

You can:
- Ask me any legal question
- Use /help to see available commands
- Send /examples for sample questions

How can I assist you today?""",
    "help": """*Available Commands:*

/start - Start a new conversation
/help - Show this help message
/examples - Show example questions
/stats - View your usage statistics
/mode [standard|deep] - Switch research mode
/clear - Clear conversation history
/feedback [message] - Send feedback

*Tips:*
- Just type your legal question naturally
- I remember our conversation context
- Your daily limit is {daily_limit} messages

Need help? Just ask!""",
    "rate_limit_daily": """Daily limit reached ({daily_limit} messages).

Your limit resets at midnight.

Stats: {daily_used}/{daily_limit} messages used today.""",
    "rate_limit_minute": """Slow down! You've sent too many messages.

Please wait {seconds} seconds before sending another message.

Current rate: {minute_used}/{minute_limit} messages per minute.""",
    "error": """Sorry, something went wrong.

Please try again. If the problem persists, contact support.""",
    "no_response": """I couldn't find an answer to that question.

Try rephrasing or asking something else. Type /examples to see what I can help with.""",
    "session_expired": """Your session has expired.

Starting a new conversation. Your previous context has been cleared.""",
    "feedback_received": """Thank you for your feedback!

Your message has been recorded and will help us improve.""",
    "stats": """*Your Usage Statistics*

*Today:* {daily_used}/{daily_limit} messages
*This hour:* {hourly_used}/{hourly_limit} messages
*Total messages:* {total_messages}
*Member since:* {member_since}""",
    "mode_changed": """Research mode changed to *{mode}*.

{description}""",
}

# ---------------------------------------------------------------------------
# Supported languages
# ---------------------------------------------------------------------------

SUPPORTED_LANGUAGES = {
    "en": "English",
    "hi": "Hindi",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "pt": "Portuguese",
    "ja": "Japanese",
    "ko": "Korean",
    "zh": "Chinese",
    "ar": "Arabic",
}

# ---------------------------------------------------------------------------
# Error messages
# ---------------------------------------------------------------------------

ERROR_MESSAGES = {
    "unauthorized": "You are not authorized to use this bot.",
    "blocked": "Your number has been blocked.",
    "invalid_message": "Invalid message format.",
    "message_too_long": "Message too long. Maximum 1000 characters.",
    "profanity_detected": "Please keep the conversation respectful.",
    "invalid_command": "Unknown command. Type /help for available commands.",
    "invalid_language": "Unsupported language. Available: "
    + ", ".join(SUPPORTED_LANGUAGES.keys()),
    "session_error": "Could not create session. Please try again.",
    "api_error": "API error occurred. Please try again later.",
    "media_not_supported": "Media files are not supported. Please send text only.",
    "voice_not_supported": "Voice messages are not supported. Please send text.",
    "insufficient_credits": "Insufficient API credits. Please contact support.",
}
