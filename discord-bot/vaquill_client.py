"""
Vaquill API Client — shared across all integration bots.

Usage:
    client = VaquillClient(api_key="vq_key_...")
    response = await client.ask("What is Section 302 IPC?")
    print(response["data"]["answer"])
"""

import aiohttp
import asyncio
import json
import ssl
import certifi
import logging
from typing import Dict, List, Optional, Any, AsyncGenerator

logger = logging.getLogger(__name__)


class VaquillClient:
    """Async client for the Vaquill Legal AI API."""

    DEFAULT_API_URL = "https://api.vaquill.ai/api/v1"

    def __init__(
        self,
        api_key: str,
        api_url: str = DEFAULT_API_URL,
        mode: str = "standard",
        country_code: Optional[str] = None,
    ):
        self.api_key = api_key
        self.api_url = api_url.rstrip("/")
        self.default_mode = mode
        self.default_country_code = country_code
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        self._session: Optional[aiohttp.ClientSession] = None
        self._ssl_context = ssl.create_default_context(cafile=certifi.where())

    # -- context manager --------------------------------------------------

    async def __aenter__(self):
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def _ensure_session(self):
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(ssl=self._ssl_context)
            self._session = aiohttp.ClientSession(connector=connector)

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    # -- core API methods -------------------------------------------------

    async def ask(
        self,
        question: str,
        *,
        mode: Optional[str] = None,
        sources: bool = True,
        max_sources: int = 5,
        chat_history: Optional[List[Dict[str, str]]] = None,
        country_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send a question to the Vaquill /ask endpoint.

        Returns the full API response dict:
            {
                "data": {"answer": "...", "sources": [...], "mode": "..."},
                "meta": {"processingTimeMs": ..., "creditsConsumed": ..., ...}
            }
        """
        await self._ensure_session()

        url = f"{self.api_url}/ask"

        payload: Dict[str, Any] = {
            "question": question,
            "mode": mode or self.default_mode,
            "sources": sources,
            "maxSources": max_sources,
        }

        cc = country_code or self.default_country_code
        if cc:
            payload["countryCode"] = cc

        if chat_history:
            payload["chatHistory"] = chat_history

        try:
            async with self._session.post(
                url, headers=self.headers, json=payload
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.debug("vaquill_response", extra={"status": 200})
                    return data
                elif response.status == 402:
                    error_text = await response.text()
                    logger.warning("insufficient_credits", extra={"error": error_text})
                    raise InsufficientCreditsError(error_text)
                elif response.status == 429:
                    error_text = await response.text()
                    logger.warning("rate_limited", extra={"error": error_text})
                    raise RateLimitError(error_text)
                else:
                    error_text = await response.text()
                    logger.error(
                        "vaquill_api_error",
                        extra={"status": response.status, "error": error_text},
                    )
                    raise VaquillAPIError(response.status, error_text)
        except aiohttp.ClientError as e:
            logger.error("vaquill_connection_error", extra={"error": str(e)})
            raise VaquillAPIError(0, str(e)) from e

    async def ask_stream(
        self,
        question: str,
        *,
        mode: Optional[str] = None,
        sources: bool = True,
        max_sources: int = 5,
        chat_history: Optional[List[Dict[str, str]]] = None,
        country_code: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Send a question to the Vaquill /ask/stream SSE endpoint.

        Yields parsed SSE event dicts. Event types:
            - init:     {"type": "init", ...}
            - thinking: {"type": "thinking", ...}
            - chunk:    {"type": "chunk", "text": "..."}
            - sources:  {"type": "sources", "sources": [...]}
            - done:     {"type": "done", "meta": {...}}
            - error:    {"type": "error", "message": "..."}
        """
        await self._ensure_session()

        url = f"{self.api_url}/ask/stream"

        payload: Dict[str, Any] = {
            "question": question,
            "mode": mode or self.default_mode,
            "sources": sources,
            "maxSources": max_sources,
        }

        cc = country_code or self.default_country_code
        if cc:
            payload["countryCode"] = cc

        if chat_history:
            payload["chatHistory"] = chat_history

        try:
            async with self._session.post(
                url, headers=self.headers, json=payload
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    yield {"type": "error", "message": error_text}
                    return

                event_type = None
                async for line in response.content:
                    line = line.decode("utf-8").strip()
                    if not line:
                        continue
                    if line.startswith("event:"):
                        event_type = line[6:].strip()
                    elif line.startswith("data:"):
                        data_str = line[5:].strip()
                        if data_str:
                            try:
                                data = json.loads(data_str)
                                data["type"] = event_type or "unknown"
                                yield data
                            except json.JSONDecodeError:
                                # Plain text chunk
                                yield {"type": event_type or "chunk", "text": data_str}
        except aiohttp.ClientError as e:
            yield {"type": "error", "message": str(e)}

    # -- helpers ----------------------------------------------------------

    def extract_answer(self, response: Dict[str, Any]) -> str:
        """Extract the answer text from an ask() response."""
        return response.get("data", {}).get("answer", "")

    def extract_sources(self, response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract sources from an ask() response."""
        return response.get("data", {}).get("sources", [])

    def format_sources_text(
        self, response: Dict[str, Any], max_sources: int = 3
    ) -> str:
        """Format sources as a readable text block."""
        sources = self.extract_sources(response)
        if not sources:
            return ""

        lines = []
        for i, src in enumerate(sources[:max_sources], 1):
            case_name = src.get("caseName") or src.get("case_name") or "Source"
            citation = src.get("citation") or ""
            court = src.get("court") or ""

            parts = [case_name]
            if citation:
                parts.append(citation)
            if court:
                parts.append(court)

            lines.append(f"{i}. {' | '.join(parts)}")

        return "\n".join(lines)


# -- exceptions ----------------------------------------------------------


class VaquillAPIError(Exception):
    """Raised when the Vaquill API returns an error."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"Vaquill API error {status_code}: {message}")


class InsufficientCreditsError(VaquillAPIError):
    """Raised when the API key has insufficient credits."""

    def __init__(self, message: str = "Insufficient credits"):
        super().__init__(402, message)


class RateLimitError(VaquillAPIError):
    """Raised when rate limited by the API."""

    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(429, message)
