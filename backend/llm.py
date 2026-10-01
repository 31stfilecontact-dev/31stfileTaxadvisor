"""Provider boundary for future language-model and embedding features.

Prompt 1 does not call a language model or generate embeddings. Later features
must use this module so the provider can be changed without coupling services.
"""

from typing import Any

from backend.config import settings


def generate(prompt: str, **options: Any) -> str:
    """Generate text through the configured provider when analysis is enabled."""
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured.")
    raise NotImplementedError("LLM analysis is not part of Prompt 1.")


def embed(text: str, **options: Any) -> list[float]:
    """Create a 768-dimensional embedding through the configured provider."""
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured.")
    raise NotImplementedError("Embedding generation is not part of Prompt 1.")