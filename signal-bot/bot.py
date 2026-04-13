#!/usr/bin/env python3
"""
Vaquill Legal AI -- Signal Bot.

Answers legal questions via the Vaquill API, formats responses for Signal,
shows case-law sources with PDF links, renders tables as images,
and maintains per-user conversation history with LRU eviction.

Uses the signalbot framework which connects to signal-cli-rest-api via WebSocket.
The framework handles reconnection automatically with exponential backoff.
"""

import logging
import re
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from signalbot import Command, Config, ConnectionMode, Context, SignalBot, enable_console_logging

from config import STARTER_QUESTIONS, SUCCESS_MESSAGES, get_settings
from conversation_manager import ConversationManager
from dedup import MessageDeduplicator
from rate_limiter import RateLimiter
from security_manager import mask_phone, sanitize_input, validate_message
from vaquill_client import VaquillAPIError, VaquillClient

# ---------------------------------------------------------------------------
# Optional Pillow import (table -> image)
# ---------------------------------------------------------------------------
try:
    from PIL import Image, ImageDraw, ImageFont

    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False

# ---------------------------------------------------------------------------
# Logging + Sentry
# ---------------------------------------------------------------------------
load_dotenv()
settings = get_settings()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
)
logger = logging.getLogger(__name__)

if settings.sentry_dsn:
    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.environment,
            traces_sample_rate=0.1,
        )
        logger.info("Sentry initialized")
    except ImportError:
        logger.warning("sentry_dsn configured but sentry-sdk not installed")

# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------

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

conversations = ConversationManager(
    max_history_pairs=settings.max_conversation_history,
    max_users=5000,
    ttl_seconds=3600,
)

dedup = MessageDeduplicator(max_entries=2000)

# Signal has no hard message limit but keep readable
SIGNAL_MAX_MESSAGE_LENGTH = 4000


# ===================================================================
# Table extraction and image rendering (from telegram bot)
# ===================================================================


def extract_markdown_tables(
    text: str,
) -> List[Tuple[str, List[str], List[List[str]]]]:
    """Extract markdown tables from text.

    Returns a list of (original_table_text, headers, rows) tuples.
    """
    tables: List[Tuple[str, List[str], List[List[str]]]] = []
    lines = text.split("\n")
    current_lines: List[str] = []
    headers: List[str] = []
    rows: List[List[str]] = []
    in_table = False

    for line in lines:
        is_table_line = "|" in line and (
            line.strip().startswith("|") or line.strip().count("|") >= 2
        )
        is_separator = is_table_line and bool(
            re.match(r"^\s*\|[-:\s|]+\|\s*$", line)
        )

        if is_table_line:
            if not in_table:
                in_table = True
                current_lines = []
                headers = []
                rows = []
            current_lines.append(line)
            if not is_separator:
                cells = [c.strip() for c in line.split("|") if c.strip()]
                if not headers:
                    headers = cells
                else:
                    rows.append(cells)
        else:
            if in_table and headers and rows:
                tables.append(("\n".join(current_lines), headers, rows))
            in_table = False
            current_lines, headers, rows = [], [], []

    if in_table and headers and rows:
        tables.append(("\n".join(current_lines), headers, rows))

    return tables


