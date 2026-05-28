"""LLM client — single entry point for all TIR calls.

Every LLM call in the codebase must go through complete_json().
No raw httpx.post or openai calls outside this module.
"""
import re
import time
from typing import TypeVar

from openai import AsyncOpenAI, APIConnectionError, APITimeoutError, APIError
from pydantic import BaseModel, ValidationError

from api.config import get_settings

T = TypeVar("T", bound=BaseModel)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class LLMValidationError(Exception):
    """LLM response failed Pydantic validation after one retry."""

    def __init__(self, schema: str, raw: str) -> None:
        self.schema = schema
        self.raw = raw
        super().__init__(
            f"LLM response failed schema '{schema}' validation. "
            f"Raw (truncated): {raw[:300]}"
        )


class LLMUnavailableError(Exception):
    """Network/timeout error reaching the TIR endpoint."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _strip_fences(text: str) -> str:
    """Remove Markdown code fences — Llama 3.1 sometimes wraps JSON in them."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def complete_json(
    system: str,
    user: str,
    schema: type[T],
    temperature: float = 0.0,
    max_tokens: int = 512,
) -> tuple[T, int]:
    """Call the TIR LLM and validate the JSON response against a Pydantic schema.

    Returns (validated_result, latency_ms).

    Retry policy:
    - On ValidationError: retry once with the error appended to the user prompt.
    - On second failure: raise LLMValidationError(schema, raw_content).
    - On network/timeout: raise LLMUnavailableError immediately (no retry).

    Callers must catch LLMValidationError and LLMUnavailableError and handle
    gracefully — never let these propagate to an HTTP response.
    """
    settings = get_settings()
    client = AsyncOpenAI(
        base_url=settings.TIR_BASE_URL,
        api_key=settings.TIR_API_KEY,
        timeout=float(settings.TIR_TIMEOUT_SECONDS),
    )

    messages: list[dict] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    total_start = int(time.monotonic() * 1000)

    for attempt in range(2):
        try:
            response = await client.chat.completions.create(
                model=settings.TIR_MODEL,
                messages=messages,  # type: ignore[arg-type]
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
        except (APIConnectionError, APITimeoutError) as exc:
            raise LLMUnavailableError(f"TIR endpoint unreachable: {exc}") from exc
        except APIError as exc:
            raise LLMUnavailableError(f"TIR API error: {exc}") from exc

        latency_ms = int(time.monotonic() * 1000) - total_start
        content = response.choices[0].message.content or ""
        content = _strip_fences(content)

        try:
            result = schema.model_validate_json(content)
            return result, latency_ms
        except ValidationError as exc:
            if attempt == 0:
                # Append the validation error and retry once
                messages.append({"role": "assistant", "content": content})
                messages.append({
                    "role": "user",
                    "content": (
                        f"Your previous response failed validation:\n{exc}\n\n"
                        "Return only valid JSON matching the schema. No explanation, no markdown."
                    ),
                })
            else:
                raise LLMValidationError(schema=schema.__name__, raw=content) from exc

    # Unreachable — loop always returns or raises
    raise LLMValidationError(schema=schema.__name__, raw="")  # pragma: no cover
