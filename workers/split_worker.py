from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from uuid import uuid4

import numpy as np
from numpy.typing import NDArray

logger = logging.getLogger(__name__)

SPLIT_SIMILARITY_THRESHOLD = float(os.getenv("DOCUMINT_SPLIT_THRESHOLD", "0.35"))
SPLIT_HEADING_THRESHOLD = float(os.getenv("DOCUMINT_SPLIT_HEADING_THRESHOLD", "0.55"))
ALLOW_LEXICAL_FALLBACK = (
    os.getenv("DOCUMINT_CLASSIFY_ALLOW_LEXICAL_FALLBACK", "true").lower() == "true"
)


async def split_document(
    parse_blocks: list[dict[str, object]],
    config: dict[str, object] | None = None,
) -> list[dict[str, object]]:
    return await asyncio.to_thread(_split_sync, parse_blocks, config or {})


def _split_sync(
    parse_blocks: list[dict[str, object]],
    config: dict[str, object],
) -> list[dict[str, object]]:
    pages = _page_text(parse_blocks)
    if not pages:
        return [
            {
                "segment_id": str(uuid4()),
                "start_page": 0,
                "end_page": 0,
                "label": "document",
                "confidence": 0.5,
                "page_count": 1,
                "evidence": "no parse blocks",
            }
        ]

    page_nums = sorted(pages)
    if len(page_nums) == 1:
        page = page_nums[0]
        return [_segment(page, page, _classify_segment_label(pages[page]), 0.8, "single page")]

    try:
        page_embeddings, model_name = _sentence_transformer_page_embeddings(pages, page_nums)
    except Exception as exc:
        if not ALLOW_LEXICAL_FALLBACK:
            raise RuntimeError(
                "SentenceTransformer split model is unavailable. "
                "Run scripts/download_models.py or set "
                "DOCUMINT_CLASSIFY_ALLOW_LEXICAL_FALLBACK=true."
            ) from exc
        logger.warning(
            "SentenceTransformer split unavailable (%s); using TF-IDF lexical fallback",
            exc,
        )
        page_embeddings, model_name = _tfidf_page_embeddings(pages, page_nums)

    similarities = [
        float(np.dot(page_embeddings[index], page_embeddings[index + 1]))
        for index in range(len(page_nums) - 1)
    ]
    min_segment = int(config.get("min_segment_pages", 1))
    boundaries = [page_nums[0]]

    for index, similarity in enumerate(similarities):
        candidate = page_nums[index + 1]
        if similarity < SPLIT_SIMILARITY_THRESHOLD and candidate - boundaries[-1] >= min_segment:
            boundaries.append(candidate)

    for page in _heading_boundary_pages(parse_blocks):
        if page not in boundaries and page in page_nums:
            page_index = page_nums.index(page)
            if page_index > 0 and similarities[page_index - 1] < SPLIT_HEADING_THRESHOLD:
                if page - boundaries[-1] >= min_segment:
                    boundaries.append(page)

    boundaries = sorted(set(boundaries))
    boundaries.append(page_nums[-1] + 1)

    segments: list[dict[str, object]] = []
    for index, start in enumerate(boundaries[:-1]):
        end = boundaries[index + 1] - 1
        segment_pages = [page for page in page_nums if start <= page <= end]
        segment_text = " ".join(pages[page] for page in segment_pages)[:1024]
        coherence = _segment_coherence(segment_pages, page_nums, page_embeddings)
        segments.append(
            _segment(
                start_page=start,
                end_page=end,
                label=_classify_segment_label(segment_text),
                confidence=coherence,
                evidence=f"{model_name} semantic coherence={coherence:.3f}",
            )
        )
    return segments


