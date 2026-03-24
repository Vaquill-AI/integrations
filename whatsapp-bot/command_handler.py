"""
Slash-command handler for the Vaquill WhatsApp bot.
"""

from datetime import datetime
from typing import Optional

import structlog

from config import (
    Config,
    RESPONSE_TEMPLATES,
    STARTER_QUESTIONS,
    SUPPORTED_LANGUAGES,
)
from session_manager import SessionManager
from rate_limiter import RateLimiter

logger = structlog.get_logger()

# Mode descriptions shown after switching
MODE_DESCRIPTIONS = {
    "standard": "Standard mode uses 18 retrieval techniques with gpt-5-mini. Best for quick lookups.",
    "deep": "Deep mode uses 35 retrieval techniques with gpt-5.2, multi-hop reasoning, and hallucination detection. Best for complex legal research.",
}


class CommandHandler:
    def __init__(
        self,
        session_manager: SessionManager,
        rate_limiter: RateLimiter,
        config: Config,
    ):
        self.session_manager = session_manager
        self.rate_limiter = rate_limiter
        self.config = config

        self.commands = {
            "/start": self.handle_start,
            "/help": self.handle_help,
            "/examples": self.handle_examples,
            "/stats": self.handle_stats,
            "/mode": self.handle_mode,
            "/language": self.handle_language,
            "/clear": self.handle_clear,
            "/feedback": self.handle_feedback,
            "/about": self.handle_about,
            "/settings": self.handle_settings,
        }

    async def handle_command(self, user_id: str, message: str) -> str:
        parts = message.split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        handler = self.commands.get(command)
        if not handler:
            return f"Unknown command: {command}\n\nType /help to see available commands."

        try:
            return await handler(user_id, args)
        except Exception as e:
            logger.error("command_error", command=command, error=str(e))
            return "An error occurred while processing the command. Please try again."

    # -- individual commands ----------------------------------------------

    async def handle_start(self, user_id: str, args: str) -> str:
        await self.session_manager.clear_session(user_id)
        await self.session_manager.create_session(user_id)

        welcome = RESPONSE_TEMPLATES["welcome"]
        welcome += "\n\n*Try these questions:*\n"
        for i, q in enumerate(STARTER_QUESTIONS["general"][:3], 1):
            welcome += f"{i}. {q}\n"
        return welcome

    async def handle_help(self, user_id: str, args: str) -> str:
        return RESPONSE_TEMPLATES["help"].format(
            daily_limit=self.config.RATE_LIMIT_DAILY
        )

    async def handle_examples(self, user_id: str, args: str) -> str:
        text = "*Example Legal Questions*\n\n"

        if args and args.lower() in STARTER_QUESTIONS:
            category = args.lower()
            text += f"*{category.title()} Questions:*\n"
            for i, q in enumerate(STARTER_QUESTIONS[category], 1):
                text += f"{i}. {q}\n"
        else:
            for category, questions in STARTER_QUESTIONS.items():
                text += f"\n*{category.title()}:*\n"
                for q in questions[:2]:
                    text += f"  - {q}\n"
            text += "\nUse `/examples [category]` to see more from a specific category."

        return text

    async def handle_stats(self, user_id: str, args: str) -> str:
        stats = await self.rate_limiter.get_user_stats(user_id)
        session = await self.session_manager.get_session(user_id)

        if session and "created_at" in session:
            member_since = datetime.fromisoformat(session["created_at"]).strftime(
                "%Y-%m-%d"
            )
        else:
            member_since = "Today"

        return RESPONSE_TEMPLATES["stats"].format(
            daily_used=stats["daily"]["used"],
            daily_limit=stats["daily"]["limit"],
            hourly_used=stats.get("hourly", {}).get("used", 0),
            hourly_limit=self.config.RATE_LIMIT_HOUR,
            total_messages=stats.get("monthly", {}).get("used", 0),
            member_since=member_since,
        )

    async def handle_mode(self, user_id: str, args: str) -> str:
        current_mode = (
            await self.session_manager.get_user_mode(user_id)
        ) or self.config.VAQUILL_MODE

        if not args:
            return (
                f"*Current mode:* {current_mode}\n\n"
                f"Available modes:\n"
                f"  - *standard* — {MODE_DESCRIPTIONS['standard']}\n"
                f"  - *deep* — {MODE_DESCRIPTIONS['deep']}\n\n"
                f"Switch with: `/mode standard` or `/mode deep`"
            )

        mode = args.strip().lower()
        if mode not in ("standard", "deep"):
            return f"Invalid mode: {mode}. Use `standard` or `deep`."

        session = await self.session_manager.get_session(user_id)
        if not session:
            await self.session_manager.create_session(user_id)

        await self.session_manager.set_mode(user_id, mode)

        return RESPONSE_TEMPLATES["mode_changed"].format(
            mode=mode,
            description=MODE_DESCRIPTIONS[mode],
        )

    async def handle_language(self, user_id: str, args: str) -> str:
        if not args:
            current = await self.session_manager.get_user_language(user_id)
            lang_list = "\n".join(
                f"  - {code} — {name}" for code, name in SUPPORTED_LANGUAGES.items()
            )
            return (
                f"*Current language:* {SUPPORTED_LANGUAGES.get(current, current)}\n\n"
                f"*Available languages:*\n{lang_list}\n\n"
                f"To change: `/language [code]`\nExample: `/language hi` for Hindi"
            )

        code = args.lower().strip()
        if code not in SUPPORTED_LANGUAGES:
            return f"Unsupported language: {code}\n\nAvailable: {', '.join(SUPPORTED_LANGUAGES.keys())}"

        session = await self.session_manager.get_session(user_id)
        if not session:
            await self.session_manager.create_session(user_id)

        success = await self.session_manager.set_language(user_id, code)
        if success:
            return f"Language changed to {SUPPORTED_LANGUAGES[code]}."
        return "Failed to change language. Please try again."

    async def handle_clear(self, user_id: str, args: str) -> str:
        await self.session_manager.clear_session(user_id)
        await self.session_manager.create_session(user_id)
        return "Conversation cleared! Starting fresh.\n\nHow can I help you?"

    async def handle_feedback(self, user_id: str, args: str) -> str:
        if not args:
            return (
                "*Send Feedback*\n\n"
                "Please provide your feedback after the command.\n"
                "Example: `/feedback The bot is very helpful!`"
            )
        logger.info("user_feedback", user_id=user_id, feedback=args)
        return RESPONSE_TEMPLATES["feedback_received"]

    async def handle_about(self, user_id: str, args: str) -> str:
        return (
            "*About Vaquill Legal AI*\n\n"
            "Vaquill is an AI-powered legal research assistant that helps "
            "lawyers and legal professionals find relevant case law, "
            "statutes, and legal principles.\n\n"
            "Powered by RAG (Retrieval-Augmented Generation) with access to "
            "millions of Indian court judgments.\n\n"
            "Website: https://vaquill.ai\n"
            "Type /help to see what I can do!"
        )

    async def handle_settings(self, user_id: str, args: str) -> str:
        session = await self.session_manager.get_session(user_id)
        current_lang = session.get("language", "en") if session else "en"
        current_mode = session.get("mode", self.config.VAQUILL_MODE) if session else self.config.VAQUILL_MODE
        stats = await self.rate_limiter.get_user_stats(user_id)

        return (
            "*Your Settings*\n\n"
            f"*Language:* {SUPPORTED_LANGUAGES.get(current_lang, current_lang)}\n"
            f"*Mode:* {current_mode}\n"
            f"*Daily limit:* {stats['daily']['used']}/{self.config.RATE_LIMIT_DAILY}\n"
            f"*Session timeout:* {self.config.SESSION_TIMEOUT_MINUTES} minutes\n\n"
            "*Available Settings:*\n"
            "  - `/language [code]` — Change language\n"
            "  - `/mode [standard|deep]` — Switch research mode\n"
            "  - `/clear` — Clear conversation history\n"
            "  - `/feedback [message]` — Send feedback"
        )
