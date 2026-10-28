"""Make ONE real Muse Spark chat completion to verify Meta Model API access."""

from pathlib import Path
import os
import sys

from dotenv import load_dotenv
from openai import OpenAI, OpenAIError

ROOT = Path(__file__).resolve().parents[1]
META_BASE_URL = "https://api.meta.ai/v1"
DEFAULT_MODEL = "muse-spark-1.3"


def main() -> int:
    load_dotenv(ROOT / ".env")
    key = os.getenv("MODEL_API_KEY", "").strip()
    model = os.getenv("META_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL

    if not key:
        print(
            "SMOKE BLOCKED: MODEL_API_KEY is missing. Copy .env.example to .env "
            "and set the key locally; never paste the key into chat or commit it.",
            file=sys.stderr,
        )
        return 2

    client = OpenAI(
        base_url=META_BASE_URL,
        api_key=key,
        timeout=30.0,
        max_retries=0,  # Explicitly one attempt for a reproducible smoke test.
    )
    try:
        result = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "user", "content": "Reply with exactly the word DAYRESCUE_READY."}
            ],
        )
    except OpenAIError as exc:
        status = getattr(exc, "status_code", None)
        print(
            f"SMOKE FAIL: {type(exc).__name__}; HTTP status={status or 'n/a'}. "
            "Check API key scope/credits, model access, network, and Meta dashboard. "
            "No secret or raw error body printed.",
            file=sys.stderr,
        )
        return 1

    if not result.choices or not (result.choices[0].message.content or "").strip():
        print("SMOKE FAIL: request returned no visible text content.", file=sys.stderr)
        return 1

    print("SMOKE PASS: live Meta Model API completion received.")
    print(f"Model: {result.model}")
    print(f"Model response: {result.choices[0].message.content.strip()}")
    if result.usage is not None:
        print(f"Total tokens: {result.usage.total_tokens}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
