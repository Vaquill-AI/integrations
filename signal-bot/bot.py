#!/usr/bin/env python3
"""
Vaquill Legal AI -- Signal Bot.

Answers legal questions via the Vaquill API, formats responses for Signal,
shows case-law sources, and maintains per-user conversation history.

Uses the signalbot framework which connects to signal-cli-rest-api via WebSocket.
"""

import logging
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from signalbot import Command, Config, Context, SignalBot, enable_console_logging

from config import STARTER_QUESTIONS, SUCCESS_MESSAGES, get_settings
from rate_limiter import RateLimiter
from vaquill_client import VaquillAPIError, VaquillClient

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Globals (initialised in main())
# ---------------------------------------------------------------------------
settings = get_settings()

vaquill = VaquillClient(
    api_key=settings.vaquill_api_key,
    api_url=settings.vaquill_api_url,
    mode=settings.vaquill_mode,
    country_code=settings.vaquill_country_code,
)

rate_limiter = RateLimiter(
    daily_limit=settings.rate_limit_per_user_per_day,
    minute_limit=settings.rate_limit_per_user_per_minute,
)

# Per-user conversation history: phone -> list of {role, content}
chat_histories: Dict[str, List[Dict[str, str]]] = defaultdict(list)

# Signal has no hard message limit but keep readable
SIGNAL_MAX_MESSAGE_LENGTH = 4000


# ===================================================================
# Signal text formatting helpers
# ===================================================================


def markdown_to_signal(text: str) -> str:
    """Convert markdown to Signal-compatible formatting.

    Signal supports: *bold*, _italic_, ~strikethrough~, ```code```, `inline`.
    It does NOT support links, headers, or HTML.
    """
    if not text:
        return ""

    # Headers -> bold text
    text = re.sub(r"^#{1,6}\s*(.+)$", r"*\1*", text, flags=re.MULTILINE)

    # **bold** or __bold__ -> *bold* (Signal uses single asterisk)
    text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)
    text = re.sub(r"__(.+?)__", r"*\1*", text)

    # Remove markdown links, keep text: [text](url) -> text (url)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", text)

    # Remove image markdown
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"[\1]", text)

    # Horizontal rules
    text = re.sub(r"^[\-\*_]{3,}$", "----------", text, flags=re.MULTILINE)

    # Clean up excessive whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def build_sources_text(sources: List[Dict[str, Any]]) -> str:
    """Format Vaquill sources for Signal."""
    if not sources:
        return ""

    lines = ["\n\n----------\n*Sources:*"]
    for i, src in enumerate(sources[:settings.max_sources_per_response], 1):
        case_name = src.get("caseName") or src.get("case_name") or "Source"
        citation = src.get("citation") or ""
        court = src.get("court") or ""
        pdf_url = src.get("pdfUrl") or src.get("pdf_url") or ""

        parts = [case_name]
        if citation:
            parts.append(f"({citation})")
        if court:
            parts.append(court)

        label = " ".join(parts)
        if pdf_url:
            lines.append(f"[{i}] *{label}*\n    {pdf_url}")
        else:
            lines.append(f"[{i}] *{label}*")

    return "\n".join(lines)


def chunk_message(text: str, max_length: int = SIGNAL_MAX_MESSAGE_LENGTH) -> List[str]:
    """Split long text into Signal-safe chunks at natural boundaries."""
    if len(text) <= max_length:
        return [text]

    chunks: List[str] = []
    remaining = text

    while remaining:
        if len(remaining) <= max_length:
            chunks.append(remaining)
            break

        chunk = remaining[:max_length]
        # Try to split at paragraph boundary
        last_para = chunk.rfind("\n\n")
        if last_para > max_length // 2:
            split_at = last_para
        else:
            last_nl = chunk.rfind("\n")
            if last_nl > max_length // 2:
                split_at = last_nl
            else:
                last_sent = max(
                    chunk.rfind(". "), chunk.rfind("! "), chunk.rfind("? ")
                )
                if last_sent > max_length // 2:
                    split_at = last_sent + 1
                else:
                    last_sp = chunk.rfind(" ")
                    split_at = last_sp if last_sp > max_length // 2 else max_length

        chunks.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].strip()

    return chunks


# ===================================================================
# Chat history helpers
# ===================================================================

MAX_HISTORY = settings.max_conversation_history


def _append_history(user_id: str, role: str, content: str) -> None:
    """Append a message to the chat history, trimming to MAX_HISTORY pairs."""
    chat_histories[user_id].append({"role": role, "content": content})
    limit = MAX_HISTORY * 2
    if len(chat_histories[user_id]) > limit:
        chat_histories[user_id] = chat_histories[user_id][-limit:]


def _get_history(user_id: str) -> List[Dict[str, str]]:
    """Return the chat history for the Vaquill API."""
    return list(chat_histories[user_id])


def _clear_history(user_id: str) -> None:
    """Wipe the chat history for a user."""
    chat_histories.pop(user_id, None)


# ===================================================================
# Command: handle all incoming messages
# ===================================================================


