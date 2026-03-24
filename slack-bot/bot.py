#!/usr/bin/env python3
"""
Vaquill Slack Bot

A Slack bot that integrates with the Vaquill Legal AI API.

Features:
- Responds to @mentions and direct messages
- Maintains chat history per thread (client-side {role, content} arrays)
- Displays structured legal sources from Vaquill
- Feedback buttons (thumbs up / down)
- /vaquill and /vaquill-help slash commands
"""

import os
import re
import json
import time
import logging
import asyncio
from datetime import datetime, timezone
from typing import Dict, Optional, List, Any

from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_sdk.web.async_client import AsyncWebClient

from config import Config
from vaquill_client import VaquillClient
from rate_limiter import RateLimiter
from conversation_manager import ConversationManager
from security_manager import SecurityManager
from starter_questions import StarterQuestionsManager
from analytics import Analytics

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Components
# ---------------------------------------------------------------------------
app = AsyncApp(
    token=Config.SLACK_BOT_TOKEN,
    signing_secret=Config.SLACK_SIGNING_SECRET,
)

vaquill_client = VaquillClient(
    api_key=Config.VAQUILL_API_KEY,
    api_url=Config.VAQUILL_API_URL,
    mode=Config.VAQUILL_MODE,
    country_code=Config.VAQUILL_COUNTRY_CODE,
)
rate_limiter = RateLimiter()
conversation_manager = ConversationManager()
security_manager = SecurityManager()
starter_questions_manager = StarterQuestionsManager()
analytics = Analytics()

bot_user_id: Optional[str] = None

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def convert_markdown_to_slack(text: str) -> str:
    """Convert standard Markdown to Slack mrkdwn."""
    if not text:
        return text
    # Headers -> bold
    text = re.sub(r"^#{1,6}\s+(.+)$", r"*\1*", text, flags=re.MULTILINE)
    # **bold** -> *bold*
    text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)
    # [text](url) -> <url|text>
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"<\2|\1>", text)
    # Bullet points
    text = re.sub(r"^[\-\*]\s+", "\u2022 ", text, flags=re.MULTILINE)
    return text


