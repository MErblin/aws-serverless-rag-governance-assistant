"""
DocuChat RAG - Google Gemini LLM Provider

Drop-in replacement for Ollama when LLM_PROVIDER=gemini.
Uses the modern google-genai SDK (google.genai) with gemini-1.5-flash (free tier).

Free tier limits:
  - 1,500 requests/day
  - 15 requests/minute
  - No billing required

Get a free API key: https://aistudio.google.com/app/apikey
"""

import logging

from google import genai
from google.genai import types

from app.config import get_settings

logger = logging.getLogger("docuchat.api.gemini")

# Module-level client cache — created once per process
_client: genai.Client | None = None


def _get_client() -> genai.Client:
    """Return a cached Gemini client, creating it on first call."""
    global _client
    if _client is None:
        settings = get_settings()
        if not settings.gemini_api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. "
                "Get a free key at https://aistudio.google.com/app/apikey "
                "and add it to your .env file."
            )
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


def get_gemini_response(prompt: str) -> str:
    """
    Send a prompt to Google Gemini and return the text response.

    Args:
        prompt: The full prompt string (system + context + question).

    Returns:
        The generated answer as a string.

    Raises:
        RuntimeError: If the API key is missing or the API call fails.
    """
    settings = get_settings()
    client = _get_client()

    logger.info("Calling Gemini model=%s", settings.gemini_model)

    try:
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,        # Low temperature for factual GRC answers
                max_output_tokens=1024,
            ),
        )
        return response.text
    except Exception as exc:
        logger.exception("Gemini API call failed")
        raise RuntimeError(f"Gemini API error: {exc}") from exc
