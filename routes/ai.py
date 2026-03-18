from __future__ import annotations

import inspect
import logging
import os

from fastapi import APIRouter

router = APIRouter()
logger = logging.getLogger("astro-api")


def initialize_openai_client(app) -> None:
    # OpenAI client initialization retained for future AI endpoints.
    app.state.openai_client = None


async def shutdown_openai_client(app) -> None:
    client = getattr(app.state, "openai_client", None)
    if client is None:
        return

    close_result = client.close()
    if inspect.isawaitable(close_result):
        await close_result
    app.state.openai_client = None
