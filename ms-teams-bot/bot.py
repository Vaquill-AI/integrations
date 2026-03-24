"""
Microsoft Teams Bot Implementation for Vaquill Legal AI
"""

import logging
from typing import List, Optional, Dict, Any, Tuple

from botbuilder.core import (
    TurnContext,
    MessageFactory,
    CardFactory,
    ActivityHandler,
)
from botbuilder.schema import (
    Activity,
    ActivityTypes,
    ChannelAccount,
)
from botbuilder.core.conversation_state import ConversationState
from botbuilder.core.user_state import UserState

from config import Config
from vaquill_client import VaquillClient, VaquillAPIError, InsufficientCreditsError
from rate_limiter import RateLimiter
from conversation_manager import ConversationManager
from adaptive_cards import AdaptiveCardBuilder
from input_validator import InputValidator

logger = logging.getLogger(__name__)


class VaquillTeamsBot(ActivityHandler):
    """Microsoft Teams bot implementation for Vaquill Legal AI"""

    def __init__(
        self,
        conversation_state: ConversationState,
        user_state: UserState,
    ):
        super().__init__()

        self.conversation_state = conversation_state
        self.user_state = user_state
        self.vaquill_client = VaquillClient(
            api_key=Config.VAQUILL_API_KEY,
            api_url=Config.VAQUILL_API_URL,
            mode=Config.VAQUILL_MODE,
            country_code=Config.VAQUILL_COUNTRY_CODE,
        )
        self.rate_limiter = RateLimiter()
        self.conversation_manager = ConversationManager()
        self._initialized = False

        self.command_patterns = {
            "/help": self._handle_help_command,
            "/clear": self._handle_clear_command,
            "/status": self._handle_status_command,
        }

    async def initialize(self):
        """Async initialization -- call before processing requests."""
        if self._initialized:
            return

        try:
            await self.vaquill_client._ensure_session()
            logger.info("Vaquill client initialized")

            await self.rate_limiter.initialize()
            logger.info("Rate limiter initialized")

            await self.conversation_manager.initialize()
            logger.info("Conversation manager initialized")

            self._initialized = True
            logger.info("Bot initialization complete")
        except Exception as e:
            logger.error(f"Bot initialization failed: {e}")
            raise

    async def cleanup(self):
        """Clean up bot resources"""
        logger.info("Starting bot cleanup...")
        try:
            await self.vaquill_client.close()
            await self.rate_limiter.close()
            await self.conversation_manager.close()
            logger.info("Bot cleanup complete")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    async def on_message_activity(self, turn_context: TurnContext) -> None:
        """Handle incoming messages"""
        logger.info("on_message_activity called")
        try:
            activity = turn_context.activity
            text = activity.text.strip() if activity.text else ""

            # Handle adaptive card actions
            if activity.value:
                logger.info(f"Handling adaptive card action: {activity.value}")
                await self._handle_card_action(turn_context, activity.value)
                return

            if not text:
                return

            # Validate and sanitize input
            if not InputValidator.validate_message_length(text):
                await turn_context.send_activity(
                    f"Your message is too long. Maximum length is "
                    f"{InputValidator.MAX_MESSAGE_LENGTH} characters."
                )
                return

            if InputValidator.detect_potential_injection(text):
                logger.warning("Potential injection attempt detected")
                await turn_context.send_activity(
                    "Your message contains potentially unsafe content. "
                    "Please rephrase your question."
                )
                return

            text = InputValidator.sanitize_message(text)

            # Get conversation details
            user_id = activity.from_property.id
            user_name = activity.from_property.name

            channel_data = activity.channel_data or {}
            channel_id = (
                channel_data.get("channel", {}).get("id", activity.conversation.id)
                if isinstance(channel_data.get("channel"), dict)
                else activity.conversation.id
            )
            tenant_id = (
                channel_data.get("tenant", {}).get("id", "default")
                if isinstance(channel_data.get("tenant"), dict)
                else "default"
            )

            logger.info(f"User: {user_name} ({user_id}), Channel: {channel_id}")

            # Validate IDs
            if not InputValidator.validate_user_id(user_id):
                logger.error("Invalid user ID format")
                return

            if not InputValidator.validate_channel_id(channel_id):
                logger.error("Invalid channel ID format")
                return

            thread_id = (
                activity.conversation.conversation_type
                if activity.conversation.is_group
                else None
            )

            # Check if bot was mentioned in a channel
            is_channel = activity.conversation.is_group
            bot_mentioned = False

            if is_channel:
                text, bot_mentioned = self._remove_mentions(activity)

                if Config.REQUIRE_MENTION_IN_CHANNELS and not bot_mentioned:
                    return

            # Check if sender is a bot
            from_properties = (
                getattr(activity.from_property, "properties", None) or {}
            )
            if from_properties.get("isBot") and not Config.RESPOND_TO_OTHER_BOTS:
                return

            # Security checks
            if Config.is_user_blocked(user_id):
                logger.warning(f"User {user_id} is blocked")
                await turn_context.send_activity(
                    "Sorry, you don't have permission to use this bot."
                )
                return

            if not Config.is_tenant_allowed(tenant_id):
                logger.warning(f"Tenant {tenant_id} is not allowed")
                await turn_context.send_activity(
                    "Sorry, this bot is not available for your organization."
                )
                return

            if not Config.is_channel_allowed(channel_id):
                logger.warning(f"Channel {channel_id} is not allowed")
                await turn_context.send_activity(
                    "Sorry, this bot is not enabled for this channel."
                )
                return

            # Check for commands
            command = text.lower().split()[0] if text else ""
            if command in self.command_patterns:
                await self.command_patterns[command](turn_context)
                return

            # Rate limiting
            is_allowed, error_message = await self.rate_limiter.check_rate_limit(
                user_id, channel_id, tenant_id
            )

            if not is_allowed:
                quota_info = await self.rate_limiter.get_remaining_quota(
                    user_id, tenant_id
                )
                card = AdaptiveCardBuilder.create_rate_limit_card(
                    reset_time=60,
                    user_remaining=quota_info.get("user_remaining"),
                )
                await turn_context.send_activity(MessageFactory.attachment(card))
                return

            # Send typing indicator
            await self._send_typing_indicator(turn_context)

            # Get or create conversation context
            conversation = (
                await self.conversation_manager.get_or_create_conversation(
                    channel_id=channel_id,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    thread_id=thread_id,
                    metadata={
                        "user_name": user_name,
                        "is_channel": is_channel,
                        "teams_conversation_id": activity.conversation.id,
                    },
                )
            )

            # Send question to Vaquill
            try:
                # Build chat history for context
                chat_history: Optional[List[Dict[str, str]]] = None
                if Config.ENABLE_THREADING and Config.ENABLE_CONVERSATION_HISTORY:
                    chat_history = await self.conversation_manager.get_chat_history(
                        channel_id,
                        user_id,
                        thread_id,
                        limit=Config.MAX_CONTEXT_MESSAGES,
                    )
                    if not chat_history:
                        chat_history = None

                response_data = await self.vaquill_client.ask(
                    question=text,
                    sources=Config.SHOW_SOURCES,
                    max_sources=Config.MAX_SOURCES,
                    chat_history=chat_history,
                )

                response_text = self.vaquill_client.extract_answer(response_data)
                sources = (
                    self.vaquill_client.extract_sources(response_data)
                    if Config.SHOW_SOURCES
                    else []
                )

                # Store messages in conversation history
                await self.conversation_manager.add_message(
                    channel_id, user_id, "user", text, thread_id
                )
                await self.conversation_manager.add_message(
                    channel_id, user_id, "assistant", response_text, thread_id
                )

                # Send response
                if Config.ENABLE_ADAPTIVE_CARDS:
                    card = AdaptiveCardBuilder.create_response_card(
                        response=response_text,
                        sources=sources if sources else None,
                        show_feedback=True,
                    )
                    await turn_context.send_activity(
                        MessageFactory.attachment(card)
                    )
                else:
                    formatted = response_text
                    if sources:
                        formatted += "\n\n**Sources:**\n"
                        formatted += self.vaquill_client.format_sources_text(
                            response_data, max_sources=Config.MAX_SOURCES
                        )
                    await turn_context.send_activity(
                        MessageFactory.text(formatted)
                    )

            except InsufficientCreditsError:
                error_card = AdaptiveCardBuilder.create_error_card(
                    error_message=(
                        "The Vaquill API key has insufficient credits. "
                        "Please contact your administrator."
                    ),
                    retry_available=False,
                )
                await turn_context.send_activity(
                    MessageFactory.attachment(error_card)
                )

            except VaquillAPIError as e:
                logger.error(f"Vaquill API error: {e}")
                error_card = AdaptiveCardBuilder.create_error_card(
                    error_message="I encountered an error while processing your request.",
                    details=str(e) if Config.LOG_LEVEL == "DEBUG" else None,
                    retry_available=True,
                )
                await turn_context.send_activity(
                    MessageFactory.attachment(error_card)
                )

            except Exception as e:
                logger.error(f"Error processing message: {e}")
                error_card = AdaptiveCardBuilder.create_error_card(
                    error_message="I encountered an error while processing your request.",
                    details=str(e) if Config.LOG_LEVEL == "DEBUG" else None,
                    retry_available=True,
                )
                await turn_context.send_activity(
                    MessageFactory.attachment(error_card)
                )

        except Exception as e:
            logger.error(f"Unexpected error in message handler: {e}", exc_info=True)
            await turn_context.send_activity(
                "An unexpected error occurred. Please try again later."
            )

    async def on_members_added_activity(
        self,
        members_added: List[ChannelAccount],
        turn_context: TurnContext,
    ) -> None:
        """Handle new members joining"""
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                await self._send_welcome_message(turn_context)

    async def _send_welcome_message(self, turn_context: TurnContext) -> None:
        """Send welcome message to new users"""
        try:
            welcome_card = AdaptiveCardBuilder.create_welcome_card(
                bot_name="Vaquill"
            )
            await turn_context.send_activity(MessageFactory.attachment(welcome_card))
        except Exception as e:
            logger.error(f"Error sending welcome message: {e}")
            await turn_context.send_activity(
                "Welcome! I'm the Vaquill Legal AI Bot. "
                "Ask me anything about law or type /help for more information."
            )

    async def _handle_card_action(
        self, turn_context: TurnContext, value: Dict[str, Any]
    ) -> None:
        """Handle adaptive card actions"""
        action = value.get("action")

        if action == "ask_question":
            question = value.get("question")
            if question:
                turn_context.activity.text = question
                await self.on_message_activity(turn_context)

        elif action == "feedback":
            reaction = value.get("reaction")
            if reaction:
                confirmation_card = (
                    AdaptiveCardBuilder.create_feedback_confirmation_card(reaction)
                )
                await turn_context.send_activity(
                    MessageFactory.attachment(confirmation_card)
                )

        elif action == "copy":
            await turn_context.send_activity(
                "Please select and copy the text above."
            )

        elif action == "retry":
            await turn_context.send_activity("Please try your question again.")

    async def _handle_help_command(self, turn_context: TurnContext) -> None:
        """Handle /help command"""
        help_card = AdaptiveCardBuilder.create_help_card()
        await turn_context.send_activity(MessageFactory.attachment(help_card))

    async def _handle_clear_command(self, turn_context: TurnContext) -> None:
        """Handle /clear command"""
        activity = turn_context.activity
        user_id = activity.from_property.id

        channel_data = activity.channel_data or {}
        channel_id = (
            channel_data.get("channel", {}).get("id", activity.conversation.id)
            if isinstance(channel_data.get("channel"), dict)
            else activity.conversation.id
        )
        thread_id = (
            activity.conversation.conversation_type
            if activity.conversation.is_group
            else None
        )

        await self.conversation_manager.clear_conversation(
            channel_id, user_id, thread_id
        )

        await turn_context.send_activity(
            "Conversation history cleared. Starting fresh!"
        )

    async def _handle_status_command(self, turn_context: TurnContext) -> None:
        """Handle /status command"""
        activity = turn_context.activity
        user_id = activity.from_property.id

        channel_data = activity.channel_data or {}
        tenant_id = (
            channel_data.get("tenant", {}).get("id", "default")
            if isinstance(channel_data.get("tenant"), dict)
            else "default"
        )

        quota_info = await self.rate_limiter.get_remaining_quota(user_id, tenant_id)
        conversation_count = (
            await self.conversation_manager.get_active_conversations_count(tenant_id)
        )

        status_text = f"""**Bot Status**

**Rate Limits:**
- User messages remaining: {quota_info['user_remaining']}/{quota_info['user_limit']} (per minute)

**Active Conversations:** {conversation_count}

**Configuration:**
- Mode: {Config.VAQUILL_MODE}
- Threading: {'Enabled' if Config.ENABLE_THREADING else 'Disabled'}
- Sources: {'Shown' if Config.SHOW_SOURCES else 'Hidden'}
"""

        await turn_context.send_activity(MessageFactory.text(status_text))

    async def _send_typing_indicator(self, turn_context: TurnContext) -> None:
        """Send typing indicator"""
        typing_activity = MessageFactory.text("")
        typing_activity.type = ActivityTypes.typing
        await turn_context.send_activity(typing_activity)

    def _remove_mentions(self, activity: Activity) -> Tuple[str, bool]:
        """Remove bot mentions from text and check if bot was mentioned"""
        text = activity.text or ""
        bot_mentioned = False

        if activity.entities:
            for entity in activity.entities:
                if entity.type == "mention":
                    mentioned_id = None
                    mention_text = None

                    if hasattr(entity, "additional_properties"):
                        mentioned = entity.additional_properties.get("mentioned", {})
                        mentioned_id = mentioned.get("id")
                        mention_text = entity.additional_properties.get("text", "")
                    elif hasattr(entity, "mentioned"):
                        mentioned = entity.mentioned
                        mentioned_id = getattr(mentioned, "id", None)
                        mention_text = getattr(entity, "text", "")

                    if mentioned_id == activity.recipient.id:
                        bot_mentioned = True

                    if mention_text:
                        text = text.replace(mention_text, "").strip()

        return text, bot_mentioned
