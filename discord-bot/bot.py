"""
Vaquill Legal AI Discord Bot.

Uses the Vaquill API to answer legal questions with source citations.
Maintains per-channel chat history for multi-turn conversations.
"""

import asyncio
import logging
import re
from collections import defaultdict
from typing import Dict, List

import discord
from discord.ext import commands

from config import (
    ALLOWED_CHANNELS,
    ALLOWED_ROLES,
    DISCORD_BOT_TOKEN,
    DISCORD_COMMAND_PREFIX,
    ENABLE_SOURCES,
    ENABLE_STARTER_QUESTIONS,
    ERROR_MESSAGES,
    MAX_CHAT_HISTORY,
    MAX_MESSAGE_LENGTH,
    RATE_LIMIT_PER_CHANNEL,
    RATE_LIMIT_PER_USER,
    RATE_LIMIT_WINDOW,
    REDIS_URL,
    STARTER_QUESTIONS,
    TYPING_INDICATOR,
    VAQUILL_API_KEY,
    VAQUILL_API_URL,
    VAQUILL_COUNTRY_CODE,
    VAQUILL_MODE,
)
from rate_limiter import DiscordRateLimiter, RateLimiter
from vaquill_client import VaquillClient
from views import HelpView, PaginationView, SourcesView, StarterQuestionsView

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class VaquillBot(commands.Cog):
    """Cog that bridges Discord commands to the Vaquill Legal AI API."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.vaquill_client: VaquillClient | None = None
        self.rate_limiter: RateLimiter | None = None
        self.discord_rate_limiter: DiscordRateLimiter | None = None
        self.starter_questions = STARTER_QUESTIONS

        # Per-channel chat history: channel_id -> list of {role, content} dicts
        self._chat_history: Dict[str, List[Dict[str, str]]] = defaultdict(list)

    # -- lifecycle --------------------------------------------------------

    async def cog_load(self):
        """Initialize clients when cog loads."""
        self.vaquill_client = VaquillClient(
            api_key=VAQUILL_API_KEY,
            api_url=VAQUILL_API_URL,
            mode=VAQUILL_MODE,
            country_code=VAQUILL_COUNTRY_CODE or None,
        )

        self.rate_limiter = RateLimiter(REDIS_URL)
        await self.rate_limiter.connect()

        self.discord_rate_limiter = DiscordRateLimiter(
            self.rate_limiter,
            {
                "RATE_LIMIT_PER_USER": RATE_LIMIT_PER_USER,
                "RATE_LIMIT_PER_CHANNEL": RATE_LIMIT_PER_CHANNEL,
                "RATE_LIMIT_WINDOW": RATE_LIMIT_WINDOW,
            },
        )

        logger.info("Vaquill Bot cog loaded successfully")

    async def cog_unload(self):
        """Cleanup on cog unload."""
        if self.rate_limiter:
            await self.rate_limiter.disconnect()
        if self.vaquill_client:
            await self.vaquill_client.close()

    # -- helpers ----------------------------------------------------------

    def _check_permissions(self, ctx: commands.Context) -> bool:
        """Check if user has permission to use the bot."""
        if ALLOWED_CHANNELS and str(ctx.channel.id) not in ALLOWED_CHANNELS:
            return False

        if ALLOWED_ROLES:
            user_roles = [str(role.id) for role in ctx.author.roles]
            if not any(role in ALLOWED_ROLES for role in user_roles):
                return False

        return True

    @staticmethod
    def _split_message(content: str, max_length: int = 2000) -> List[str]:
        """Split long messages at sentence boundaries."""
        if len(content) <= max_length:
            return [content]

        sentences = re.split(r"(?<=[.!?])\s+", content)
        chunks: List[str] = []
        current_chunk = ""

        for sentence in sentences:
            if len(current_chunk) + len(sentence) + 1 <= max_length:
                current_chunk += sentence + " "
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                # Handle single sentences longer than max_length
                if len(sentence) > max_length:
                    while sentence:
                        chunks.append(sentence[:max_length])
                        sentence = sentence[max_length:]
                else:
                    current_chunk = sentence + " "

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks

    def _get_chat_history(self, channel_id: str) -> List[Dict[str, str]]:
        """Return the chat history for a channel, trimmed to MAX_CHAT_HISTORY pairs."""
        history = self._chat_history[channel_id]
        # Keep the most recent messages (each pair = user + assistant)
        max_messages = MAX_CHAT_HISTORY * 2
        if len(history) > max_messages:
            history = history[-max_messages:]
            self._chat_history[channel_id] = history
        return history

    def _append_to_history(
        self, channel_id: str, question: str, answer: str
    ) -> None:
        """Append a Q/A pair to channel chat history."""
        self._chat_history[channel_id].append({"role": "user", "content": question})
        self._chat_history[channel_id].append(
            {"role": "assistant", "content": answer}
        )

    # -- message processing -----------------------------------------------

    async def process_message(
        self,
        channel: discord.TextChannel,
        author: discord.User,
        question: str,
    ):
        """Process a question and send the response."""
        try:
            if TYPING_INDICATOR:
                async with channel.typing():
                    await self._send_response(channel, author, question)
            else:
                await self._send_response(channel, author, question)
        except Exception as e:
            logger.error("Error processing message: %s", e)
            await channel.send(ERROR_MESSAGES["api_error"])

    async def _send_response(
        self,
        channel: discord.TextChannel,
        author: discord.User,
        question: str,
    ):
        """Call Vaquill API and send the formatted response."""
        channel_id = str(channel.id)
        chat_history = self._get_chat_history(channel_id)

        async with self.vaquill_client:
            response = await self.vaquill_client.ask(
                question,
                chat_history=chat_history or None,
            )

        answer = self.vaquill_client.extract_answer(response)
        sources = self.vaquill_client.extract_sources(response)

        # Store in chat history
        self._append_to_history(channel_id, question, answer)

        # Split if needed
        chunks = self._split_message(answer)

        if len(chunks) == 1:
            if sources and ENABLE_SOURCES:
                view = SourcesView(sources, chunks[0])
                await channel.send(chunks[0], view=view)
            else:
                await channel.send(chunks[0])
        else:
            # Paginated response
            embed = discord.Embed(
                description=chunks[0],
                color=discord.Color.blue(),
            )
            embed.set_footer(text=f"Page 1/{len(chunks)}")
            view = PaginationView(chunks, author)
            await channel.send(embed=embed, view=view)

    # -- commands ---------------------------------------------------------

    @commands.command(name="ask", aliases=["a", "q"])
    async def ask(self, ctx: commands.Context, *, question: str = None):
        """Ask a legal question to Vaquill."""
        if not self._check_permissions(ctx):
            await ctx.send(ERROR_MESSAGES["unauthorized"])
            return

        if not question:
            await ctx.send(ERROR_MESSAGES["invalid_input"])
            return

        if len(question) > MAX_MESSAGE_LENGTH:
            await ctx.send(
                f"Your message is too long. Please keep it under {MAX_MESSAGE_LENGTH} characters."
            )
            return

        # Rate limits
        user_allowed, _, user_reset = await self.discord_rate_limiter.check_user_limit(
            str(ctx.author.id)
        )
        channel_allowed, _, channel_reset = (
            await self.discord_rate_limiter.check_channel_limit(str(ctx.channel.id))
        )

        if not user_allowed:
            await ctx.send(
                f"{ERROR_MESSAGES['rate_limit']}\nReset in {user_reset} seconds."
            )
            return

        if not channel_allowed:
            await ctx.send(
                f"This channel has reached its query limit.\n"
                f"Reset in {channel_reset} seconds."
            )
            return

        await self.process_message(ctx.channel, ctx.author, question)

    @commands.command(name="starters", aliases=["start", "questions"])
    async def starters(self, ctx: commands.Context):
        """Show starter questions."""
        if not self._check_permissions(ctx):
            await ctx.send(ERROR_MESSAGES["unauthorized"])
            return

        if ENABLE_STARTER_QUESTIONS and self.starter_questions:
            embed = discord.Embed(
                title="Starter Questions",
                description="Click a button below to ask that question:",
                color=discord.Color.blue(),
            )
            view = StarterQuestionsView(self.starter_questions, self)
            await ctx.send(embed=embed, view=view)
        else:
            await ctx.send("Starter questions are not available.")

    @commands.command(name="reset")
    async def reset(self, ctx: commands.Context):
        """Reset conversation history for this channel."""
        if not self._check_permissions(ctx):
            await ctx.send(ERROR_MESSAGES["unauthorized"])
            return

        channel_id = str(ctx.channel.id)
        if channel_id in self._chat_history and self._chat_history[channel_id]:
            del self._chat_history[channel_id]
            await ctx.send("Conversation has been reset for this channel.")
        else:
            await ctx.send("No active conversation to reset.")

    @commands.command(name="help")
    async def help_command(self, ctx: commands.Context):
        """Show help information."""
        embed = discord.Embed(
            title="Vaquill Legal AI Bot",
            description=(
                "I answer legal questions using Vaquill's legal AI engine. "
                "Ask me about cases, statutes, or legal concepts."
            ),
            color=discord.Color.blue(),
        )
        view = HelpView(prefix=DISCORD_COMMAND_PREFIX)
        await ctx.send(embed=embed, view=view)


# -- Bot setup -----------------------------------------------------------

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=DISCORD_COMMAND_PREFIX, intents=intents)
bot.remove_command("help")  # Replace default help


@bot.event
async def on_ready():
    logger.info("%s has connected to Discord!", bot.user)
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.listening,
            name=f"{DISCORD_COMMAND_PREFIX}help",
        )
    )


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.CommandNotFound):
        return
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"Missing required argument: {error.param.name}")
    else:
        logger.error("Command error: %s", error)
        await ctx.send(ERROR_MESSAGES["api_error"])


async def main():
    async with bot:
        await bot.add_cog(VaquillBot(bot))
        await bot.start(DISCORD_BOT_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
