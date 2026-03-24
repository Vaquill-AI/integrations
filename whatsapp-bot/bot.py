#!/usr/bin/env python3
"""
Vaquill Legal AI — WhatsApp Bot (Twilio).

Receives WhatsApp messages via Twilio webhook, forwards them to the
Vaquill /ask API, and returns the answer + sources. Chat history is
maintained client-side per phone number and sent with each request.
"""

import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

import structlog
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from twilio.rest import Client as TwilioClient
from twilio.twiml.messaging_response import MessagingResponse

from analytics import Analytics
from command_handler import CommandHandler
from config import Config
from rate_limiter import RateLimiter
from security_manager import SecurityManager
from session_manager import SessionManager
from starter_questions import StarterQuestions
from vaquill_client import VaquillClient, InsufficientCreditsError

load_dotenv()

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Configuration & shared state
# ---------------------------------------------------------------------------

config = Config()

twilio_client = TwilioClient(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN)

vaquill = VaquillClient(
    api_key=config.VAQUILL_API_KEY,
    api_url=config.VAQUILL_API_URL,
    mode=config.VAQUILL_MODE,
    country_code=config.VAQUILL_COUNTRY_CODE,
)

rate_limiter = RateLimiter(
    redis_url=config.REDIS_URL,
    daily_limit=config.RATE_LIMIT_DAILY,
    minute_limit=config.RATE_LIMIT_MINUTE,
)

session_manager = SessionManager(
    redis_url=config.REDIS_URL,
    session_timeout_minutes=config.SESSION_TIMEOUT_MINUTES,
    max_context_messages=config.SESSION_CONTEXT_MESSAGES,
)

security_manager = SecurityManager(config)

command_handler = CommandHandler(session_manager, rate_limiter, config)

starter_questions = StarterQuestions()

analytics = Analytics(redis_url=config.REDIS_URL)


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("starting_whatsapp_bot")
    await rate_limiter.initialize()
    await session_manager.initialize()
    await analytics.initialize()
    logger.info("whatsapp_bot_started")
    yield
    logger.info("shutting_down_whatsapp_bot")
    await vaquill.close()
    await rate_limiter.close()
    await session_manager.close()
    await analytics.close()


app = FastAPI(title="Vaquill WhatsApp Bot", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/")
async def root():
    return {
        "name": "Vaquill WhatsApp Bot",
        "status": "active",
        "version": "1.0.0",
    }


@app.post("/")
async def root_post_redirect(request: Request):
    """Redirect root POST to the webhook (some Twilio configs hit /)."""
    return await whatsapp_webhook(request)


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "vaquill": "configured",
            "redis": await rate_limiter.check_connection(),
            "twilio": "configured",
        },
    }


@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request):
    """Handle incoming WhatsApp messages from Twilio."""
    try:
        form_data = await request.form()

        from_number = form_data.get("From", "").replace("whatsapp:", "")
        message_body = form_data.get("Body", "")
        message_sid = form_data.get("MessageSid", "")
        media_url = form_data.get("MediaUrl0")
        num_media = int(form_data.get("NumMedia", 0))

        logger.info(
            "whatsapp_message_received",
            from_number=from_number,
            message_preview=message_body[:50],
            has_media=num_media > 0,
        )

        # Fire-and-forget processing
        asyncio.create_task(
            process_message(from_number, message_body, message_sid, media_url)
        )

        # Immediate empty TwiML so Twilio doesn't retry
        response = MessagingResponse()
        return Response(content=str(response), media_type="application/xml")

    except Exception as e:
        logger.error("webhook_error", error=str(e))
        return Response(status_code=500)


# ---------------------------------------------------------------------------
# Message processing
# ---------------------------------------------------------------------------


