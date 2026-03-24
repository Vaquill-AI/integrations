#!/usr/bin/env python3
"""
Vaquill Legal AI — Telegram Bot.

Answers legal questions via the Vaquill API, renders markdown tables as
images (Pillow), shows case-law sources with inline keyboard buttons, and
maintains per-chat conversation history.
"""

import html
import logging
import os
import re
from collections import defaultdict
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.constants import ChatAction, ParseMode
from telegram.error import BadRequest
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import STARTER_QUESTIONS, SUCCESS_MESSAGES, get_settings
from rate_limiter import RateLimiter
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

# Per-chat conversation history: chat_id -> list of {role, content}
chat_histories: Dict[int, List[Dict[str, str]]] = defaultdict(list)

# Telegram hard limit
TELEGRAM_MAX_MESSAGE_LENGTH = 4096

# ===================================================================
# Table extraction & image rendering
# ===================================================================


def extract_markdown_tables(
    text: str,
) -> List[Tuple[str, List[str], List[List[str]]]]:
    """
    Extract markdown tables from *text*.

    Returns a list of ``(original_table_text, headers, rows)`` tuples.
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


def _wrap_text(text: str, font, max_width: int, draw) -> List[str]:
    """Word-wrap *text* to fit within *max_width* pixels."""
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


def _clean_cell(text: str) -> str:
    """Strip markdown formatting from a table cell."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"_(.+?)_", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return text.strip()


