"""
Flask application for Microsoft Teams Vaquill Bot
"""

import asyncio
import logging
import sys
import signal
import atexit
from flask import Flask, request, Response
from botbuilder.core import (
    TurnContext,
    BotFrameworkAdapter,
    BotFrameworkAdapterSettings,
    MemoryStorage,
    ConversationState,
    UserState,
)
from botbuilder.schema import Activity
from bot import VaquillTeamsBot
from config import Config

# Configure logging
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format=Config.LOG_FORMAT,
)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)

# Validate configuration
try:
    Config.validate()
except ValueError as e:
    logger.error(f"Configuration error: {e}")
    sys.exit(1)

# Create adapter settings
settings = BotFrameworkAdapterSettings(
    app_id=Config.TEAMS_APP_ID,
    app_password=Config.TEAMS_APP_PASSWORD,
    channel_auth_tenant=Config.TEAMS_TENANT_ID,
)

# Create adapter
adapter = BotFrameworkAdapter(settings)

# Create state storage
storage = MemoryStorage()
conversation_state = ConversationState(storage)
user_state = UserState(storage)

# Create bot instance
bot = VaquillTeamsBot(conversation_state, user_state)

# Bot initialization flag
bot_initialized = False


async def ensure_bot_initialized():
    """Ensure bot is initialized before processing requests"""
    global bot_initialized
    if not bot_initialized:
        try:
            await bot.initialize()
            bot_initialized = True
            logger.info("Bot initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize bot: {e}")
            raise


async def shutdown():
    """Graceful shutdown handler"""
    global bot_initialized
    if bot_initialized:
        logger.info("Shutting down bot...")
        try:
            await bot.cleanup()
            bot_initialized = False
            logger.info("Bot shutdown complete")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")


def signal_handler(sig, frame):
    """Handle shutdown signals"""
    logger.info(f"Received signal {sig}")
    asyncio.run(shutdown())
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
atexit.register(lambda: asyncio.run(shutdown()))


# Error handler
async def on_error(context: TurnContext, error: Exception):
    """Handle errors"""
    logger.error(f"Error in bot: {error}", exc_info=True)

    try:
        await context.send_activity(
            "Sorry, an error occurred while processing your request. "
            "Please try again later."
        )
    except Exception as e:
        logger.error(f"Error sending error message: {e}")


adapter.on_turn_error = on_error


@app.route("/api/messages", methods=["POST"])
def messages():
    """Handle incoming messages from Teams"""
    logger.info("Received POST request to /api/messages")

    if "application/json" not in request.headers.get("Content-Type", ""):
        return Response(status=415)

    try:
        body = request.json
        activity = Activity().deserialize(body)
        auth_header = request.headers.get("Authorization", "")

        async def aux_func(turn_context):
            await ensure_bot_initialized()
            await bot.on_message_activity(turn_context)
            await conversation_state.save_changes(turn_context)
            await user_state.save_changes(turn_context)

        # Get or create event loop for this thread
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        loop.run_until_complete(
            adapter.process_activity(activity, auth_header, aux_func)
        )
        return Response(status=201)

    except Exception as e:
        logger.error(f"Error processing activity: {e}", exc_info=True)
        return Response(status=500)


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    status = {
        "status": "healthy" if bot_initialized else "initializing",
        "bot": "Vaquill Teams Bot",
        "version": "1.0.0",
    }
    return status, 200 if bot_initialized else 503


@app.route("/", methods=["GET"])
def home():
    """Home page"""
    return """
    <html>
        <head>
            <title>Vaquill Teams Bot</title>
            <style>
                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI',
                                 Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                    max-width: 800px;
                    margin: 50px auto;
                    padding: 20px;
                    line-height: 1.6;
                }
                h1 { color: #5B5FC7; }
                .status {
                    padding: 10px;
                    background: #e8f5e9;
                    border-left: 4px solid #4caf50;
                    margin: 20px 0;
                }
            </style>
        </head>
        <body>
            <h1>Vaquill Teams Bot</h1>
            <div class="status">
                <strong>Status:</strong> Bot is running!
            </div>
            <p>To interact with the bot, please add it to your Microsoft Teams.</p>
            <h2>Features</h2>
            <ul>
                <li>AI-powered legal research via Vaquill</li>
                <li>Natural conversation with context</li>
                <li>Threading support</li>
                <li>Rich Adaptive Cards UI</li>
                <li>Source citations from Indian case law</li>
                <li>Rate limiting and security controls</li>
            </ul>
            <h2>Commands</h2>
            <ul>
                <li><code>/help</code> - Show available commands</li>
                <li><code>/clear</code> - Clear conversation history</li>
                <li><code>/status</code> - Check bot status and limits</li>
            </ul>
        </body>
    </html>
    """


if __name__ == "__main__":
    logger.info(f"Starting Vaquill Teams Bot on {Config.HOST}:{Config.PORT}")
    logger.info(f"Log level: {Config.LOG_LEVEL}")

    asyncio.run(ensure_bot_initialized())

    app.run(host=Config.HOST, port=Config.PORT, debug=False)
