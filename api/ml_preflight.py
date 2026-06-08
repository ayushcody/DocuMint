from __future__ import annotations

import importlib.util
import logging
import os

logger = logging.getLogger(__name__)

PROFILE = os.getenv("DOCUMINT_PROFILE", "full").lower()

PROFILE_REQUIREMENTS: dict[str, list[str]] = {
    "parse_only": ["docling"],
    "parse_extract": ["docling", "outlines"],
    "full": ["docling", "outlines", "colpali_engine", "qdrant_client"],
    "rag_only": ["colpali_engine", "qdrant_client"],
}


def check_required_models() -> None:
    required = PROFILE_REQUIREMENTS.get(PROFILE, PROFILE_REQUIREMENTS["full"])
    missing: list[str] = []

    if "docling" in required and _missing("docling") and not _layout_fallback_enabled():
        missing.append(
            "docling - required for Agent 2 layout detection. Install: pip install docling"
        )
    if "outlines" in required and _missing("outlines") and not _remote_extraction_enabled():
        missing.append(
            "outlines - required for Agent 6 constrained decoding. Install: pip install "
            "outlines, or set DOCUMINT_EXTRACTION_ENDPOINT to use a remote SGLang server"
        )
    if "colpali_engine" in required and _missing("colpali_engine"):
        missing.append(
            "colpali-engine - required for Agent 7 visual RAG. Install: pip install "
            "colpali-engine, or set DOCUMINT_PROFILE=parse_extract to run without RAG"
        )
    if "qdrant_client" in required and _missing("qdrant_client"):
        missing.append(
            "qdrant-client - required for Agent 7 vector storage. "
            "Install: pip install qdrant-client"
        )

    if missing:
        raise RuntimeError(
            f"DocuMint startup failed (profile='{PROFILE}'). Missing required "
            "dependencies:\n"
            + "\n".join(f"  - {item}" for item in missing)
            + "\n\nTo start without RAG: set DOCUMINT_PROFILE=parse_extract"
        )

    logger.info(
        "DocuMint preflight passed. Profile=%s. Required deps verified=%s",
        PROFILE,
        required,
    )


def rag_enabled() -> bool:
    return PROFILE in {"full", "rag_only"}


def _missing(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is None


def _layout_fallback_enabled() -> bool:
    return os.getenv("DOCUMINT_LAYOUT_FALLBACK_HEURISTIC", "").lower() == "true"


def _remote_extraction_enabled() -> bool:
    return bool(os.getenv("DOCUMINT_EXTRACTION_ENDPOINT"))