def generate_table_image(
    headers: List[str],
    rows: List[List[str]],
    max_width: int = 1200,
    padding: int = 12,
    font_size: int = 14,
    header_font_size: int = 15,
) -> Optional[BytesIO]:
    """Render a markdown table as a PNG image. Returns ``None`` when Pillow is missing."""
    if not PILLOW_AVAILABLE or not headers or not rows:
        return None

    try:
        # --- fonts ---
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/Library/Fonts/Arial.ttf",
            "C:\\Windows\\Fonts\\arial.ttf",
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

        # --- measurement pass ---
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

        # --- draw ---
        img = Image.new("RGB", (total_w, total_h), color="#FFFFFF")
        draw = ImageDraw.Draw(img)

        header_bg = "#1E40AF"
        header_fg = "#FFFFFF"
        even_bg = "#F8FAFC"
        odd_bg = "#FFFFFF"
        cell_fg = "#1F2937"
        border = "#E5E7EB"
        col1_bg = "#F0F9FF"

        y = padding

        # header row
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

        # data rows
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

        # borders
        draw.rectangle(
            [padding, padding, total_w - padding, total_h - padding],
            outline=border,
            width=2,
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
# Telegram text formatting helpers
# ===================================================================


def escape_html(text: str) -> str:
    """Escape HTML special chars for Telegram."""
    return html.escape(text, quote=False)


def convert_markdown_table_to_cards(text: str) -> str:
    """Convert markdown tables into a mobile-friendly card layout."""
    lines = text.split("\n")
    result: List[str] = []
    table_rows: List[List[str]] = []
    in_table = False
    headers: List[str] = []

    for line in lines:
        is_tbl = "|" in line and (
            line.strip().startswith("|") or line.strip().count("|") >= 2
        )
        if is_tbl:
            if re.match(r"^\s*\|[-:\s|]+\|\s*$", line):
                continue
            cells = [c.strip() for c in line.split("|") if c.strip()]
            if not in_table:
                in_table = True
                headers = cells
            else:
                table_rows.append(cells)
        else:
            if in_table and table_rows:
                result.append(_format_cards(headers, table_rows))
                table_rows, headers = [], []
                in_table = False
            result.append(line)

    if in_table and table_rows:
        result.append(_format_cards(headers, table_rows))

    return "\n".join(result)


def _format_cards(headers: List[str], rows: List[List[str]]) -> str:
    """Format table data as vertical cards."""
    if not headers or not rows:
        return ""
    cards: List[str] = []
    if len(headers) == 2:
        for row in rows:
            if len(row) >= 2:
                title = re.sub(r"\*\*(.+?)\*\*", r"\1", row[0])
                title = re.sub(r"__(.+?)__", r"\1", title)
                cards.append(f"<b>{title}</b>\n{row[1]}")
    else:
        for row in rows:
            parts: List[str] = []
            for i, cell in enumerate(row):
                if i < len(headers):
                    hdr = re.sub(r"\*\*(.+?)\*\*", r"\1", headers[i])
                    parts.append(f"<b>{hdr}:</b> {cell}")
                else:
                    parts.append(cell)
            cards.append("\n".join(parts))
    return "\n\n".join(cards)


def sanitize_for_telegram(text: str) -> str:
    """
    Convert arbitrary markdown/HTML to Telegram-safe HTML.

    Strategy: strip all HTML, escape everything, then selectively apply
    Telegram-supported tags.
    """
    if not text:
        return ""

    # --- preserve code blocks ---
    code_blocks: List[Tuple[str, str]] = []

    def _save_code(m):
        idx = len(code_blocks)
        code_blocks.append((m.group(1) or "", m.group(2)))
        return f"__CODE_BLOCK_{idx}__"

    text = re.sub(r"```(\w*)\n?([\s\S]*?)```", _save_code, text)

    inline_codes: List[str] = []

    def _save_inline(m):
        idx = len(inline_codes)
        inline_codes.append(m.group(1))
        return f"__INLINE_CODE_{idx}__"

    text = re.sub(r"`([^`]+)`", _save_inline, text)

    # --- strip HTML ---
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(
        r"</?(?:p|div|section|article|header|footer|main|aside|nav)[^>]*>",
        "\n",
        text,
        flags=re.I,
    )
    text = re.sub(
        r"<h[1-6][^>]*>(.*?)</h[1-6]>", r"\n\1\n", text, flags=re.I | re.S
    )
    text = re.sub(r"<hr\s*/?>", "\n----------\n", text, flags=re.I)
    text = re.sub(r"</?(?:ul|ol)[^>]*>", "\n", text, flags=re.I)
    text = re.sub(
        r"<li[^>]*>(.*?)</li>", r"- \1\n", text, flags=re.I | re.S
    )
    text = re.sub(r"</?(?:table|thead|tbody|tr)[^>]*>", "\n", text, flags=re.I)
    text = re.sub(
        r"<(?:th|td)[^>]*>(.*?)</(?:th|td)>", r"\1 | ", text, flags=re.I | re.S
    )
    text = re.sub(r"<[^>]+>", "", text)

    # --- escape ---
    text = html.escape(text, quote=False)

    # --- markdown tables -> cards ---
    if "|" in text and re.search(r"\|.*\|.*\|", text):
        text = convert_markdown_table_to_cards(text)

    # --- markdown -> Telegram HTML ---
    text = re.sub(r"^#{1,6}\s*(.+)$", r"<b>\1</b>", text, flags=re.M)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"__(.+?)__", r"<b>\1</b>", text)
    text = re.sub(r"(?<![/\w])\*([^*\n]+)\*(?![/\w])", r"<i>\1</i>", text)
    text = re.sub(r"(?<![/\w])_([^_\n]+)_(?![/\w])", r"<i>\1</i>", text)
    text = re.sub(r"~~(.+?)~~", r"<s>\1</s>", text)

    def _md_link(m):
        return f'<a href="{m.group(2)}">{m.group(1)}</a>'

    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", _md_link, text)
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"[Image: \1]", text)
    text = re.sub(r"^&gt;\s*(.+)$", r"\u25b8 \1", text, flags=re.M)
    text = re.sub(r"^[\-\*]\s+(.+)$", r"- \1", text, flags=re.M)
    text = re.sub(r"^[\-\*_]{3,}$", "----------", text, flags=re.M)

    # --- restore code ---
    for i, (lang, code) in enumerate(code_blocks):
        escaped = html.escape(code)
        if lang:
            repl = f'<pre><code class="language-{lang}">{escaped}</code></pre>'
        else:
            repl = f"<pre>{escaped}</pre>"
        text = text.replace(f"__CODE_BLOCK_{i}__", repl)

    for i, code in enumerate(inline_codes):
        text = text.replace(f"__INLINE_CODE_{i}__", f"<code>{html.escape(code)}</code>")

    # --- clean whitespace ---
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r"\n +", "\n", text)
    return text.strip()