def _format_sources_block(sources: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Build a Slack context block listing legal sources."""
    if not sources or not Config.SHOW_SOURCES:
        return None

    lines = ["*Sources:*"]
    for i, src in enumerate(sources[:5], 1):
        case_name = src.get("caseName") or src.get("case_name") or "Source"
        citation = src.get("citation") or ""
        court = src.get("court") or ""
        parts = [case_name]
        if citation:
            parts.append(citation)
        if court:
            parts.append(court)
        lines.append(f"  {i}. {' | '.join(parts)}")

    return {
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": "\n".join(lines)}],
    }


def build_response_blocks(
    answer_text: str,
    sources: List[Dict[str, Any]],
    response_id: str = "",
) -> List[Dict[str, Any]]:
    """Assemble Slack Block Kit blocks for a Vaquill response."""
    blocks: List[Dict[str, Any]] = [
        {"type": "section", "text": {"type": "mrkdwn", "text": answer_text}},
    ]

    sources_block = _format_sources_block(sources)
    if sources_block:
        blocks.append(sources_block)

    # Feedback buttons
    blocks.append(
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Helpful"},
                    "action_id": "feedback_positive",
                    "value": response_id,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Not Helpful"},
                    "action_id": "feedback_negative",
                    "value": response_id,
                },
            ],
        }
    )
    return blocks


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


@app.middleware
async def log_request(logger, body, next):
    """Log incoming Slack events for debugging."""
    request_type = body.get("type", "unknown")
    if request_type == "block_actions":
        actions = body.get("actions", [])
        action_ids = [a.get("action_id") for a in actions]
        logger.info("block_actions received: %s", action_ids)
    await next()


# ---------------------------------------------------------------------------
# Event handlers
# ---------------------------------------------------------------------------


@app.event("app_mention")
async def handle_app_mention(event: Dict[str, Any], client: AsyncWebClient, say):
    """Handle @Vaquill mentions in channels."""
    try:
        user_id = event["user"]
        channel_id = event["channel"]
        text = event["text"]
        thread_ts = event.get("thread_ts") or event["ts"]

        # Security
        if not await security_manager.is_user_allowed(user_id):
            await say(
                "Sorry, you don't have permission to use this bot.",
                thread_ts=thread_ts,
            )
            return

        # Rate limiting
        if not await rate_limiter.check_rate_limit(user_id, channel_id):
            await say(
                "You've reached the rate limit. Please wait a moment before trying again.",
                thread_ts=thread_ts,
            )
            return

        # Strip the @mention to get the actual query
        query = re.sub(r"<@[A-Z0-9]+>", "", text).strip()

        if not query:
            blocks = await starter_questions_manager.get_formatted_blocks()
            await say(blocks=blocks, thread_ts=thread_ts)
            return

        # Input validation
        if not security_manager.validate_input(query):
            query = security_manager.sanitize_input(query)

        await analytics.track_query(user_id, channel_id, query)

        # Typing indicator
        await client.chat_postMessage(
            channel=channel_id, text="Thinking...", thread_ts=thread_ts
        )

        # Retrieve chat history for this thread
        chat_history = conversation_manager.get_or_create_history(
            user_id, channel_id, thread_ts
        )

        try:
            start = time.time()
            response = await vaquill_client.ask(
                question=query,
                chat_history=chat_history if chat_history else None,
            )
            elapsed = time.time() - start

            answer = vaquill_client.extract_answer(response)
            sources = vaquill_client.extract_sources(response)
            meta = response.get("meta", {})

            # Persist exchange in local history
            conversation_manager.append_exchange(
                user_id, channel_id, thread_ts, query, answer
            )

            # Format for Slack
            slack_text = convert_markdown_to_slack(answer)
            blocks = build_response_blocks(
                slack_text,
                sources,
                response_id=f"{channel_id}:{thread_ts}",
            )

            await say(text=slack_text, blocks=blocks, thread_ts=thread_ts)

            # Mark thread so follow-ups work
            if thread_ts:
                conversation_manager.mark_thread_participation(channel_id, thread_ts)

            await analytics.track_response(
                user_id,
                channel_id,
                success=True,
                response_time=elapsed,
                credits_consumed=meta.get("creditsConsumed"),
            )

        except Exception as exc:
            logger.error("Vaquill API error: %s", exc)
            await say(
                security_manager.get_safe_error_message(exc),
                thread_ts=thread_ts,
            )
            await analytics.track_response(user_id, channel_id, success=False)

    except Exception as exc:
        logger.error("Error handling app mention: %s", exc)
        await say("An unexpected error occurred. Please try again later.")


@app.event("message")
async def handle_direct_message(event: Dict[str, Any], client: AsyncWebClient, say):
    """Handle DMs and thread follow-ups."""
    subtype = event.get("subtype")
    if subtype in (
        "message_changed",
        "message_deleted",
        "channel_join",
        "channel_leave",
        "bot_add",
        "bot_remove",
    ):
        return

    if not event.get("text", "").strip():
        return

    # Skip bot messages
    if Config.IGNORE_BOT_MESSAGES:
        if event.get("bot_id") or subtype == "bot_message" or event.get("user") == bot_user_id:
            return
        uid = event.get("user")
        if uid:
            try:
                info = await client.users_info(user=uid)
                if info.get("user", {}).get("is_bot"):
                    return
            except Exception:
                pass

    # Direct messages
    if event.get("channel_type") == "im":
        await handle_app_mention(event, client, say)
        return

    # Thread follow-ups
    if Config.THREAD_FOLLOW_UP_ENABLED:
        channel_id = event.get("channel")
        thread_ts = event.get("thread_ts")
        if thread_ts and thread_ts != event.get("ts"):
            if event.get("subtype") == "thread_broadcast":
                return
            should_respond, reason = conversation_manager.should_respond_to_thread(
                channel_id, thread_ts
            )
            if should_respond:
                logger.info("Responding to thread follow-up: %s", reason)
                conversation_manager.update_thread_activity(channel_id, thread_ts)
                await handle_app_mention(event, client, say)


# ---------------------------------------------------------------------------
# Slash commands
# ---------------------------------------------------------------------------


@app.command("/vaquill")
async def handle_vaquill_command(ack, command, say):
    """Handle /vaquill <question> slash command."""
    await ack()

    user_id = command["user_id"]
    channel_id = command["channel_id"]
    query = command["text"]

    if not query:
        await say("Please provide a question. Usage: `/vaquill [your question]`")
        return

    fake_event = {
        "user": user_id,
        "channel": channel_id,
        "text": query,
        "ts": str(datetime.now(timezone.utc).timestamp()),
    }
    await handle_app_mention(fake_event, app.client, say)


@app.command("/vaquill-help")
async def handle_help_command(ack, command, say):
    """Handle /vaquill-help slash command."""
    await ack()

    help_text = """
*Vaquill Legal AI Bot*

*Basic Usage:*
\u2022 Mention me in a channel: `@Vaquill your question`
\u2022 Direct message me with your question
\u2022 Use slash command: `/vaquill your question`

*Commands:*
\u2022 `/vaquill [question]` - Ask a legal question
\u2022 `/vaquill-help` - Show this help message

*Features:*
\u2022 Thread support -- I maintain context within threads
\u2022 Legal sources -- See cited cases and statutes
\u2022 Feedback -- Use the buttons to rate responses
\u2022 Starter questions -- Mention me without a question

*Tips:*
\u2022 Be specific with your questions for better answers
\u2022 Use threads for follow-up questions
\u2022 Indian law is our primary coverage area

Need more help? Contact your administrator.
    """
    await say(help_text)


# ---------------------------------------------------------------------------
# Action handlers
# ---------------------------------------------------------------------------


@app.action("feedback_positive")
async def handle_positive_feedback(ack, body, client):
    await ack()
    user_id = body["user"]["id"]
    message_id = body["actions"][0]["value"]
    await analytics.track_feedback(user_id, message_id, "positive")

    await client.chat_update(
        channel=body["channel"]["id"],
        ts=body["message"]["ts"],
        text=body["message"]["text"],
        blocks=body["message"]["blocks"][:-1]
        + [
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": "Thanks for your feedback!"}
                ],
            }
        ],
    )


@app.action("feedback_negative")
async def handle_negative_feedback(ack, body, client):
    await ack()
    user_id = body["user"]["id"]
    message_id = body["actions"][0]["value"]
    await analytics.track_feedback(user_id, message_id, "negative")

    await client.chat_update(
        channel=body["channel"]["id"],
        ts=body["message"]["ts"],
        text=body["message"]["text"],
        blocks=body["message"]["blocks"][:-1]
        + [
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "Thanks for your feedback. We'll work on improving!",
                    }
                ],
            }
        ],
    )


@app.action(re.compile("ask_question_.*"))
async def handle_ask_question(ack, body, say):
    """Handle starter-question button clicks."""
    await ack()

    question = body["actions"][0]["value"]
    user_id = body["user"]["id"]
    channel_id = body["channel"]["id"]
    thread_ts = body["message"].get("thread_ts") or body["message"]["ts"]

    fake_event = {
        "user": user_id,
        "channel": channel_id,
        "text": question,
        "ts": str(datetime.now(timezone.utc).timestamp()),
        "thread_ts": thread_ts,
    }
    await handle_app_mention(fake_event, app.client, say)


# ---------------------------------------------------------------------------
# Error handler
# ---------------------------------------------------------------------------


@app.error
async def global_error_handler(error, body, logger):
    logger.error("Unhandled error: %s", error)
    logger.debug("Request body: %s", body)


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


async def initialize_bot() -> None:
    """Fetch bot user ID and start periodic cleanup."""
    global bot_user_id
    try:
        auth = await app.client.auth_test()
        bot_user_id = auth["user_id"]
        logger.info("Bot initialised with user ID: %s", bot_user_id)

        async def _periodic_cleanup():
            while True:
                await asyncio.sleep(3600)
                conversation_manager.cleanup_expired_conversations()
                conversation_manager.cleanup_expired_thread_participation()
                logger.info("Completed periodic cleanup")

        asyncio.create_task(_periodic_cleanup())
    except Exception as exc:
        logger.error("Failed to initialise bot: %s", exc)
        raise


async def main() -> None:
    """Entry point -- Socket Mode (dev) or HTTP (prod)."""
    await initialize_bot()

    if Config.SLACK_APP_TOKEN:
        handler = AsyncSocketModeHandler(app, Config.SLACK_APP_TOKEN)
        await handler.start_async()
    else:
        from aiohttp import web

        port = int(os.environ.get("PORT", 3000))
        runner = web.AppRunner(app.server(port=port).web_app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        logger.info("Bot is running on port %d", port)
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
