"""
Discord UI views for the Vaquill bot.

Includes starter-question buttons, pagination, source citations, and help.
"""

import discord
from typing import List


class StarterQuestionsView(discord.ui.View):
    """View displaying starter questions as interactive buttons."""

    def __init__(self, questions: List[str], bot_instance):
        super().__init__(timeout=300)  # 5-minute timeout
        self.bot = bot_instance

        # Discord limits to 5 buttons per action row
        for i, question in enumerate(questions[:5]):
            button = QuestionButton(question, i)
            self.add_item(button)


class QuestionButton(discord.ui.Button):
    """A single starter-question button."""

    def __init__(self, question: str, index: int):
        label = question[:80] if len(question) > 80 else question
        super().__init__(
            style=discord.ButtonStyle.primary,
            label=label,
            custom_id=f"vaquill_question_{index}",
        )
        self.question = question

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()

        cog = interaction.client.get_cog("VaquillBot")
        if cog:
            await cog.process_message(
                interaction.channel, interaction.user, self.question
            )


class PaginationView(discord.ui.View):
    """Paginate long responses across Discord embeds."""

    def __init__(self, pages: List[str], original_author: discord.User):
        super().__init__(timeout=300)
        self.pages = pages
        self.current_page = 0
        self.original_author = original_author
        self.update_buttons()

    def update_buttons(self):
        self.children[0].disabled = self.current_page == 0
        self.children[1].disabled = self.current_page == len(self.pages) - 1

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.secondary)
    async def previous_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user != self.original_author:
            await interaction.response.send_message(
                "Only the original requester can navigate pages.", ephemeral=True
            )
            return

        self.current_page = max(0, self.current_page - 1)
        self.update_buttons()

        embed = discord.Embed(
            description=self.pages[self.current_page],
            color=discord.Color.blue(),
        )
        embed.set_footer(text=f"Page {self.current_page + 1}/{len(self.pages)}")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary)
    async def next_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user != self.original_author:
            await interaction.response.send_message(
                "Only the original requester can navigate pages.", ephemeral=True
            )
            return

        self.current_page = min(len(self.pages) - 1, self.current_page + 1)
        self.update_buttons()

        embed = discord.Embed(
            description=self.pages[self.current_page],
            color=discord.Color.blue(),
        )
        embed.set_footer(text=f"Page {self.current_page + 1}/{len(self.pages)}")
        await interaction.response.edit_message(embed=embed, view=self)


class SourcesView(discord.ui.View):
    """Toggle-able view for showing Vaquill legal sources."""

    def __init__(self, sources: List[dict], message_content: str):
        super().__init__(timeout=120)
        self.sources = sources
        self.message_content = message_content
        self.showing_sources = False

    @discord.ui.button(label="Show Sources", style=discord.ButtonStyle.secondary)
    async def toggle_sources(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.showing_sources = not self.showing_sources

        if self.showing_sources:
            button.label = "Hide Sources"
            embed = discord.Embed(title="Sources", color=discord.Color.green())

            for i, src in enumerate(self.sources[:5]):
                case_name = (
                    src.get("caseName")
                    or src.get("case_name")
                    or f"Source {i + 1}"
                )
                citation = src.get("citation", "")
                court = src.get("court", "")

                parts = [case_name]
                if citation:
                    parts.append(citation)
                if court:
                    parts.append(court)

                field_value = " | ".join(parts)
                embed.add_field(
                    name=f"[{i + 1}] {case_name[:256]}",
                    value=field_value[:1024],
                    inline=False,
                )

            await interaction.response.edit_message(
                content=self.message_content, embed=embed, view=self
            )
        else:
            button.label = "Show Sources"
            await interaction.response.edit_message(
                content=self.message_content, embed=None, view=self
            )


class HelpView(discord.ui.View):
    """Interactive help menu for the Vaquill bot."""

    def __init__(self, prefix: str = "!"):
        super().__init__(timeout=180)
        self.prefix = prefix

    @discord.ui.button(label="Bot Commands", style=discord.ButtonStyle.primary)
    async def commands_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        embed = discord.Embed(
            title="Bot Commands",
            description="Available commands:",
            color=discord.Color.blue(),
        )
        embed.add_field(
            name=f"{self.prefix}ask [question]",
            value="Ask a legal question to Vaquill",
            inline=False,
        )
        embed.add_field(
            name=f"{self.prefix}help",
            value="Show this help message",
            inline=False,
        )
        embed.add_field(
            name=f"{self.prefix}starters",
            value="Show starter questions",
            inline=False,
        )
        embed.add_field(
            name=f"{self.prefix}reset",
            value="Reset conversation history for this channel",
            inline=False,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="How to Use", style=discord.ButtonStyle.secondary)
    async def usage_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        embed = discord.Embed(
            title="How to Use",
            description="Getting started with the Vaquill legal AI bot:",
            color=discord.Color.green(),
        )
        embed.add_field(
            name="1. Ask a question",
            value=f"Use `{self.prefix}ask` followed by your legal question",
            inline=False,
        )
        embed.add_field(
            name="2. Continue the conversation",
            value="The bot remembers context within each channel",
            inline=False,
        )
        embed.add_field(
            name="3. Try starter questions",
            value=f"Type `{self.prefix}starters` for suggested topics",
            inline=False,
        )
        embed.add_field(
            name="4. View sources",
            value="Click 'Show Sources' to see cited cases and statutes",
            inline=False,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Settings Info", style=discord.ButtonStyle.secondary)
    async def settings_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        embed = discord.Embed(
            title="Bot Settings",
            description="Current configuration:",
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name="Rate Limits",
            value="10 queries per minute per user\n30 queries per minute per channel",
            inline=False,
        )
        embed.add_field(
            name="Features",
            value=(
                "Conversation memory per channel\n"
                "Legal source citations\n"
                "Starter questions\n"
                "Rate limiting"
            ),
            inline=False,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