def strip_all_formatting(text: str) -> str:
    """Return plain text with all HTML/markdown removed."""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"_(.+?)_", r"\1", text)
    text = re.sub(r"~~(.+?)~~", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return text


def chunk_message(
    text: str, max_length: int = TELEGRAM_MAX_MESSAGE_LENGTH
) -> List[str]:
    """Split long text into Telegram-safe chunks at natural boundaries."""
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
# Source formatting helpers
# ===================================================================


def build_sources_text(sources: List[Dict[str, Any]]) -> str:
    """Format Vaquill sources as Telegram HTML."""
    if not sources:
        return ""

    lines = ["\n\n<b>Sources:</b>"]
    for i, src in enumerate(sources[:settings.max_sources_per_response], 1):
        case_name = (
            src.get("caseName")
            or src.get("case_name")
            or "Source"
        )
        citation = src.get("citation") or ""
        court = src.get("court") or ""
        pdf_url = src.get("pdfUrl") or src.get("pdf_url") or ""

        label_parts = [html.escape(case_name)]
        if citation:
            label_parts.append(html.escape(citation))
        if court:
            label_parts.append(html.escape(court))
        label = " | ".join(label_parts)

        if pdf_url:
            safe_url = pdf_url.replace('"', "%22").replace("'", "%27")
            lines.append(f'{i}. <a href="{safe_url}">{label}</a>')
        else:
            lines.append(f"{i}. {label}")

    return "\n".join(lines)


def build_sources_keyboard(sources: List[Dict[str, Any]]) -> Optional[InlineKeyboardMarkup]:
    """Build an inline keyboard with source links (if any have URLs)."""
    buttons: List[List[InlineKeyboardButton]] = []
    for i, src in enumerate(sources[:settings.max_sources_per_response], 1):
        pdf_url = src.get("pdfUrl") or src.get("pdf_url") or ""
        if not pdf_url:
            continue
        case_name = (
            src.get("caseName")
            or src.get("case_name")
            or f"Source {i}"
        )
        # Telegram inline button text max 64 chars
        label = f"{i}. {case_name}"[:60]
        buttons.append([InlineKeyboardButton(label, url=pdf_url)])

    return InlineKeyboardMarkup(buttons) if buttons else None


# ===================================================================
# Chat history helpers
# ===================================================================

MAX_HISTORY = settings.max_conversation_history


def _append_history(chat_id: int, role: str, content: str) -> None:
    """Append a message to the chat history, trimming to MAX_HISTORY pairs."""
    chat_histories[chat_id].append({"role": role, "content": content})
    # Keep last MAX_HISTORY * 2 entries (pairs of user + assistant)
    limit = MAX_HISTORY * 2
    if len(chat_histories[chat_id]) > limit:
        chat_histories[chat_id] = chat_histories[chat_id][-limit:]


def _get_history(chat_id: int) -> List[Dict[str, str]]:
    """Return the chat history for the Vaquill API."""
    return list(chat_histories[chat_id])


def _clear_history(chat_id: int) -> None:
    """Wipe the chat history for a chat."""
    chat_histories.pop(chat_id, None)


# ===================================================================
# Command handlers
# ===================================================================


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start — welcome message + example buttons."""
    chat_id = update.effective_chat.id
    _clear_history(chat_id)

    keyboard = [
        [InlineKeyboardButton("Indian Law", callback_data="examples_indian_law")],
        [InlineKeyboardButton("US Law", callback_data="examples_us_law")],
        [InlineKeyboardButton("General", callback_data="examples_general")],
    ]

    await update.message.reply_text(
        SUCCESS_MESSAGES["welcome"],
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML,
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help."""
    text = SUCCESS_MESSAGES["help"].format(
        daily_limit=settings.rate_limit_per_user_per_day,
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def cmd_examples(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /examples — show category buttons."""
    keyboard = [
        [InlineKeyboardButton("Indian Law", callback_data="examples_indian_law")],
        [InlineKeyboardButton("US Law", callback_data="examples_us_law")],
        [InlineKeyboardButton("General", callback_data="examples_general")],
    ]
    await update.message.reply_text(
        "Choose a category to see example questions:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /stats — show rate-limit usage."""
    user_id = update.effective_user.id
    stats = await rate_limiter.get_stats(user_id)

    text = (
        "<b>Your Usage Statistics</b>\n\n"
        f"Today's usage: {stats['daily_used']} / {stats['daily_limit']}\n"
        f"Remaining today: {stats['daily_remaining']}\n\n"
        f"Per-minute limit: {stats['minute_limit']} messages"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /clear — wipe conversation history."""
    _clear_history(update.effective_chat.id)
    await update.message.reply_text(
        "Conversation cleared! Send me a new question to start fresh."
    )


# ===================================================================
# Shared question processing
# ===================================================================


async def _process_question(
    chat_id: int,
    user_id: int,
    question: str,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """
    Send *question* to the Vaquill API, format the response, and deliver it
    to *chat_id*.  Shared by both ``handle_message`` and the ``ask_*``
    inline-keyboard callback so the logic lives in one place.
    """
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    try:
        history = _get_history(chat_id)

        response = await vaquill.ask(
            question=question,
            chat_history=history if history else None,
            sources=True,
            max_sources=settings.max_sources_per_response,
        )

        answer = vaquill.extract_answer(response)
        sources = vaquill.extract_sources(response)

        if not answer:
            await context.bot.send_message(
                chat_id=chat_id,
                text="I couldn't get a response. Please try again.",
            )
            return

        # Record history
        _append_history(chat_id, "user", question)
        _append_history(chat_id, "assistant", answer)

        # --- table images ---
        table_images: List[BytesIO] = []
        if PILLOW_AVAILABLE:
            for _, hdrs, rws in extract_markdown_tables(answer):
                img = generate_table_image(hdrs, rws)
                if img:
                    table_images.append(img)

        # --- format text ---
        formatted = sanitize_for_telegram(answer)
        sources_text = build_sources_text(sources)
        sources_kb = build_sources_keyboard(sources)

        if table_images:
            # text first, then images, then sources
            chunks = chunk_message(formatted)
        else:
            full = formatted + sources_text
            chunks = chunk_message(full)

        # --- send text chunks ---
        for i, chunk in enumerate(chunks):
            # Attach source buttons only to the last chunk (when no table images)
            kb = sources_kb if (i == len(chunks) - 1 and not table_images) else None
            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=chunk,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                    reply_markup=kb,
                )
            except BadRequest as e:
                if "parse" in str(e).lower() or "entities" in str(e).lower():
                    logger.warning("HTML parse failed, falling back to plain text")
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=strip_all_formatting(chunk),
                        disable_web_page_preview=True,
                        reply_markup=kb,
                    )
                else:
                    raise

        # --- send table images ---
        for idx, timg in enumerate(table_images):
            try:
                caption = f"Table {idx + 1}" if len(table_images) > 1 else "Table"
                await context.bot.send_photo(
                    chat_id=chat_id, photo=timg, caption=caption
                )
            except Exception:
                logger.exception("failed to send table image %d", idx + 1)

        # --- send sources after images ---
        if table_images and sources_text:
            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=sources_text.strip(),
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                    reply_markup=sources_kb,
                )
            except BadRequest:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=strip_all_formatting(sources_text).strip(),
                    disable_web_page_preview=True,
                )

        logger.info(
            "message handled: user=%s sources=%d tables=%d chunks=%d",
            user_id,
            len(sources),
            len(table_images),
            len(chunks),
        )

    except VaquillAPIError as e:
        logger.error("Vaquill API error: %s", e)
        if e.status_code == 402:
            await context.bot.send_message(
                chat_id=chat_id,
                text="The bot's API credits are exhausted. Please contact the administrator.",
            )
        elif e.status_code == 429:
            await context.bot.send_message(
                chat_id=chat_id,
                text="The API is rate-limited right now. Please wait a moment and try again.",
            )
        else:
            await context.bot.send_message(
                chat_id=chat_id,
                text="Something went wrong. Please try again later.",
            )
    except Exception:
        logger.exception("unexpected error handling message for user=%s", user_id)
        await context.bot.send_message(
            chat_id=chat_id,
            text="An unexpected error occurred. Please try again later.",
        )


# ===================================================================
# Message handler
# ===================================================================


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route a plain-text message through the Vaquill API."""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    user_text = (update.message.text or "").strip()

    if not user_text:
        return

    # --- access control ---
    if settings.allowed_users and user_id not in settings.allowed_users:
        await update.message.reply_text("Sorry, you're not authorized to use this bot.")
        return

    # --- message length ---
    if len(user_text) > settings.max_message_length:
        await update.message.reply_text(
            f"Your message is too long. Please keep it under {settings.max_message_length} characters."
        )
        return

    # --- rate limit ---
    allowed, err_msg, _ = await rate_limiter.check(user_id)
    if not allowed:
        await context.bot.send_message(chat_id=chat_id, text=err_msg)
        return

    await _process_question(chat_id, user_id, user_text, context)


# ===================================================================
# Callback query handler (inline keyboard buttons)
# ===================================================================


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline-keyboard button presses."""
    query = update.callback_query
    await query.answer()

    if query.data.startswith("examples_"):
        category = query.data.removeprefix("examples_")
        questions = STARTER_QUESTIONS.get(category, [])

        if questions:
            text = f"<b>{category.replace('_', ' ').title()} Questions:</b>\n\n"
            for i, q in enumerate(questions, 1):
                text += f"{i}. {q}\n"
            text += "\nTap a question or type your own!"

            keyboard = [
                [InlineKeyboardButton(q, callback_data=f"ask_{q}")]
                for q in questions
            ]
            await query.edit_message_text(
                text=text,
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(keyboard),
            )

    elif query.data.startswith("ask_"):
        question = query.data.removeprefix("ask_")
        await query.message.delete()

        chat_id = query.message.chat.id
        user_id = query.from_user.id

        await context.bot.send_message(
            chat_id=chat_id,
            text=f"<i>You asked: {html.escape(question)}</i>",
            parse_mode=ParseMode.HTML,
        )

        allowed, err_msg, _ = await rate_limiter.check(user_id)
        if not allowed:
            await context.bot.send_message(chat_id=chat_id, text=err_msg)
            return

        await _process_question(chat_id, user_id, question, context)


# ===================================================================
# Error handler
# ===================================================================


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log unhandled exceptions from the dispatcher."""
    logger.error("Unhandled exception: %s", context.error, exc_info=context.error)


# ===================================================================
# Bot setup
# ===================================================================


async def post_init(application: Application) -> None:
    """Register slash-command hints with Telegram."""
    commands = [
        BotCommand("start", "Start a new conversation"),
        BotCommand("help", "Show help information"),
        BotCommand("examples", "Show example questions"),
        BotCommand("stats", "View your usage statistics"),
        BotCommand("clear", "Clear conversation history"),
    ]
    await application.bot.set_my_commands(commands)


def main() -> None:
    """Entry point — build the Application and start polling."""
    if not settings.telegram_bot_token:
        logger.error("TELEGRAM_BOT_TOKEN is not set")
        return
    if not settings.vaquill_api_key:
        logger.error("VAQUILL_API_KEY is not set")
        return

    application = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .post_init(post_init)
        .build()
    )

    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("help", cmd_help))
    application.add_handler(CommandHandler("examples", cmd_examples))
    application.add_handler(CommandHandler("stats", cmd_stats))
    application.add_handler(CommandHandler("clear", cmd_clear))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_error_handler(error_handler)

    logger.info("Vaquill Telegram bot starting (mode=%s)", settings.vaquill_mode)
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
