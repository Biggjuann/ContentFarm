"""FastAPI service — Railway entrypoint.

Exposes:
- GET /health           liveness probe
- GET /                 minimal status banner
- POST /generate        run the full pipeline for a topic
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .config import SETTINGS
from .pipeline import run_pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("contentfarm.server")

app = FastAPI(
    title="ContentFarm",
    version="0.1.0",
    description="Multi-agent short-form video script generator.",
)


class GenerateRequest(BaseModel):
    topic: str = Field(..., min_length=2, max_length=200)


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "model": SETTINGS.model,
        "anthropic_configured": "yes" if SETTINGS.anthropic_api_key else "no",
        "youtube_configured": "yes" if SETTINGS.youtube_api_key else "no",
        "reddit_configured": "yes" if (SETTINGS.reddit_client_id and SETTINGS.reddit_client_secret) else "no",
        "x_configured": "yes" if SETTINGS.x_bearer_token else "no",
    }


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": "ContentFarm",
        "endpoints": "GET /health, POST /generate",
    }


@app.post("/generate")
def generate(req: GenerateRequest) -> dict:
    if not SETTINGS.anthropic_api_key:
        raise HTTPException(
            status_code=500,
            detail="ANTHROPIC_API_KEY is not configured on the server.",
        )
    try:
        result = run_pipeline(req.topic)
    except Exception as exc:
        log.exception("Pipeline failed for topic=%r", req.topic)
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {exc}")

    return result.to_dict()
