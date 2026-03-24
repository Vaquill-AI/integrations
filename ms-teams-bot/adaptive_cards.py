"""
Adaptive Cards for Vaquill Microsoft Teams Bot
"""

from typing import Dict, List, Any, Optional


class AdaptiveCardBuilder:
    """Builder for Microsoft Teams Adaptive Cards"""

    @staticmethod
    def create_welcome_card(
        bot_name: str = "Vaquill",
        starter_questions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create a welcome card with starter questions"""
        if starter_questions is None:
            starter_questions = [
                "What is Section 302 of IPC?",
                "Explain the doctrine of res judicata",
                "What are the grounds for divorce under Hindu Marriage Act?",
            ]

        card = {
            "type": "AdaptiveCard",
            "version": "1.5",
            "body": [
                {
                    "type": "Container",
                    "items": [
                        {
                            "type": "TextBlock",
                            "text": f"Welcome to {bot_name}!",
                            "weight": "Bolder",
                            "size": "Large",
                            "horizontalAlignment": "Center",
                            "spacing": "Medium",
                        },
                        {
                            "type": "TextBlock",
                            "text": (
                                "I'm your AI-powered legal research assistant. "
                                "Ask me anything about Indian law, or choose "
                                "from the suggestions below."
                            ),
                            "wrap": True,
                            "horizontalAlignment": "Center",
                            "spacing": "Small",
                        },
                    ],
                }
            ],
        }

        if starter_questions:
            question_container = {
                "type": "Container",
                "spacing": "Large",
                "items": [
                    {
                        "type": "TextBlock",
                        "text": "**Suggested Questions:**",
                        "weight": "Bolder",
                        "spacing": "Medium",
                    }
                ],
            }

            actions = []
            for question in starter_questions[:5]:
                actions.append(
                    {
                        "type": "Action.Submit",
                        "title": question,
                        "data": {
                            "action": "ask_question",
                            "question": question,
                        },
                    }
                )

            card["body"].append(question_container)
            card["actions"] = actions

        return AdaptiveCardBuilder._create_attachment(card)

    @staticmethod
    def create_response_card(
        response: str,
        sources: Optional[List[Dict[str, Any]]] = None,
        show_feedback: bool = True,
    ) -> Dict[str, Any]:
        """Create a response card with sources and feedback buttons"""
        card = {
            "type": "AdaptiveCard",
            "version": "1.5",
            "body": [
                {
                    "type": "TextBlock",
                    "text": response,
                    "wrap": True,
                    "size": "Default",
                }
            ],
            "actions": [],
        }

        # Add sources if available
        if sources:
            sources_container = {
                "type": "Container",
                "spacing": "Large",
                "separator": True,
                "items": [
                    {
                        "type": "TextBlock",
                        "text": "**Sources:**",
                        "weight": "Bolder",
                        "size": "Small",
                        "spacing": "Medium",
                    }
                ],
            }

            for src in sources[:5]:
                case_name = (
                    src.get("caseName")
                    or src.get("case_name")
                    or "Source"
                )
                citation = src.get("citation") or ""
                court = src.get("court") or ""

                label_parts = [case_name]
                if citation:
                    label_parts.append(citation)
                if court:
                    label_parts.append(court)

                source_item = {
                    "type": "Container",
                    "spacing": "Small",
                    "items": [
                        {
                            "type": "TextBlock",
                            "text": f"- {' | '.join(label_parts)}",
                            "wrap": True,
                            "size": "Small",
                            "color": "Accent",
                        }
                    ],
                }
                sources_container["items"].append(source_item)

            card["body"].append(sources_container)

        # Add feedback buttons
        if show_feedback:
            card["actions"].extend(
                [
                    {
                        "type": "Action.Submit",
                        "title": "Helpful",
                        "data": {"action": "feedback", "reaction": "thumbs_up"},
                    },
                    {
                        "type": "Action.Submit",
                        "title": "Not helpful",
                        "data": {"action": "feedback", "reaction": "thumbs_down"},
                    },
                ]
            )

        # Add copy button
        card["actions"].append(
            {
                "type": "Action.Submit",
                "title": "Copy Response",
                "data": {"action": "copy", "text": response},
            }
        )

        return AdaptiveCardBuilder._create_attachment(card)

    @staticmethod
    def create_error_card(
        error_message: str,
        details: Optional[str] = None,
        retry_available: bool = True,
    ) -> Dict[str, Any]:
        """Create an error card"""
        card = {
            "type": "AdaptiveCard",
            "version": "1.5",
            "body": [
                {
                    "type": "Container",
                    "style": "attention",
                    "items": [
                        {
                            "type": "ColumnSet",
                            "columns": [
                                {
                                    "type": "Column",
                                    "width": "auto",
                                    "items": [
                                        {
                                            "type": "TextBlock",
                                            "text": "**Error**",
                                            "size": "Large",
                                        }
                                    ],
                                },
                                {
                                    "type": "Column",
                                    "width": "stretch",
                                    "items": [
                                        {
                                            "type": "TextBlock",
                                            "text": error_message,
                                            "wrap": True,
                                            "spacing": "Small",
                                        }
                                    ],
                                },
                            ],
                        }
                    ],
                }
            ],
        }

        if details:
            card["body"].append(
                {
                    "type": "Container",
                    "spacing": "Medium",
                    "items": [
                        {
                            "type": "TextBlock",
                            "text": details,
                            "wrap": True,
                            "size": "Small",
                            "isSubtle": True,
                        }
                    ],
                }
            )

        if retry_available:
            card["actions"] = [
                {
                    "type": "Action.Submit",
                    "title": "Try Again",
                    "data": {"action": "retry"},
                }
            ]

        return AdaptiveCardBuilder._create_attachment(card)

    @staticmethod
    def create_rate_limit_card(
        reset_time: int,
        user_remaining: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Create a rate limit notification card"""
        card = {
            "type": "AdaptiveCard",
            "version": "1.5",
            "body": [
                {
                    "type": "Container",
                    "style": "warning",
                    "items": [
                        {
                            "type": "TextBlock",
                            "text": "**Rate Limit Reached**",
                            "weight": "Bolder",
                            "size": "Medium",
                        },
                        {
                            "type": "TextBlock",
                            "text": (
                                f"Please wait {reset_time} seconds "
                                "before sending another message."
                            ),
                            "wrap": True,
                            "spacing": "Small",
                        },
                    ],
                }
            ],
        }

        if user_remaining is not None:
            card["body"].append(
                {
                    "type": "Container",
                    "spacing": "Medium",
                    "items": [
                        {
                            "type": "TextBlock",
                            "text": f"Messages remaining: {user_remaining}",
                            "size": "Small",
                        }
                    ],
                }
            )

        return AdaptiveCardBuilder._create_attachment(card)

    @staticmethod
    def create_feedback_confirmation_card(reaction: str) -> Dict[str, Any]:
        """Create a feedback confirmation card"""
        message = (
            "Thank you for your positive feedback!"
            if reaction == "thumbs_up"
            else "Thank you for your feedback. We'll work on improving."
        )

        card = {
            "type": "AdaptiveCard",
            "version": "1.5",
            "body": [
                {
                    "type": "Container",
                    "style": "good" if reaction == "thumbs_up" else "attention",
                    "items": [
                        {
                            "type": "TextBlock",
                            "text": message,
                            "wrap": True,
                            "horizontalAlignment": "Center",
                        }
                    ],
                }
            ],
        }

        return AdaptiveCardBuilder._create_attachment(card)

    @staticmethod
    def create_help_card() -> Dict[str, Any]:
        """Create a help card with bot instructions"""
        card = {
            "type": "AdaptiveCard",
            "version": "1.5",
            "body": [
                {
                    "type": "TextBlock",
                    "text": "**Vaquill Bot Help**",
                    "weight": "Bolder",
                    "size": "Large",
                },
                {
                    "type": "Container",
                    "spacing": "Medium",
                    "items": [
                        {
                            "type": "TextBlock",
                            "text": "**How to use this bot:**",
                            "weight": "Bolder",
                            "spacing": "Medium",
                        },
                        {
                            "type": "TextBlock",
                            "text": "In channels: @mention me with your question",
                            "wrap": True,
                        },
                        {
                            "type": "TextBlock",
                            "text": "In direct chat: Just type your question",
                            "wrap": True,
                        },
                        {
                            "type": "TextBlock",
                            "text": "Use threads to maintain context in conversations",
                            "wrap": True,
                        },
                    ],
                },
                {
                    "type": "Container",
                    "spacing": "Medium",
                    "items": [
                        {
                            "type": "TextBlock",
                            "text": "**Available Commands:**",
                            "weight": "Bolder",
                            "spacing": "Medium",
                        },
                        {
                            "type": "TextBlock",
                            "text": "**/help** - Show this help message",
                            "wrap": True,
                        },
                        {
                            "type": "TextBlock",
                            "text": "**/clear** - Clear conversation history",
                            "wrap": True,
                        },
                        {
                            "type": "TextBlock",
                            "text": "**/status** - Check bot status and limits",
                            "wrap": True,
                        },
                    ],
                },
            ],
        }

        return AdaptiveCardBuilder._create_attachment(card)

    @staticmethod
    def create_typing_indicator_card() -> Dict[str, Any]:
        """Create a typing indicator card"""
        card = {
            "type": "AdaptiveCard",
            "version": "1.5",
            "body": [
                {
                    "type": "Container",
                    "items": [
                        {
                            "type": "TextBlock",
                            "text": "Vaquill is thinking...",
                            "isSubtle": True,
                        }
                    ],
                }
            ],
        }

        return AdaptiveCardBuilder._create_attachment(card)

    @staticmethod
    def _create_attachment(card: Dict[str, Any]) -> Dict[str, Any]:
        """Create an attachment from an Adaptive Card"""
        return {
            "contentType": "application/vnd.microsoft.card.adaptive",
            "content": card,
        }