def _clean_cell(text: str) -> str:
    """Strip markdown formatting from a table cell."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"_(.+?)_", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return text.strip()


def _wrap_text(text: str, font, max_width: int, draw) -> List[str]:
    """Word-wrap text to fit within max_width pixels."""
    if not text:
        return [""]
    words = text.split()
    lines: List[str] = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip() if current else word
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def generate_table_image(
    headers: List[str],
    rows: List[List[str]],
    max_width: int = 1200,
    padding: int = 12,
    font_size: int = 14,
    header_font_size: int = 15,
) -> Optional[BytesIO]:
    """Render a markdown table as a PNG image."""
    if not PILLOW_AVAILABLE or not headers or not rows:
        return None

    try:
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
        ]
        font = header_font = None
        for path in font_paths:
            try:
                font = ImageFont.truetype(path, font_size)
                header_font = ImageFont.truetype(path, header_font_size)
                break
            except Exception:
                continue
        if font is None:
            font = ImageFont.load_default()
            header_font = font

        headers = [_clean_cell(h) for h in headers]
        rows = [[_clean_cell(c) for c in row] for row in rows]

        tmp = Image.new("RGB", (1, 1))
        draw = ImageDraw.Draw(tmp)
        bbox = draw.textbbox((0, 0), "Hg", font=font)
        line_h = bbox[3] - bbox[1] + 4

        num_cols = len(headers)
        available = max_width - padding * 2
        if num_cols == 2:
            col_widths = [int(available * 0.30), int(available * 0.70)]
        else:
            col_widths = [available // num_cols] * num_cols

        wrapped_headers = [
            _wrap_text(h, header_font, col_widths[i] - padding * 2, draw)
            for i, h in enumerate(headers)
        ]
        header_height = max(len(w) for w in wrapped_headers) * line_h + padding * 2

        wrapped_rows: List[List[List[str]]] = []
        row_heights: List[int] = []
        for row in rows:
            wr: List[List[str]] = []
            max_lines = 1
            for i, cell in enumerate(row):
                if i < len(col_widths):
                    w = _wrap_text(cell, font, col_widths[i] - padding * 2, draw)
                    wr.append(w)
                    max_lines = max(max_lines, len(w))
            wrapped_rows.append(wr)
            row_heights.append(max_lines * line_h + padding * 2)

        total_w = sum(col_widths) + padding * 2
        total_h = header_height + sum(row_heights) + padding * 2

        img = Image.new("RGB", (total_w, total_h), color="#FFFFFF")
        draw = ImageDraw.Draw(img)

        header_bg, header_fg = "#1E40AF", "#FFFFFF"
        even_bg, odd_bg = "#F8FAFC", "#FFFFFF"
        cell_fg, border = "#1F2937", "#E5E7EB"
        col1_bg = "#F0F9FF"

        y = padding

        # Header row
        x = padding
        draw.rectangle([x, y, total_w - padding, y + header_height], fill=header_bg)
        for i, (wrapped, width) in enumerate(zip(wrapped_headers, col_widths)):
            ty = y + padding
            for ln in wrapped:
                bb = draw.textbbox((0, 0), ln, font=header_font)
                tx = x + (width - (bb[2] - bb[0])) // 2
                draw.text((tx, ty), ln, fill=header_fg, font=header_font)
                ty += line_h
            x += width
        y += header_height

        # Data rows
        for ri, (wr, rh) in enumerate(zip(wrapped_rows, row_heights)):
            x = padding
            bg = even_bg if ri % 2 == 0 else odd_bg
            draw.rectangle([x, y, total_w - padding, y + rh], fill=bg)
            for i, width in enumerate(col_widths):
                if i == 0 and num_cols == 2:
                    draw.rectangle([x, y, x + width, y + rh], fill=col1_bg)
                if i < len(wr):
                    ty = y + padding
                    for ln in wr[i]:
                        draw.text((x + padding, ty), ln, fill=cell_fg, font=font)
                        ty += line_h
                x += width
            y += rh

        # Borders
        draw.rectangle(
            [padding, padding, total_w - padding, total_h - padding],
            outline=border, width=2,
        )
        y = padding + header_height
        for rh in row_heights:
            draw.line([(padding, y), (total_w - padding, y)], fill=border, width=1)
            y += rh
        x = padding
        for width in col_widths[:-1]:
            x += width
            draw.line([(x, padding), (x, total_h - padding)], fill=border, width=1)

        buf = BytesIO()
        img.save(buf, format="PNG", optimize=True)
        buf.seek(0)
        return buf

    except Exception:
        logger.exception("table image generation failed")
        return None


# ===================================================================
# Signal text formatting helpers
# ===================================================================


def markdown_to_signal(text: str) -> str:
    """Convert markdown to Signal styled text format.

    Signal uses text_mode="styled" with:
      **bold**, *italic*, ~strikethrough~, ||spoiler||, `code`, ```block```
    Note: **double asterisks** for bold, *single* for italic.
    """
    if not text:
        return ""

    # Headers -> bold text
    text = re.sub(r"^#{1,6}\s*(.+)$", r"**\1**", text, flags=re.MULTILINE)

    # __bold__ -> **bold** (Signal uses double asterisk for bold)
    text = re.sub(r"__(.+?)__", r"**\1**", text)

    # _italic_ stays as *italic* (single asterisk)
    # **bold** stays as **bold** (already correct)

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

    lines = ["\n\n----------\n**Sources:**"]
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
            lines.append(f"[{i}] **{label}**\n    {pdf_url}")
        else:
            lines.append(f"[{i}] **{label}**")

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
# Styled send helper
# ===================================================================


async def send(context: Context, text: str, **kwargs) -> None:
    """Send a message with styled text formatting enabled."""
    await context.send(text, text_mode="styled", **kwargs)


# ===================================================================
# Command: handle all incoming messages
# ===================================================================

# Commands (case-insensitive)
_COMMANDS = frozenset({
    "help", "/help",
    "start", "/start",
    "hi", "hello", "hey",
    "examples", "/examples",
    "stats", "/stats",
    "clear", "/clear", "new", "new chat", "reset",
})


class LegalQueryCommand(Command):
    """Handle all incoming Signal messages.

    signalbot routes every message through registered commands.
    This is a catch-all that processes commands and legal questions.
    """

    async def handle(self, context: Context) -> None:
        """Process incoming message."""
        message = context.message
        raw_text = message.text or ""
        sender = message.source  # E.164 phone number

        if not raw_text.strip() or not sender:
            return

        # Deduplication (Signal can redeliver on reconnection)
        if hasattr(message, "timestamp") and message.timestamp:
            if dedup.is_duplicate(sender, message.timestamp):
                logger.debug("duplicate message skipped: %s", mask_phone(sender))
                return

        # Sanitize input
        text = sanitize_input(raw_text)
        if not text:
            return

        # Access control
        if settings.allowed_users and sender not in settings.allowed_users:
            await send(context, "Sorry, you're not authorized to use this bot.")
            return

        # Validate message
        is_valid, error_msg = validate_message(text, settings.max_message_length)
        if not is_valid:
            if error_msg:
                await send(context, error_msg)
            return

        # Handle commands
        text_lower = text.lower().strip()

        if text_lower in {"help", "/help"}:
            help_text = SUCCESS_MESSAGES["help"].format(
                daily_limit=settings.rate_limit_per_user_per_day,
            )
            await send(context, help_text)
            return

        if text_lower in {"start", "/start", "hi", "hello", "hey"}:
            conversations.clear(sender)
            await send(context, SUCCESS_MESSAGES["welcome"])
            return

        if text_lower in {"examples", "/examples"}:
            await self._send_examples(context)
            return

        if text_lower in {"stats", "/stats"}:
            stats = await rate_limiter.get_stats(sender)
            stats_text = (
                "**Your Usage Statistics**\n\n"
                f"Today's usage: {stats['daily_used']} / {stats['daily_limit']}\n"
                f"Remaining today: {stats['daily_remaining']}\n\n"
                f"Per-minute limit: {stats['minute_limit']} messages"
            )
            await send(context, stats_text)
            return

        if text_lower in {"clear", "/clear", "new", "new chat", "reset"}:
            conversations.clear(sender)
            await send(context,
                "Conversation cleared. Send me a new question to start fresh."
            )
            return

        # Rate limit check
        allowed, err_msg, _ = await rate_limiter.check(sender)
        if not allowed:
            await send(context, err_msg)
            return

        # Process as legal question
        await self._process_question(context, sender, text)

    async def _process_question(
        self, context: Context, sender: str, question: str
    ) -> None:
        """Send question to Vaquill API and deliver formatted response."""
        phone_masked = mask_phone(sender)

        # Send "Researching..." indicator (typing indicators are unreliable in Signal)
        try:
            await send(context, "*Researching your question. This may take up to a minute...*")
        except Exception:
            pass

        try:
            await context.start_typing()
        except Exception:
            pass

        try:
            history = conversations.get(sender)

            response = await vaquill.ask(
                question=question,
                chat_history=history if history else None,
                sources=True,
                max_sources=settings.max_sources_per_response,
            )

            answer = vaquill.extract_answer(response)
            sources = vaquill.extract_sources(response)

            if not answer:
                await send(context,
                    "I couldn't get a response. Please try again."
                )
                return

            # Record history
            conversations.append(sender, "user", question)
            conversations.append(sender, "assistant", answer)

            # Generate table images before stripping markdown
            table_images: List[BytesIO] = []
            if PILLOW_AVAILABLE:
                for _, hdrs, rws in extract_markdown_tables(answer):
                    img = generate_table_image(hdrs, rws)
                    if img:
                        table_images.append(img)

            # Format for Signal
            formatted = markdown_to_signal(answer)
            sources_text = build_sources_text(sources)
            footer = (
                "\n\n*For acts, citation graphs, translations and more:* "
                "https://app.vaquill.ai"
            )

            full = formatted + sources_text + footer
            chunks = chunk_message(full)

            # Send text chunks (styled formatting)
            for chunk in chunks:
                await send(context, chunk)

            # Send table images as attachments
            import base64

            for idx, timg in enumerate(table_images):
                try:
                    img_b64 = base64.b64encode(timg.read()).decode("utf-8")
                    caption = f"Table {idx + 1}" if len(table_images) > 1 else "Table"
                    await context.send(caption, base64_attachments=[img_b64])
                except Exception:
                    logger.debug("failed to send table image %d", idx + 1)

            # Send source PDFs as document attachments (download and forward)
            await self._send_source_pdfs(context, sources)

            logger.info(
                "message handled: user=%s sources=%d tables=%d chunks=%d",
                phone_masked,
                len(sources),
                len(table_images),
                len(chunks),
            )

        except VaquillAPIError as e:
            logger.error("Vaquill API error: %s", e)
            if e.status_code == 402:
                await send(context,
                    "The bot's API credits are exhausted. "
                    "Please contact the administrator."
                )
            elif e.status_code == 429:
                await send(context,
                    "The API is rate-limited right now. "
                    "Please wait a moment and try again."
                )
            else:
                await send(context,
                    "Something went wrong. Please try again later."
                )
        except Exception:
            logger.exception(
                "unexpected error handling message for user=%s", phone_masked,
            )
            await send(context,
                "An unexpected error occurred. Please try again later."
            )
        finally:
            try:
                await context.stop_typing()
            except Exception:
                pass

    async def _send_source_pdfs(
        self, context: Context, sources: List[Dict[str, Any]]
    ) -> None:
        """Download source PDFs and send as named Signal attachments.

        Uses the signal-cli-rest-api data URI format to set filenames:
        data:application/pdf;filename=Case_Name.pdf;base64,<data>
        """
        import base64
        import re

        import aiohttp

        pdf_count = 0
        for src in sources[:3]:  # Max 3 PDFs
            pdf_url = src.get("pdfUrl") or src.get("pdf_url") or ""
            if not pdf_url:
                continue

            case_name = src.get("caseName") or src.get("case_name") or "Judgment"
            citation = src.get("citation") or ""
            idx = src.get("sourceIndex") or src.get("source_index") or pdf_count + 1

            # Build a clean filename: "[1] Case Name (Citation).pdf"
            filename = f"[{idx}] {case_name[:50]}"
            if citation:
                filename += f" ({citation})"
            # Sanitize filename: remove chars unsafe for filesystems
            filename = re.sub(r'[<>:"/\\|?*]', "", filename).strip()
            filename += ".pdf"

            caption = f"[{idx}] {case_name}"
            if citation:
                caption += f" ({citation})"

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(pdf_url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                        if resp.status == 200:
                            pdf_bytes = await resp.read()
                            pdf_b64 = base64.b64encode(pdf_bytes).decode("utf-8")
                            # Use data URI format with filename for signal-cli
                            named_attachment = (
                                f"data:application/pdf;filename={filename};base64,{pdf_b64}"
                            )
                            await context.send(
                                caption[:200],
                                base64_attachments=[named_attachment],
                                text_mode="styled",
                            )
                            pdf_count += 1
            except Exception:
                logger.debug("failed to download/send PDF: %s", pdf_url[:60])

    async def _send_examples(self, context: Context) -> None:
        """Send example questions grouped by category."""
        lines = ["**Example Questions:**\n"]

        for category, questions in STARTER_QUESTIONS.items():
            cat_name = category.replace("_", " ").title()
            lines.append(f"\n**{cat_name}:**")
            for i, q in enumerate(questions, 1):
                lines.append(f"  {i}. {q}")

        lines.append("\nJust copy and send any question, or type your own.")
        await send(context, "\n".join(lines))


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
        signal_service=settings.signal_service_url.replace("http://", "").replace("https://", ""),
        phone_number=settings.signal_phone_number,
        connection_mode=ConnectionMode.HTTP_ONLY,  # Internal Docker network, no TLS
        retry_interval=5,  # Seconds between reconnection attempts
    )

    bot = SignalBot(config)

    # Register the catch-all command for private messages only (no groups)
    bot.register(LegalQueryCommand(), contacts=True, groups=False)

    logger.info(
        "Vaquill Signal bot starting (phone=%s, mode=%s, pillow=%s)",
        mask_phone(settings.signal_phone_number),
        settings.vaquill_mode,
        PILLOW_AVAILABLE,
    )
    bot.start()


if __name__ == "__main__":
    main()
