"""
Vaquill Chat Widget — FastAPI backend

Serves:
  POST /api/chat         — Proxy to Vaquill /ask with chat history
  GET  /api/widget/info  — Widget display configuration (title, branding)
  GET  /health           — Health check
  GET  /*                — Static frontend (React SPA)
"""

import logging
import mimetypes
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from routes.chat import router as chat_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

FRONTEND_DIST = "/app/frontend/dist"


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    _validate_config()
    logger.info("Vaquill Widget backend started")
    yield
    logger.info("Vaquill Widget backend shutting down")


def _validate_config() -> None:
    api_key = os.getenv("VAQUILL_API_KEY", "")
    if not api_key:
        logger.error("VAQUILL_API_KEY is not set — chat requests will fail")
    elif not api_key.startswith("vq_"):
        logger.warning("VAQUILL_API_KEY does not start with 'vq_' — check the value")
    else:
        logger.info(f"VAQUILL_API_KEY present ({api_key[:10]}...)")

    logger.info(f"VAQUILL_API_URL = {os.getenv('VAQUILL_API_URL', '(default)')}")
    logger.info(f"WIDGET_TITLE    = {os.getenv('WIDGET_TITLE', 'Vaquill Legal AI')}")
    logger.info(f"WIDGET_MODE     = {os.getenv('WIDGET_MODE', 'standard')}")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Vaquill Chat Widget",
    description="Embeddable legal AI chat widget powered by Vaquill",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow all origins by default so the embed script works everywhere.
# Restrict via ALLOWED_ORIGINS env var in production.
_raw_origins = os.getenv("ALLOWED_ORIGINS", "*")
_origins = (
    ["*"] if _raw_origins.strip() == "*" else [o.strip() for o in _raw_origins.split(",")]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=_raw_origins.strip() != "*",
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

app.include_router(chat_router)


@app.get("/health", tags=["system"])
async def health():
    """Liveness probe."""
    return {"status": "ok", "service": "vaquill-widget"}


@app.get("/api/widget/info", tags=["system"])
async def widget_info():
    """
    Return widget display configuration used by the frontend.
    """
    return {
        "title": os.getenv("WIDGET_TITLE", "Vaquill Legal AI"),
        "mode": os.getenv("WIDGET_MODE", "standard"),
        "branding": {
            "primaryColor": "#1a56db",
            "logoText": "Vaquill",
        },
        "suggestedQuestions": [
            "What is Section 302 of the IPC?",
            "Explain the right to bail under CrPC.",
            "What are the grounds for divorce under the Hindu Marriage Act?",
            "Summarise the landmark ruling in Maneka Gandhi v. Union of India.",
        ],
    }


# ---------------------------------------------------------------------------
# Static frontend (catch-all, must come last)
# ---------------------------------------------------------------------------


@app.get("/")
async def root():
    logger.debug("[ROUTE] GET / — serving index.html")
    return FileResponse(f"{FRONTEND_DIST}/index.html")


@app.get("/{full_path:path}")
async def catch_all(full_path: str):
    static_file = f"{FRONTEND_DIST}/{full_path}"

    if os.path.isfile(static_file):
        mime_type, _ = mimetypes.guess_type(static_file)

        if full_path.endswith(".wasm"):
            mime_type = "application/wasm"
        elif full_path.endswith((".js", ".mjs")):
            mime_type = "application/javascript"
        elif full_path.endswith(".onnx"):
            mime_type = "application/octet-stream"

        logger.debug(f"[ROUTE] GET /{full_path} — static ({mime_type})")
        return FileResponse(static_file, media_type=mime_type)

    logger.debug(f"[ROUTE] GET /{full_path} — SPA fallback")
    return FileResponse(f"{FRONTEND_DIST}/index.html")
