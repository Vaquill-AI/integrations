"""
Configuration for Vaquill Slack Bot.
"""

import os
from typing import Optional, List

from dotenv import load_dotenv

load_dotenv()


class Config:
    """Bot configuration loaded from environment variables."""

    # -- Slack ----------------------------------------------------------------
    SLACK_BOT_TOKEN: str = os.environ.get("SLACK_BOT_TOKEN", "")
    SLACK_SIGNING_SECRET: str = os.environ.get("SLACK_SIGNING_SECRET", "")
    SLACK_APP_TOKEN: Optional[str] = os.environ.get("SLACK_APP_TOKEN")  # Socket Mode

    # -- Vaquill API ----------------------------------------------------------
    VAQUILL_API_KEY: str = os.environ.get("VAQUILL_API_KEY", "")
    VAQUILL_API_URL: str = os.environ.get(
        "VAQUILL_API_URL", "https://api.vaquill.ai/api/v1"
    )
    VAQUILL_MODE: str = os.environ.get("VAQUILL_MODE", "standard")
    VAQUILL_COUNTRY_CODE: Optional[str] = os.environ.get("VAQUILL_COUNTRY_CODE")

    # -- Rate Limiting --------------------------------------------------------
    RATE_LIMIT_PER_USER: int = int(os.environ.get("RATE_LIMIT_PER_USER", "20"))
    RATE_LIMIT_PER_CHANNEL: int = int(os.environ.get("RATE_LIMIT_PER_CHANNEL", "100"))
    RATE_LIMIT_WINDOW_USER: int = 60  # seconds
    RATE_LIMIT_WINDOW_CHANNEL: int = 3600  # seconds

    # -- Redis (optional, for distributed rate limiting) ----------------------
    REDIS_URL: Optional[str] = os.environ.get("REDIS_URL")

    # -- Bot Behaviour --------------------------------------------------------
    MAX_MESSAGE_LENGTH: int = int(os.environ.get("MAX_MESSAGE_LENGTH", "4000"))
    SHOW_SOURCES: bool = os.environ.get("SHOW_SOURCES", "true").lower() == "true"
    ENABLE_THREADING: bool = (
        os.environ.get("ENABLE_THREADING", "true").lower() == "true"
    )

    # -- Security -------------------------------------------------------------
    ALLOWED_CHANNELS: Optional[str] = os.environ.get("ALLOWED_CHANNELS")
    BLOCKED_USERS: Optional[str] = os.environ.get("BLOCKED_USERS")

    # -- Logging --------------------------------------------------------------
    LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")

    # -- Analytics ------------------------------------------------------------
    ENABLE_ANALYTICS: bool = (
        os.environ.get("ENABLE_ANALYTICS", "true").lower() == "true"
    )
    ANALYTICS_ENDPOINT: Optional[str] = os.environ.get("ANALYTICS_ENDPOINT")

    # -- Conversation Management ----------------------------------------------
    CONVERSATION_TIMEOUT: int = int(
        os.environ.get("CONVERSATION_TIMEOUT", "86400")
    )  # 24 h
    MAX_CONTEXT_MESSAGES: int = int(os.environ.get("MAX_CONTEXT_MESSAGES", "10"))

    # -- Thread Follow-up -----------------------------------------------------
    THREAD_FOLLOW_UP_ENABLED: bool = (
        os.environ.get("THREAD_FOLLOW_UP_ENABLED", "true").lower() == "true"
    )
    THREAD_FOLLOW_UP_TIMEOUT: int = int(
        os.environ.get("THREAD_FOLLOW_UP_TIMEOUT", "3600")
    )  # 1 h
    THREAD_FOLLOW_UP_MAX_MESSAGES: int = int(
        os.environ.get("THREAD_FOLLOW_UP_MAX_MESSAGES", "50")
    )
    IGNORE_BOT_MESSAGES: bool = (
        os.environ.get("IGNORE_BOT_MESSAGES", "true").lower() == "true"
    )

    # -- Helpers --------------------------------------------------------------

    @classmethod
    def validate(cls) -> bool:
        """Validate that all required env vars are set."""
        required = ["SLACK_BOT_TOKEN", "SLACK_SIGNING_SECRET", "VAQUILL_API_KEY"]
        missing = [f for f in required if not getattr(cls, f)]
        if missing:
            raise ValueError(f"Missing required configuration: {', '.join(missing)}")
        return True

    @classmethod
    def get_allowed_channels(cls) -> Optional[List[str]]:
        if cls.ALLOWED_CHANNELS:
            return [ch.strip() for ch in cls.ALLOWED_CHANNELS.split(",")]
        return None

    @classmethod
    def get_blocked_users(cls) -> Optional[List[str]]:
        if cls.BLOCKED_USERS:
            return [u.strip() for u in cls.BLOCKED_USERS.split(",")]
        return None
