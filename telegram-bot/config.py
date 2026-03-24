"""Configuration for the Vaquill Telegram Bot."""

import os
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Bot settings loaded from environment variables."""

    # Telegram
    telegram_bot_token: str = Field(..., alias="TELEGRAM_BOT_TOKEN")

    # Vaquill API
    vaquill_api_url: str = Field(
        "https://api.vaquill.ai/api/v1", alias="VAQUILL_API_URL"
    )
    vaquill_api_key: str = Field(..., alias="VAQUILL_API_KEY")
    vaquill_mode: str = Field("standard", alias="VAQUILL_MODE")
    vaquill_country_code: Optional[str] = Field(None, alias="VAQUILL_COUNTRY_CODE")

    # Rate limiting
    rate_limit_per_user_per_day: int = Field(
        100, alias="RATE_LIMIT_PER_USER_PER_DAY"
    )
    rate_limit_per_user_per_minute: int = Field(
        5, alias="RATE_LIMIT_PER_USER_PER_MINUTE"
    )

    # Security
    max_message_length: int = Field(4000, alias="MAX_MESSAGE_LENGTH")
    allowed_users: Optional[List[int]] = Field(None, alias="ALLOWED_USERS")

    # Bot behaviour
    max_conversation_history: int = Field(10, alias="MAX_CONVERSATION_HISTORY")
    max_sources_per_response: int = Field(5, alias="MAX_SOURCES_PER_RESPONSE")

    # Observability
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    sentry_dsn: Optional[str] = Field(None, alias="SENTRY_DSN")

    # Environment
    environment: str = Field("development", alias="ENVIRONMENT")

    @field_validator("allowed_users", mode="before")
    @classmethod
    def parse_allowed_users(cls, v):
        if isinstance(v, str) and v:
            return [int(uid.strip()) for uid in v.split(",")]
        return None

    model_config = {"env_file": ".env", "case_sensitive": False}


# ---------------------------------------------------------------------------
# Starter questions — legal-oriented for Vaquill
# ---------------------------------------------------------------------------

STARTER_QUESTIONS = {
    "indian_law": [
        "What is Section 302 of the IPC?",
        "Explain the Right to Information Act",
        "What are the grounds for divorce under Hindu Marriage Act?",
    ],
    "us_law": [
        "What is the 4th Amendment?",
        "Explain Miranda rights",
        "What is the difference between civil and criminal law?",
    ],
    "general": [
        "What can you help me with?",
        "How do I search for a legal case?",
        "What jurisdictions do you cover?",
    ],
}

# ---------------------------------------------------------------------------
# Message templates
# ---------------------------------------------------------------------------

ERROR_MESSAGES = {
    "rate_limit": "You've reached your message limit. Please try again later.",
    "unauthorized": "Sorry, you're not authorized to use this bot.",
    "api_error": "Something went wrong. Please try again later.",
    "message_too_long": "Your message is too long. Please keep it under {max_length} characters.",
    "insufficient_credits": "The Vaquill API key has insufficient credits. Please contact the bot administrator.",
}

SUCCESS_MESSAGES = {
    "welcome": (
        "<b>Welcome to Vaquill Legal AI!</b>\n\n"
        "I can help you research Indian and US legal questions, "
        "find case law, and understand statutes.\n\n"
        "You can:\n"
        "- Ask me questions directly\n"
        "- Use /help to see available commands\n"
        "- Click the buttons below for example questions\n\n"
        "How can I assist you today?"
    ),
    "help": (
        "<b>Available Commands:</b>\n\n"
        "/start - Start a new conversation\n"
        "/help  - Show this help message\n"
        "/examples - Show example questions\n"
        "/stats - View your usage statistics\n"
        "/clear - Clear conversation history\n\n"
        "<b>Tips:</b>\n"
        "- Just type your question naturally\n"
        "- I remember our conversation context\n"
        "- Your daily limit is {daily_limit} messages\n"
    ),
    "examples_intro": "Here are some questions you can ask:",
}


def get_settings() -> Settings:
    """Return a Settings instance (reads from env / .env)."""
    return Settings()
