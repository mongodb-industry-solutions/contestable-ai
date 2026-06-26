"""
Central configuration and client factory.
Supports direct OpenAI and gateway-based access (e.g. Grove) via env vars.
Embeddings are handled by Voyage AI.
"""
from __future__ import annotations
import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY        = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL       = os.getenv("OPENAI_BASE_URL") or None
OPENAI_API_KEY_HEADER = os.getenv("OPENAI_API_KEY_HEADER") or "Authorization"
OPENAI_API_VERSION    = os.getenv("OPENAI_API_VERSION") or None
OPENAI_MODEL          = os.getenv("OPENAI_MODEL", "gpt-4o")

VOYAGE_API_KEY        = os.getenv("VOYAGE_API_KEY")
VOYAGE_MODEL          = os.getenv("VOYAGE_MODEL", "voyage-3-large")
VOYAGE_EMBEDDING_DIMS = 1024

MONGODB_URI           = os.getenv("MONGODB_URI", "mongodb://localhost:27017")


def make_openai_client():
    """
    Return an OpenAI client configured for the active gateway (Grove or direct).

    Grove (and similar gateways) authenticate via a custom header instead of the
    standard 'Authorization: Bearer' that the SDK sends by default.
    """
    from openai import OpenAI

    kwargs: dict = {"api_key": OPENAI_API_KEY}

    if OPENAI_BASE_URL:
        kwargs["base_url"] = OPENAI_BASE_URL

    if OPENAI_API_KEY_HEADER.lower() != "authorization":
        kwargs["default_headers"] = {OPENAI_API_KEY_HEADER: OPENAI_API_KEY}

    return OpenAI(**kwargs)


def make_crewai_llm():
    """
    Return a CrewAI LLM instance routed through Grove or direct OpenAI.

    CrewAI uses LiteLLM under the hood; extra_headers are forwarded to every
    completion call so Grove's custom auth header reaches the gateway.
    """
    from crewai import LLM

    kwargs: dict = {
        "model": OPENAI_MODEL,
        "api_key": OPENAI_API_KEY,
        "timeout": 90.0,  # fail fast rather than hanging indefinitely
    }

    if OPENAI_BASE_URL:
        kwargs["base_url"] = OPENAI_BASE_URL

    if OPENAI_API_KEY_HEADER.lower() != "authorization":
        kwargs["default_headers"] = {OPENAI_API_KEY_HEADER: OPENAI_API_KEY}

    return LLM(**kwargs)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of strings with Voyage AI. Returns a list of float vectors."""
    import voyageai
    vo = voyageai.Client(api_key=VOYAGE_API_KEY)
    result = vo.embed(texts, model=VOYAGE_MODEL, input_type="document")
    return result.embeddings


def embed_query(text: str) -> list[float]:
    """Embed a single query string with Voyage AI (uses query input_type for retrieval)."""
    import voyageai
    vo = voyageai.Client(api_key=VOYAGE_API_KEY)
    result = vo.embed([text], model=VOYAGE_MODEL, input_type="query")
    return result.embeddings[0]
