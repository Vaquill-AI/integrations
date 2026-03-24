"""
Starter Questions for Vaquill Slack Bot.

Provides pre-configured legal-domain questions shown when users
mention the bot without a query.
"""

import logging
import random
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


# Legal-domain starter questions for Vaquill
DEFAULT_QUESTIONS: List[str] = [
    "What are the grounds for divorce under Hindu Marriage Act?",
    "Explain Section 498A of IPC and its implications",
    "What is the procedure for filing a bail application?",
    "Summarise the landmark case Kesavananda Bharati v. State of Kerala",
    "What are the tenant rights under the Rent Control Act?",
]


class StarterQuestionsManager:
    """Manages starter questions with a simple TTL cache."""

    def __init__(self, questions: Optional[List[str]] = None) -> None:
        self.questions = questions or DEFAULT_QUESTIONS

    async def get_questions(self, count: int = 5) -> List[str]:
        """Return up to *count* starter questions."""
        return self.questions[:count]

    async def get_random_questions(self, count: int = 3) -> List[str]:
        if len(self.questions) <= count:
            return list(self.questions)
        return random.sample(self.questions, count)

    def clear_cache(self) -> None:
        """Reset to defaults (no-op in the static version)."""
        pass

    async def get_formatted_blocks(self) -> List[Dict[str, Any]]:
        """Return Slack Block Kit blocks for the starter questions."""
        questions = await self.get_questions()

        blocks: List[Dict[str, Any]] = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Here are some questions you can ask:*",
                },
            }
        ]

        for i, question in enumerate(questions[:5]):
            blocks.append(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"\u2022 {question}"},
                    "accessory": {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Ask this"},
                        "action_id": f"ask_question_{i}",
                        "value": question,
                    },
                }
            )

        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "You can also ask me anything about Indian law!",
                    }
                ],
            }
        )

        return blocks