def _sentence_transformer_page_embeddings(
    pages: dict[int, str],
    page_nums: list[int],
) -> tuple[NDArray[np.float64], str]:
    from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]

    model_id = os.getenv("DOCUMINT_CLASSIFY_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    cache_dir = os.getenv(
        "DOCUMINT_MODEL_CACHE_DIR",
        os.path.expanduser("~/.cache/documint/models"),
    )
    model_path = _cached_snapshot_path(model_id, cache_dir) or model_id
    local_snapshot = model_path != model_id
    if local_snapshot:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    model = SentenceTransformer(
        model_path,
        cache_folder=cache_dir,
        local_files_only=local_snapshot,
        config_kwargs={"local_files_only": local_snapshot},
        model_kwargs={"local_files_only": local_snapshot},
    )
    embeddings = model.encode(
        [pages[page][:1024] for page in page_nums],
        normalize_embeddings=True,
    )
    return np.asarray(embeddings, dtype=np.float64), model_id


def _cached_snapshot_path(model_id: str, cache_dir: str) -> str | None:
    model_cache = Path(cache_dir) / f"models--{model_id.replace('/', '--')}"
    snapshots = model_cache / "snapshots"
    if not snapshots.exists():
        return None
    candidates = [path for path in snapshots.iterdir() if path.is_dir()]
    if not candidates:
        return None
    return str(max(candidates, key=lambda path: path.stat().st_mtime))


def _tfidf_page_embeddings(
    pages: dict[int, str],
    page_nums: list[int],
) -> tuple[NDArray[np.float64], str]:
    from sklearn.feature_extraction.text import TfidfVectorizer

    vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words="english")
    matrix = vectorizer.fit_transform([pages[page][:2048] for page in page_nums])
    dense = matrix.toarray().astype(np.float64)
    norms = np.linalg.norm(dense, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    return dense / norms, "tfidf_lexical_fallback"


def _segment_coherence(
    segment_pages: list[int],
    page_nums: list[int],
    page_embeddings: NDArray[np.float64],
) -> float:
    if len(segment_pages) <= 1:
        return 1.0
    indices = [page_nums.index(page) for page in segment_pages]
    similarities = [
        float(np.dot(page_embeddings[indices[index]], page_embeddings[indices[index + 1]]))
        for index in range(len(indices) - 1)
    ]
    return round(max(0.0, min(1.0, float(np.mean(similarities)))), 4)


def _segment(
    start_page: int,
    end_page: int,
    label: str,
    confidence: float,
    evidence: str,
) -> dict[str, object]:
    return {
        "segment_id": str(uuid4()),
        "start_page": start_page,
        "end_page": end_page,
        "label": label,
        "confidence": round(max(0.0, min(1.0, confidence)), 4),
        "page_count": end_page - start_page + 1,
        "evidence": evidence,
    }


def _page_text(parse_blocks: list[dict[str, object]]) -> dict[int, str]:
    pages: dict[int, list[str]] = {}
    for block in parse_blocks:
        text = str(block.get("text", "")).strip()
        if not text:
            continue
        pages.setdefault(int(block.get("page", 0)), []).append(text)
    return {page: " ".join(parts) for page, parts in pages.items()}


def _heading_boundary_pages(parse_blocks: list[dict[str, object]]) -> set[int]:
    pages: set[int] = set()
    for block in parse_blocks:
        page = int(block.get("page", 0))
        if page <= 0:
            continue
        text = str(block.get("text", "")).strip().lower()
        block_type = str(block.get("type", "")).lower()
        if block_type in {"heading", "header"}:
            pages.add(page)
        elif text.startswith(("section", "exhibit", "appendix", "schedule")):
            pages.add(page)
    return pages


def _classify_segment_label(text: str) -> str:
    text_lower = text.lower()[:500]
    labels = [
        ("invoice", ["invoice", "bill to", "amount due", "payment", "line items"]),
        ("contract", ["agreement", "hereby agrees", "terms and conditions", "whereas", "party"]),
        ("appendix", ["appendix", "exhibit", "schedule", "attachment", "supporting"]),
        ("table_of_contents", ["table of contents", "contents"]),
        ("financial", ["balance sheet", "income statement", "cash flow", "profit", "revenue"]),
        ("legal", ["court", "plaintiff", "defendant", "pursuant", "statute"]),
        ("report", ["executive summary", "findings", "methodology", "conclusion"]),
    ]
    for label, keywords in labels:
        if any(keyword in text_lower for keyword in keywords):
            return label
    return "document"
