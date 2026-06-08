from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

import numpy as np
from numpy.typing import NDArray

logger = logging.getLogger(__name__)

ST_MODEL_ID = os.getenv("DOCUMINT_CLASSIFY_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
CLASSIFY_THRESHOLD = float(os.getenv("DOCUMINT_CLASSIFY_THRESHOLD", "0.25"))
ALLOW_LEXICAL_FALLBACK = (
    os.getenv("DOCUMINT_CLASSIFY_ALLOW_LEXICAL_FALLBACK", "true").lower() == "true"
)

_st_model: object | None = None

TaxonomyInput = str | dict[str, object]


@dataclass(frozen=True, slots=True)
class ClassificationResult:
    run_id: UUID
    page_labels: dict[int, str]
    scores: dict[str, float]
    classifications: list[dict[str, object]]


def classify_pages(
    parse_blocks: list[dict[str, object]],
    taxonomy: list[TaxonomyInput],
    threshold: float = CLASSIFY_THRESHOLD,
) -> ClassificationResult:
    classifications = _classify_sync(parse_blocks, taxonomy, threshold)
    return ClassificationResult(
        run_id=uuid4(),
        page_labels={int(item["page_num"]): str(item["label"]) for item in classifications},
        scores={
            f"{item['page_num']}:{label}": float(score)
            for item in classifications
            for label, score in _as_score_dict(item.get("scores", {})).items()
        },
        classifications=classifications,
    )


async def classify_document(
    parse_blocks: list[dict[str, object]],
    taxonomy: list[TaxonomyInput],
    threshold: float = CLASSIFY_THRESHOLD,
) -> list[dict[str, object]]:
    return await asyncio.to_thread(_classify_sync, parse_blocks, taxonomy, threshold)


def _classify_sync(
    parse_blocks: list[dict[str, object]],
    taxonomy: list[TaxonomyInput],
    threshold: float,
) -> list[dict[str, object]]:
    categories = _normalize_taxonomy(taxonomy)
    if not categories:
        return []

    pages = _page_text(parse_blocks)
    if not pages:
        return []

    try:
        return _classify_with_sentence_transformers(pages, categories, threshold)
    except Exception as exc:
        if not ALLOW_LEXICAL_FALLBACK:
            raise RuntimeError(
                "SentenceTransformer classification model is unavailable. "
                "Run scripts/download_models.py or set "
                "DOCUMINT_CLASSIFY_ALLOW_LEXICAL_FALLBACK=true."
            ) from exc
        logger.warning(
            "SentenceTransformer classification unavailable (%s); using TF-IDF lexical fallback",
            exc,
        )
        return _classify_with_tfidf(pages, categories, threshold)


def _classify_with_sentence_transformers(
    pages: dict[int, str],
    categories: list[dict[str, str]],
    threshold: float,
) -> list[dict[str, object]]:
    model = _get_st_model()
    taxonomy_texts = [
        f"{item['label']}: {item.get('description') or item['label']}" for item in categories
    ]
    taxonomy_embeddings = model.encode(taxonomy_texts, normalize_embeddings=True)
    page_nums = sorted(pages)
    page_texts = [pages[page_num][:1024] for page_num in page_nums]
    page_embeddings = model.encode(page_texts, normalize_embeddings=True)
    return _rank_pages(
        page_nums=page_nums,
        similarities=np.asarray(page_embeddings) @ np.asarray(taxonomy_embeddings).T,
        categories=categories,
        threshold=threshold,
        model_name=ST_MODEL_ID,
    )


def _classify_with_tfidf(
    pages: dict[int, str],
    categories: list[dict[str, str]],
    threshold: float,
) -> list[dict[str, object]]:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    taxonomy_texts = [
        f"{item['label']} {item.get('description') or item['label']}" for item in categories
    ]
    page_nums = sorted(pages)
    page_texts = [pages[page_num][:2048] for page_num in page_nums]
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words="english")
    vectors = vectorizer.fit_transform([*page_texts, *taxonomy_texts])
    similarities = cosine_similarity(vectors[: len(page_texts)], vectors[len(page_texts) :])
    boosted = _apply_keyword_boost(
        np.asarray(similarities, dtype=np.float64),
        page_texts,
        categories,
    )
    return _rank_pages(
        page_nums=page_nums,
        similarities=boosted,
        categories=categories,
        threshold=min(threshold, 0.15),
        model_name="tfidf_lexical_fallback",
    )