async def process_message(
    from_number: str,
    message_body: str,
    message_sid: str,
    media_url: Optional[str] = None,
):
    """Process a single incoming WhatsApp message end-to-end."""
    try:
        # --- security checks ---
        if not security_manager.is_allowed_number(from_number):
            await send_whatsapp_message(
                from_number,
                "Sorry, you are not authorized to use this bot.",
            )
            return

        if security_manager.is_blocked_number(from_number):
            logger.warning("blocked_number_attempt", number=from_number)
            return

        is_valid, error_msg = security_manager.validate_message(message_body)
        if not is_valid:
            await send_whatsapp_message(from_number, error_msg)
            return

        # --- rate limiting ---
        allowed, error, stats = await rate_limiter.check_rate_limit(from_number)
        if not allowed:
            await send_whatsapp_message(
                from_number,
                f"{error}\n\nYour usage today: {stats.get('daily_used', '?')}/{stats.get('daily_limit', '?')}",
            )
            return

        await analytics.log_message(from_number, message_body)

        # --- commands ---
        if message_body.startswith("/"):
            response_text = await command_handler.handle_command(
                from_number, message_body
            )
            await send_whatsapp_message(from_number, response_text)
            return

        # --- media ---
        if media_url and config.ENABLE_MEDIA_RESPONSES:
            await send_whatsapp_message(
                from_number,
                "Media received. Processing media files coming soon!",
            )
            return

        # --- thinking indicator ---
        if config.ENABLE_THINKING_MESSAGE:
            await send_whatsapp_message(from_number, "Thinking...")

        # --- ensure session exists ---
        session = await session_manager.get_session(from_number)
        if not session:
            await session_manager.create_session(from_number)
            session = await session_manager.get_session(from_number)

        # --- determine mode ---
        mode = (session or {}).get("mode") or config.VAQUILL_MODE

        # --- build chat history ---
        chat_history = await session_manager.get_chat_history(from_number)

        # --- call Vaquill API ---
        start_time = datetime.utcnow()

        try:
            response = await vaquill.ask(
                question=message_body,
                mode=mode,
                chat_history=chat_history if chat_history else None,
            )

            answer = vaquill.extract_answer(response)
            sources_text = vaquill.format_sources_text(response, max_sources=3)

            if not answer:
                await send_whatsapp_message(
                    from_number,
                    "Sorry, I couldn't get a proper response. Please try again.",
                )
                await analytics.log_response(from_number, False)
                return

            # Build final message
            reply = answer
            if sources_text:
                reply += f"\n\n*Sources:*\n{sources_text}"

            # Append credits info if available
            meta = response.get("meta", {})
            remaining = meta.get("creditsRemaining")
            if remaining is not None and remaining < 50:
                reply += f"\n\n_Credits remaining: {remaining}_"

            await send_whatsapp_message(from_number, reply)

            # Update chat history
            await session_manager.add_message(from_number, "user", message_body)
            await session_manager.add_message(from_number, "assistant", answer)

            response_time = (datetime.utcnow() - start_time).total_seconds()
            await analytics.log_response(from_number, True, response_time)

            # Occasionally suggest follow-up questions (skip greetings)
            greeting_words = [
                "hey", "hi", "hello", "good morning",
                "good afternoon", "good evening",
            ]
            is_greeting = any(w in message_body.lower() for w in greeting_words)

            if (
                not is_greeting
                and hash(from_number + message_body) % 10 < 3  # ~30%
            ):
                suggestions = await starter_questions.get_suggestions(
                    message_body, answer
                )
                if suggestions:
                    suggestion_text = "\n*You might also ask:*\n"
                    for i, q in enumerate(suggestions[:3], 1):
                        suggestion_text += f"{i}. {q}\n"
                    await send_whatsapp_message(from_number, suggestion_text)

        except InsufficientCreditsError:
            await send_whatsapp_message(
                from_number,
                "The bot has run out of API credits. Please contact support.",
            )
            await analytics.log_error(from_number, "insufficient_credits")

        except Exception as e:
            logger.error("vaquill_api_error", error=str(e))
            await send_whatsapp_message(
                from_number,
                "An error occurred while processing your message. Please try again.",
            )
            await analytics.log_error(from_number, str(e))

    except Exception as e:
        logger.error(
            "message_processing_error", error=str(e), from_number=from_number
        )


# ---------------------------------------------------------------------------
# Twilio send helper
# ---------------------------------------------------------------------------


async def send_whatsapp_message(
    to_number: str, message: str, media_url: Optional[str] = None
) -> Optional[str]:
    """Send a WhatsApp message via the Twilio API."""
    try:
        if not to_number.startswith("whatsapp:"):
            to_number = f"whatsapp:{to_number}"

        params = {
            "body": message,
            "from_": config.TWILIO_WHATSAPP_NUMBER,
            "to": to_number,
        }
        if media_url:
            params["media_url"] = [media_url]

        # Twilio client is synchronous; run in a thread to avoid blocking
        msg = await asyncio.to_thread(twilio_client.messages.create, **params)

        logger.info(
            "whatsapp_message_sent",
            to=to_number,
            message_sid=msg.sid,
            status=msg.status,
        )
        return msg.sid

    except Exception as e:
        logger.error("send_message_error", error=str(e), to_number=to_number)
        return None


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------


@app.get("/stats/{phone_number}")
async def get_user_stats(phone_number: str, api_key: Optional[str] = None):
    if api_key != config.ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    stats = await analytics.get_user_stats(phone_number)
    return JSONResponse(content=stats)


@app.post("/broadcast")
async def broadcast_message(request: Request):
    data = await request.json()
    if data.get("api_key") != config.ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

    message = data.get("message", "")
    recipients = data.get("recipients", [])

    results = []
    for recipient in recipients:
        try:
            sid = await send_whatsapp_message(recipient, message)
            results.append({"recipient": recipient, "status": "sent", "sid": sid})
        except Exception as e:
            results.append({"recipient": recipient, "status": "failed", "error": str(e)})

    return JSONResponse(content={"results": results})


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(
        "bot:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=bool(os.getenv("DEBUG", "")),
    )
