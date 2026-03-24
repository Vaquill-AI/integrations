"""
Chat API Routes

FastAPI endpoints for chat functionality powered by Vaquill Legal AI.
Accepts a message and optional chat history, calls the Vaquill /ask endpoint,
and returns the answer with structured legal sources.
"""

import logging
import os
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from markdown_processor import preprocess_markdown
from vaquill_client import (
    InsufficientCreditsError,
    RateLimitError,
    VaquillAPIError,
    VaquillClient,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])

# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class ChatHistoryItem(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    chatHistory: Optional[List[ChatHistoryItem]] = None
    mode: Optional[str] = None  # "standard" | "deep" — defaults to env WIDGET_MODE


class Source(BaseModel):
    caseName: Optional[str] = None
    citation: Optional[str] = None
    court: Optional[str] = None
    excerpt: Optional[str] = None
    pdfUrl: Optional[str] = None
    relevanceScore: Optional[float] = None


class ChatResponse(BaseModel):
    answer: str
    sources: List[Source] = []
    questionInterpreted: Optional[str] = None
    mode: Optional[str] = None
    processingTimeMs: Optional[int] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_client() -> VaquillClient:
    api_key = os.getenv("VAQUILL_API_KEY", "")
    api_url = os.getenv("VAQUILL_API_URL", VaquillClient.DEFAULT_API_URL)
    default_mode = os.getenv("WIDGET_MODE", "standard")

    if not api_key:
        raise ValueError("VAQUILL_API_KEY environment variable is not set")

    return VaquillClient(api_key=api_key, api_url=api_url, mode=default_mode)


def _parse_sources(raw_sources: List[Dict[str, Any]]) -> List[Source]:
    """Convert raw Vaquill source dicts into typed Source models."""
    result: List[Source] = []
    for s in raw_sources:
        result.append(
            Source(
                caseName=s.get("caseName") or s.get("case_name"),
                citation=s.get("citation"),
                court=s.get("court"),
                excerpt=s.get("excerpt"),
                pdfUrl=s.get("pdfUrl") or s.get("pdf_url"),
                relevanceScore=s.get("relevanceScore") or s.get("relevance_score"),
            )
        )
    return result


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Send a message to Vaquill Legal AI and receive an answer with sources.

    Request body:
        message      — The user's question (required)
        chatHistory  — Previous turns for multi-turn context (optional)
        mode         — Override RAG mode: "standard" or "deep" (optional)

    Response:
        answer              — Markdown-formatted legal answer
        sources             — Structured legal source objects
        questionInterpreted — How Vaquill understood the question
        mode                — RAG mode used
        processingTimeMs    — Server-side processing time
    """
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="message must not be empty")

    try:
        client = _build_client()
    except ValueError as e:
        logger.error(f"Vaquill client init failed: {e}")
        raise HTTPException(status_code=500, detail="Vaquill API key not configured")

    # Convert chat history to the format VaquillClient expects
    history: Optional[List[Dict[str, str]]] = None
    if request.chatHistory:
        history = [
            {"role": item.role, "content": item.content}
            for item in request.chatHistory
        ]

    start = time.time()

    try:
        async with client:
            response = await client.ask(
                question=request.message,
                mode=request.mode,
                sources=True,
                max_sources=5,
                chat_history=history,
            )

        elapsed_ms = int((time.time() - start) * 1000)

        data = response.get("data", {})
        meta = response.get("meta", {})

        raw_answer = data.get("answer", "")
        answer = preprocess_markdown(raw_answer)

        sources = _parse_sources(data.get("sources", []))

        logger.info(
            f"[CHAT] question={request.message[:80]!r} "
            f"mode={data.get('mode')} sources={len(sources)} elapsed={elapsed_ms}ms"
        )

        return ChatResponse(
            answer=answer,
            sources=sources,
            questionInterpreted=data.get("questionInterpreted"),
            mode=data.get("mode"),
            processingTimeMs=meta.get("processingTimeMs", elapsed_ms),
        )

    except InsufficientCreditsError:
        logger.warning("[CHAT] Insufficient credits")
        raise HTTPException(
            status_code=402,
            detail="Insufficient API credits. Please top up your Vaquill account.",
        )
    except RateLimitError:
        logger.warning("[CHAT] Rate limited by Vaquill API")
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please slow down and try again shortly.",
        )
    except VaquillAPIError as e:
        logger.error(f"[CHAT] Vaquill API error {e.status_code}: {e.message[:200]}")
        raise HTTPException(
            status_code=502, detail="Error communicating with Vaquill API"
        )
    except Exception as e:
        logger.error(f"[CHAT] Unexpected error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
