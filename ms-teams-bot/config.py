"""
Configuration for Vaquill Microsoft Teams Bot
"""

import os
from typing import Optional, List
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Bot configuration"""

    # Microsoft Teams Configuration
    TEAMS_APP_ID: str = os.environ.get("TEAMS_APP_ID", "")
    TEAMS_APP_PASSWORD: str = os.environ.get("TEAMS_APP_PASSWORD", "")
    TEAMS_APP_TYPE: str = os.environ.get(
        "TEAMS_APP_TYPE", "MultiTenant"
    )  # MultiTenant, SingleTenant, or Managed
    TEAMS_TENANT_ID: Optional[str] = os.environ.get(
        "TEAMS_TENANT_ID"
    )  # Required for SingleTenant

    # Bot Framework Configuration
    BOT_OPENID_METADATA: str = os.environ.get(
        "BOT_OPENID_METADATA",
        "https://login.microsoftonline.com/common/v2.0/.well-known/openid-configuration",
    )

    # Vaquill Configuration
    VAQUILL_API_KEY: str = os.environ.get("VAQUILL_API_KEY", "")
    VAQUILL_API_URL: str = os.environ.get(
        "VAQUILL_API_URL", "https://api.vaquill.ai/api/v1"
    )
    VAQUILL_MODE: str = os.environ.get("VAQUILL_MODE", "standard")
    VAQUILL_COUNTRY_CODE: Optional[str] = os.environ.get("VAQUILL_COUNTRY_CODE")

    # Rate Limiting Configuration
    RATE_LIMIT_PER_USER: int = int(os.environ.get("RATE_LIMIT_PER_USER", "20"))
    RATE_LIMIT_PER_CHANNEL: int = int(os.environ.get("RATE_LIMIT_PER_CHANNEL", "100"))
    RATE_LIMIT_PER_TENANT: int = int(os.environ.get("RATE_LIMIT_PER_TENANT", "500"))
    RATE_LIMIT_WINDOW_USER: int = 60  # seconds
    RATE_LIMIT_WINDOW_CHANNEL: int = 3600  # seconds
    RATE_LIMIT_WINDOW_TENANT: int = 3600  # seconds

    # Redis Configuration (optional, for distributed rate limiting)
    REDIS_URL: Optional[str] = os.environ.get("REDIS_URL")
    REDIS_SSL: bool = os.environ.get("REDIS_SSL", "false").lower() == "true"

    # Bot Behavior Configuration
    MAX_MESSAGE_LENGTH: int = int(os.environ.get("MAX_MESSAGE_LENGTH", "4000"))
    SHOW_SOURCES: bool = os.environ.get("SHOW_SOURCES", "true").lower() == "true"
    MAX_SOURCES: int = int(os.environ.get("MAX_SOURCES", "5"))
    ENABLE_THREADING: bool = (
        os.environ.get("ENABLE_THREADING", "true").lower() == "true"
    )
    RESPONSE_TIMEOUT: int = int(os.environ.get("RESPONSE_TIMEOUT", "60"))

    # Teams-Specific Configuration
    REQUIRE_MENTION_IN_CHANNELS: bool = (
        os.environ.get("REQUIRE_MENTION_IN_CHANNELS", "true").lower() == "true"
    )
    RESPOND_TO_OTHER_BOTS: bool = (
        os.environ.get("RESPOND_TO_OTHER_BOTS", "false").lower() == "true"
    )
    ENABLE_ADAPTIVE_CARDS: bool = (
        os.environ.get("ENABLE_ADAPTIVE_CARDS", "true").lower() == "true"
    )

    # Security Configuration
    ALLOWED_TENANTS: Optional[str] = os.environ.get("ALLOWED_TENANTS")
    ALLOWED_CHANNELS: Optional[str] = os.environ.get("ALLOWED_CHANNELS")
    BLOCKED_USERS: Optional[str] = os.environ.get("BLOCKED_USERS")
    ENABLE_AUDIT_LOGGING: bool = (
        os.environ.get("ENABLE_AUDIT_LOGGING", "true").lower() == "true"
    )

    # Conversation Management
    CONVERSATION_TIMEOUT: int = int(
        os.environ.get("CONVERSATION_TIMEOUT", "86400")
    )  # 24 hours
    MAX_CONTEXT_MESSAGES: int = int(os.environ.get("MAX_CONTEXT_MESSAGES", "10"))
    ENABLE_CONVERSATION_HISTORY: bool = (
        os.environ.get("ENABLE_CONVERSATION_HISTORY", "true").lower() == "true"
    )

    # Logging Configuration
    LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Server Configuration
    PORT: int = int(os.environ.get("PORT", "3978"))
    HOST: str = os.environ.get("HOST", "0.0.0.0")

    @classmethod
    def validate(cls) -> bool:
        """Validate required configuration"""
        required_fields = [
            "TEAMS_APP_ID",
            "TEAMS_APP_PASSWORD",
            "VAQUILL_API_KEY",
        ]

        if cls.TEAMS_APP_TYPE == "SingleTenant" and not cls.TEAMS_TENANT_ID:
            raise ValueError("TEAMS_TENANT_ID is required for SingleTenant apps")

        missing = []
        for field in required_fields:
            if not getattr(cls, field):
                missing.append(field)

        if missing:
            raise ValueError(f"Missing required configuration: {', '.join(missing)}")

        return True

    @classmethod
    def get_allowed_tenants(cls) -> Optional[List[str]]:
        """Get list of allowed tenants"""
        if cls.ALLOWED_TENANTS:
            return [t.strip() for t in cls.ALLOWED_TENANTS.split(",")]
        return None

    @classmethod
    def get_allowed_channels(cls) -> Optional[List[str]]:
        """Get list of allowed channels"""
        if cls.ALLOWED_CHANNELS:
            return [ch.strip() for ch in cls.ALLOWED_CHANNELS.split(",")]
        return None

    @classmethod
    def get_blocked_users(cls) -> Optional[List[str]]:
        """Get list of blocked users"""
        if cls.BLOCKED_USERS:
            return [u.strip() for u in cls.BLOCKED_USERS.split(",")]
        return None

    @classmethod
    def is_tenant_allowed(cls, tenant_id: str) -> bool:
        """Check if tenant is allowed"""
        allowed_tenants = cls.get_allowed_tenants()
        if not allowed_tenants:
            return True
        return tenant_id in allowed_tenants

    @classmethod
    def is_channel_allowed(cls, channel_id: str) -> bool:
        """Check if channel is allowed"""
        allowed_channels = cls.get_allowed_channels()
        if not allowed_channels:
            return True
        return channel_id in allowed_channels

    @classmethod
    def is_user_blocked(cls, user_id: str) -> bool:
        """Check if user is blocked"""
        blocked_users = cls.get_blocked_users()
        if not blocked_users:
            return False
        return user_id in blocked_users
