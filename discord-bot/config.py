import os
from dotenv import load_dotenv

load_dotenv()

# Discord Configuration
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_COMMAND_PREFIX = os.getenv("DISCORD_COMMAND_PREFIX", "!")

# Vaquill Configuration
VAQUILL_API_KEY = os.getenv("VAQUILL_API_KEY")  # Bearer vq_key_...
VAQUILL_API_URL = os.getenv(
    "VAQUILL_API_URL", "https://api.vaquill.ai/api/v1"
)
VAQUILL_MODE = os.getenv("VAQUILL_MODE", "standard")  # standard | deep
VAQUILL_COUNTRY_CODE = os.getenv("VAQUILL_COUNTRY_CODE", "")  # IN, US, CA, etc.

# Rate Limiting Configuration
RATE_LIMIT_PER_USER = int(os.getenv("RATE_LIMIT_PER_USER", "10"))  # queries per window
RATE_LIMIT_PER_CHANNEL = int(os.getenv("RATE_LIMIT_PER_CHANNEL", "30"))  # queries per window
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))  # seconds

# Redis Configuration (for rate limiting)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Security Configuration
ALLOWED_CHANNELS = (
    os.getenv("ALLOWED_CHANNELS", "").split(",")
    if os.getenv("ALLOWED_CHANNELS")
    else []
)
ALLOWED_ROLES = (
    os.getenv("ALLOWED_ROLES", "").split(",")
    if os.getenv("ALLOWED_ROLES")
    else []
)
MAX_MESSAGE_LENGTH = int(os.getenv("MAX_MESSAGE_LENGTH", "2000"))

# Bot Configuration
ENABLE_STARTER_QUESTIONS = os.getenv("ENABLE_STARTER_QUESTIONS", "True").lower() == "true"
TYPING_INDICATOR = os.getenv("TYPING_INDICATOR", "True").lower() == "true"
ENABLE_SOURCES = os.getenv("ENABLE_SOURCES", "True").lower() == "true"
MAX_CHAT_HISTORY = int(os.getenv("MAX_CHAT_HISTORY", "20"))  # per-channel message pairs

ERROR_MESSAGES = {
    "rate_limit": "You've reached your query limit. Please wait a moment before asking again.",
    "api_error": "Sorry, I couldn't process your request. Please try again later.",
    "unauthorized": "You don't have permission to use this bot.",
    "invalid_input": "Please provide a valid question.",
}

# Starter Questions (legal-oriented defaults)
STARTER_QUESTIONS = [
    "What is Section 302 of IPC?",
    "Explain the doctrine of basic structure",
    "What are the grounds for divorce under Hindu Marriage Act?",
    "Summarize the Kesavananda Bharati case",
]
