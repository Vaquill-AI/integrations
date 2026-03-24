"""
Starter and follow-up question suggestions for the Vaquill WhatsApp bot.
"""

import random
import re
from typing import List, Optional

import structlog

from config import STARTER_QUESTIONS

logger = structlog.get_logger()


class StarterQuestions:
    def __init__(self):
        self.questions = STARTER_QUESTIONS

        # Keywords -> category mapping
        self.keyword_categories = {
            "general": ["help", "start", "begin", "what", "how", "can", "law"],
            "criminal": [
                "criminal", "fir", "arrest", "bail", "police",
                "murder", "theft", "ipc", "crpc",
            ],
            "civil": [
                "civil", "suit", "contract", "consumer", "property",
                "landlord", "tenant", "decree",
            ],
            "constitutional": [
                "constitution", "fundamental", "article", "pil",
                "writ", "supreme court", "high court",
            ],
        }

        # Follow-up templates (legal domain)
        self.follow_up_templates = {
            "clarification": [
                "Can you explain more about {topic}?",
                "What are the key provisions related to {topic}?",
                "How does {topic} apply in practice?",
            ],
            "deeper": [
                "What are the landmark judgments on {topic}?",
                "How has {topic} evolved over time?",
                "What are the exceptions to {topic}?",
            ],
            "related": [
                "How does {topic} compare to similar provisions?",
                "What are the common legal issues with {topic}?",
                "What recent amendments affect {topic}?",
            ],
        }

    async def get_initial_questions(
        self, category: Optional[str] = None
    ) -> List[str]:
        if category and category in self.questions:
            return self.questions[category]
        all_q = [q for qs in self.questions.values() for q in qs]
        return random.sample(all_q, min(5, len(all_q)))

    async def get_suggestions(
        self, user_message: str, bot_response: str
    ) -> List[str]:
        suggestions: List[str] = []
        try:
            topic = self._extract_topic(user_message, bot_response)
            category = self._detect_category(user_message)

            if topic and len(topic) > 3:
                for ttype in ("clarification", "deeper"):
                    if ttype in self.follow_up_templates:
                        tmpl = random.choice(self.follow_up_templates[ttype])
                        suggestions.append(tmpl.format(topic=topic))

            if category and category in self.questions:
                candidates = [
                    q
                    for q in self.questions[category]
                    if q.lower() not in user_message.lower()
                ]
                if candidates:
                    suggestions.append(random.choice(candidates))

            # Deduplicate, cap at 3
            suggestions = list(dict.fromkeys(suggestions))[:3]

            if not suggestions:
                pool = self.questions.get("general", [])
                suggestions = random.sample(pool, min(3, len(pool)))
        except Exception as e:
            logger.error("suggestion_error", error=str(e))
            suggestions = self.questions.get("general", [])[:3]

        return suggestions

    # -- internals --------------------------------------------------------

    def _detect_category(self, message: str) -> Optional[str]:
        lower = message.lower()
        scores = {}
        for cat, kws in self.keyword_categories.items():
            score = sum(1 for kw in kws if kw in lower)
            if score > 0:
                scores[cat] = score
        if scores:
            return max(scores, key=scores.get)
        return "general"

    def _extract_topic(
        self, user_message: str, bot_response: str
    ) -> Optional[str]:
        indicators = [
            "about", "regarding", "under", "section", "article",
            "for", "with", "of", "on",
        ]
        words = user_message.lower().split()
        for i, w in enumerate(words):
            if w in indicators and i + 1 < len(words):
                topic_words = []
                for j in range(i + 1, min(i + 4, len(words))):
                    if words[j] not in ("the", "a", "an", "it", "this", "that", "is", "are"):
                        topic_words.append(words[j])
                    else:
                        break
                if topic_words:
                    topic = " ".join(topic_words)
                    if len(topic) > 2:
                        return topic

        quoted = re.findall(r'"([^"]+)"', bot_response)
        if quoted:
            return quoted[0].lower()

        return None

    def get_category_questions(self, category: str) -> List[str]:
        return self.questions.get(category, self.questions["general"])

    def get_random_questions(
        self, count: int = 3, exclude: Optional[List[str]] = None
    ) -> List[str]:
        exclude = exclude or []
        pool = [q for qs in self.questions.values() for q in qs if q not in exclude]
        return random.sample(pool, min(count, len(pool)))
