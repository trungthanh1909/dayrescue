"""Explicitly enabled invocation boundary; importing this module sends no requests."""

import os
from pathlib import Path

from dotenv import load_dotenv

from .agent import AgentResult, run_agent
from .meta_client import DEFAULT_MODEL, MetaProvider
from .models import DayContext

ROOT = Path(__file__).resolve().parents[1]


def live_ai_enabled() -> bool:
    # Do not load .env to discover this flag. The launching process must opt in.
    return os.getenv("DAYRESCUE_ENABLE_LIVE_AI") == "1"


def generate_live_result(context: DayContext) -> AgentResult:
    """Called only by an explicit UI action; no retries beyond agent correction."""
    if not live_ai_enabled():
        return AgentResult("provider_error", ())
    snapshot = context.model_copy(deep=True)
    provider = None

    def propose(request):
        nonlocal provider
        # Lazy construction lets run_agent preflight reject fixed conflicts with
        # zero HTTP requests and without loading credentials or creating a client.
        if provider is None:
            load_dotenv(ROOT / ".env", override=False, interpolate=False)
            provider = MetaProvider(model=DEFAULT_MODEL, reasoning_effort="low")
        return provider(request)

    try:
        try:
            return run_agent(snapshot, propose)
        finally:
            if provider is not None:
                provider.close()
    except Exception:
        # Setup/cleanup failures must not reach Streamlit's raw exception display.
        return AgentResult("provider_error", ())
