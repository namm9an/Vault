"""LLM client — single entry point for all Gemini calls.

Every LLM call in the codebase must go through complete_json() or complete_vision_json().
No raw google-generativeai calls outside this module.
"""
import base64
import re
import time
from typing import TypeVar

import google.generativeai as genai
from google.api_core.exceptions import GoogleAPIError
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
    """Network/timeout error reaching the Gemini endpoint."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _get_model(system: str, temperature: float, max_tokens: int) -> genai.GenerativeModel:
    settings = get_settings()
    genai.configure(api_key=settings.GEMINI_API_KEY)
    return genai.GenerativeModel(
        model_name=settings.GEMINI_MODEL,
        system_instruction=system,
        generation_config=genai.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            response_mime_type="application/json",
        ),
    )


async def _call_and_validate(
    model: genai.GenerativeModel,
    parts: list,
    schema: type[T],
    total_start: int,
) -> tuple[T, int]:
    """Send parts to Gemini, validate JSON response, retry once on failure."""
    messages = list(parts)

    for attempt in range(2):
        try:
            response = await model.generate_content_async(messages)
        except GoogleAPIError as exc:
            raise LLMUnavailableError(f"Gemini API error: {exc}") from exc
        except Exception as exc:
            raise LLMUnavailableError(f"Gemini unexpected error: {exc}") from exc

        latency_ms = int(time.monotonic() * 1000) - total_start
        content = response.text or ""
        content = _strip_fences(content)

        try:
            result = schema.model_validate_json(content)
            return result, latency_ms
        except ValidationError as exc:
            if attempt == 0:
                messages = list(parts) + [
                    content,
                    (
                        f"Your previous response failed validation:\n{exc}\n\n"
                        "Return only valid JSON matching the schema. No explanation, no markdown."
                    ),
                ]
            else:
                raise LLMValidationError(schema=schema.__name__, raw=content) from exc

    raise LLMValidationError(schema=schema.__name__, raw="")  # pragma: no cover


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
    """Call Gemini with a text prompt and validate the JSON response.

    Returns (validated_result, latency_ms).
    Raises LLMValidationError or LLMUnavailableError — callers must handle both.
    """
    model = _get_model(system, temperature, max_tokens)
    total_start = int(time.monotonic() * 1000)
    return await _call_and_validate(model, [user], schema, total_start)


async def complete_vision_json(
    system: str,
    user: str,
    image_bytes: bytes,
    mime_type: str,
    schema: type[T],
    temperature: float = 0.0,
    max_tokens: int = 512,
) -> tuple[T, int]:
    """Call Gemini with an image + text prompt and validate the JSON response.

    Used by the OCR receipt pipeline. image_bytes is the raw file content.
    Returns (validated_result, latency_ms).
    Raises LLMValidationError or LLMUnavailableError — callers must handle both.
    """
    model = _get_model(system, temperature, max_tokens)
    total_start = int(time.monotonic() * 1000)

    image_part = {
        "inline_data": {
            "mime_type": mime_type,
            "data": base64.b64encode(image_bytes).decode("utf-8"),
        }
    }
    parts = [image_part, user]
    return await _call_and_validate(model, parts, schema, total_start)