def _apply_keyword_boost(
    similarities: NDArray[np.float64],
    page_texts: list[str],
    categories: list[dict[str, str]],
) -> NDArray[np.float64]:
    boosted = similarities.copy()
    for page_index, page_text in enumerate(page_texts):
        lower = page_text.lower()
        for category_index, category in enumerate(categories):
            label = category["label"].lower()
            description_tokens = set((category.get("description") or "").lower().split())
            if label in lower:
                boosted[page_index, category_index] += 0.35
            keyword_hits = sum(
                1 for token in description_tokens if len(token) > 4 and token in lower
            )
            keyword_hits += sum(1 for token in _category_keywords(label) if token in lower)
            if keyword_hits:
                boosted[page_index, category_index] += min(0.3, 0.08 * keyword_hits)
    return boosted


def _category_keywords(label: str) -> tuple[str, ...]:
    known = {
        "invoice": ("invoice", "amount due", "total", "bill to", "vendor", "payment"),
        "contract": (
            "agreement",
            "confidentiality",
            "termination",
            "governing law",
            "whereas",
            "party",
        ),
        "appendix": ("appendix", "exhibit", "schedule", "attachment"),
        "financial": ("balance sheet", "income statement", "cash flow", "revenue"),
        "legal": ("plaintiff", "defendant", "court", "statute", "pursuant"),
    }
    return known.get(label, ())


def _rank_pages(
    page_nums: list[int],
    similarities: NDArray[np.float64],
    categories: list[dict[str, str]],
    threshold: float,
    model_name: str,
) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for row_index, page_num in enumerate(page_nums):
        row = similarities[row_index]
        best_idx = int(np.argmax(row))
        best_score = float(row[best_idx])
        label = categories[best_idx]["label"] if best_score >= threshold else "uncertain"
        results.append(
            {
                "page_num": page_num,
                "label": label,
                "confidence": round(max(0.0, min(1.0, best_score)), 4),
                "scores": {
                    categories[index]["label"]: round(float(score), 4)
                    for index, score in enumerate(row)
                },
                "model": model_name,
            }
        )
    return results


def _get_st_model() -> object:
    global _st_model
    if _st_model is None:
        from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]

        cache_dir = os.getenv(
            "DOCUMINT_MODEL_CACHE_DIR",
            os.path.expanduser("~/.cache/documint/models"),
        )
        model_path = _cached_snapshot_path(ST_MODEL_ID, cache_dir) or ST_MODEL_ID
        local_snapshot = model_path != ST_MODEL_ID
        if local_snapshot:
            os.environ.setdefault("HF_HUB_OFFLINE", "1")
            os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        _st_model = SentenceTransformer(
            model_path,
            cache_folder=cache_dir,
            local_files_only=local_snapshot,
            config_kwargs={"local_files_only": local_snapshot},
            model_kwargs={"local_files_only": local_snapshot},
        )
        logger.info("SentenceTransformer loaded: %s", ST_MODEL_ID)
    return _st_model


def _cached_snapshot_path(model_id: str, cache_dir: str) -> str | None:
    model_cache = Path(cache_dir) / f"models--{model_id.replace('/', '--')}"
    snapshots = model_cache / "snapshots"
    if not snapshots.exists():
        return None
    candidates = [path for path in snapshots.iterdir() if path.is_dir()]
    if not candidates:
        return None
    return str(max(candidates, key=lambda path: path.stat().st_mtime))


def _normalize_taxonomy(taxonomy: list[TaxonomyInput]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for item in taxonomy:
        if isinstance(item, str):
            normalized.append({"label": item, "description": item})
            continue
        label = str(item.get("label", "")).strip()
        if not label:
            continue
        description = str(item.get("description", label)).strip() or label
        normalized.append({"label": label, "description": description})
    return normalized


def _page_text(parse_blocks: list[dict[str, object]]) -> dict[int, str]:
    pages: dict[int, list[str]] = {}
    for block in parse_blocks:
        page = int(block.get("page", 0))
        text = str(block.get("text", "")).strip()
        if text:
            pages.setdefault(page, []).append(text)
    return {page: "\n".join(parts) for page, parts in pages.items()}


def _as_score_dict(value: object) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    return {str(key): float(score) for key, score in value.items()}