class LegalQueryCommand(Command):
    """Handle all incoming Signal messages.

    signalbot routes every message through registered commands.
    This is a catch-all that processes commands and legal questions.
    """

    async def handle(self, context: Context) -> None:
        """Process incoming message."""
        message = context.message
        text = (message.text or "").strip()
        sender = message.source  # E.164 phone number

        if not text or not sender:
            return

        # Access control
        if settings.allowed_users and sender not in settings.allowed_users:
            await context.send("Sorry, you're not authorized to use this bot.")
            return

        # Message length check
        if len(text) > settings.max_message_length:
            await context.send(
                f"Your message is too long. Please keep it under "
                f"{settings.max_message_length} characters."
            )
            return

        # Handle commands
        text_lower = text.lower().strip()

        if text_lower in {"help", "/help"}:
            help_text = SUCCESS_MESSAGES["help"].format(
                daily_limit=settings.rate_limit_per_user_per_day,
            )
            await context.send(help_text)
            return

        if text_lower in {"start", "/start", "hi", "hello", "hey"}:
            _clear_history(sender)
            await context.send(SUCCESS_MESSAGES["welcome"])
            return

        if text_lower in {"examples", "/examples"}:
            await self._send_examples(context)
            return

        if text_lower in {"stats", "/stats"}:
            stats = await rate_limiter.get_stats(sender)
            stats_text = (
                "*Your Usage Statistics*\n\n"
                f"Today's usage: {stats['daily_used']} / {stats['daily_limit']}\n"
                f"Remaining today: {stats['daily_remaining']}\n\n"
                f"Per-minute limit: {stats['minute_limit']} messages"
            )
            await context.send(stats_text)
            return

        if text_lower in {"clear", "/clear", "new", "new chat", "reset"}:
            _clear_history(sender)
            await context.send(
                "Conversation cleared. Send me a new question to start fresh."
            )
            return

        # Rate limit check
        allowed, err_msg, _ = await rate_limiter.check(sender)
        if not allowed:
            await context.send(err_msg)
            return

        # Process as legal question
        await self._process_question(context, sender, text)

    async def _process_question(
        self, context: Context, sender: str, question: str
    ) -> None:
        """Send question to Vaquill API and deliver formatted response."""
        # Show typing indicator
        try:
            await context.start_typing()
        except Exception:
            pass

        try:
            history = _get_history(sender)

            response = await vaquill.ask(
                question=question,
                chat_history=history if history else None,
                sources=True,
                max_sources=settings.max_sources_per_response,
            )

            answer = vaquill.extract_answer(response)
            sources = vaquill.extract_sources(response)

            if not answer:
                await context.send(
                    "I couldn't get a response. Please try again."
                )
                return

            # Record history
            _append_history(sender, "user", question)
            _append_history(sender, "assistant", answer)

            # Format for Signal
            formatted = markdown_to_signal(answer)
            sources_text = build_sources_text(sources)
            footer = (
                "\n\n_For acts, citation graphs, translations and more: "
                "https://app.vaquill.ai_"
            )

            full = formatted + sources_text + footer
            chunks = chunk_message(full)

            for chunk in chunks:
                await context.send(chunk)

            logger.info(
                "message handled: user=%s sources=%d chunks=%d",
                sender[:6] + "****",
                len(sources),
                len(chunks),
            )

        except VaquillAPIError as e:
            logger.error("Vaquill API error: %s", e)
            if e.status_code == 402:
                await context.send(
                    "The bot's API credits are exhausted. "
                    "Please contact the administrator."
                )
            elif e.status_code == 429:
                await context.send(
                    "The API is rate-limited right now. "
                    "Please wait a moment and try again."
                )
            else:
                await context.send(
                    "Something went wrong. Please try again later."
                )
        except Exception:
            logger.exception(
                "unexpected error handling message for user=%s",
                sender[:6] + "****",
            )
            await context.send(
                "An unexpected error occurred. Please try again later."
            )
        finally:
            try:
                await context.stop_typing()
            except Exception:
                pass

    async def _send_examples(self, context: Context) -> None:
        """Send example questions grouped by category."""
        lines = ["*Example Questions:*\n"]

        for category, questions in STARTER_QUESTIONS.items():
            cat_name = category.replace("_", " ").title()
            lines.append(f"\n*{cat_name}:*")
            for i, q in enumerate(questions, 1):
                lines.append(f"  {i}. {q}")

        lines.append("\nJust copy and send any question, or type your own.")
        await context.send("\n".join(lines))


# ===================================================================
# Bot setup and entry point
# ===================================================================


def main() -> None:
    """Entry point. Build the SignalBot and start listening."""
    if not settings.signal_phone_number:
        logger.error("SIGNAL_PHONE_NUMBER is not set")
        return
    if not settings.vaquill_api_key:
        logger.error("VAQUILL_API_KEY is not set")
        return

    enable_console_logging(logging.INFO)

    config = Config(
        signal_service=settings.signal_service_url,
        phone_number=settings.signal_phone_number,
    )

    bot = SignalBot(config)

    # Register the catch-all command for all contacts and groups
    bot.register(LegalQueryCommand())

    logger.info(
        "Vaquill Signal bot starting (phone=%s, mode=%s)",
        settings.signal_phone_number[:6] + "****",
        settings.vaquill_mode,
    )
    bot.start()


if __name__ == "__main__":
    main()
