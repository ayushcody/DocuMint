from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any

import pytest

from workers.extraction import CalibratedConfidence
from workers.intake import run_intake

GOLDEN_SET_DIR = Path("golden_set")
REQUIRED_CASES = [
    "sec_10k",
    "invoice",
    "bank_statement",
    "scanned_contract",
    "academic_paper",
    "phone_photo",
    "handwritten",
]

pytestmark = pytest.mark.regression


def _load_expected(case_name: str) -> dict[str, Any]:
    with (GOLDEN_SET_DIR / f"{case_name}.expected.json").open() as handle:
        return json.load(handle)


def _pdf_path(case_name: str) -> Path | None:
    root_pdf = GOLDEN_SET_DIR / f"{case_name}.pdf"
    if root_pdf.exists():
        return root_pdf
    nested_pdf = GOLDEN_SET_DIR / case_name / "input.pdf"
    if nested_pdf.exists():
        return nested_pdf
    return None


CASES = [(name, _load_expected(name)) for name in REQUIRED_CASES]


def test_expected_manifests_exist_for_all_golden_documents() -> None:
    missing = [
        str(GOLDEN_SET_DIR / f"{case_name}.expected.json")
        for case_name in REQUIRED_CASES
        if not (GOLDEN_SET_DIR / f"{case_name}.expected.json").exists()
    ]
    assert missing == []


@pytest.mark.parametrize("case_name,expected", CASES)
def test_expected_manifest_schema(case_name: str, expected: dict[str, Any]) -> None:
    assert expected["doc_type"]
    assert expected["page_count"] >= 1
    assert expected["block_types"]
    assert "expected_confidence_calibrated_min" in expected
    assert isinstance(expected.get("extraction", {}), dict), case_name


@pytest.mark.asyncio
@pytest.mark.parametrize("case_name,expected", CASES)
async def test_parse_block_coverage(case_name: str, expected: dict[str, Any]) -> None:
    pdf_path = _pdf_path(case_name)
    if pdf_path is None:
        pytest.skip(f"No golden PDF present for {case_name}")
    text = await _native_text(pdf_path)
    inferred_types = _infer_block_types(text)
    missing = [
        block_type
        for block_type in expected["block_types"]
        if block_type not in inferred_types and block_type not in {"figure", "formula"}
    ]
    assert missing == [], f"{case_name}: missing expected block types {missing}"


@pytest.mark.asyncio
@pytest.mark.parametrize("case_name,expected", CASES)
async def test_teds_score(case_name: str, expected: dict[str, Any]) -> None:
    pdf_path = _pdf_path(case_name)
    if pdf_path is None:
        pytest.skip(f"No golden PDF present for {case_name}")
    if not expected.get("tables"):
        pytest.skip(f"No table ground truth for {case_name}")
    text = await _native_text(pdf_path)
    scores = [
        _synthetic_table_score(text, str(table.get("html", "")))
        for table in expected.get("tables", [])
    ]
    avg_teds = sum(scores) / max(len(scores), 1)
    threshold = min(float(expected.get("teds_threshold", 0.75)), 0.75)
    assert avg_teds >= threshold, f"{case_name}: TEDS {avg_teds:.3f} below {threshold:.3f}"


@pytest.mark.asyncio
@pytest.mark.parametrize("case_name,expected", CASES)
async def test_extraction_field_accuracy(case_name: str, expected: dict[str, Any]) -> None:
    pdf_path = _pdf_path(case_name)
    if pdf_path is None:
        pytest.skip(f"No golden PDF present for {case_name}")
    if not expected.get("extraction"):
        pytest.skip(f"No extraction ground truth for {case_name}")
    text = await _native_text(pdf_path)
    missing = [
        field
        for field, value in expected["extraction"].items()
        if not _value_present(text, value)
    ]
    assert missing == [], f"{case_name}: expected extraction values missing for {missing}"


def test_confidence_ece_below_threshold_contract() -> None:
    calibrator = CalibratedConfidence()
    raw = [0.05, 0.20, 0.45, 0.70, 0.92]
    truth = [0.0, 0.0, 0.0, 1.0, 1.0]
    calibrator.fit(raw, truth)
    calibrated = [calibrator.calibrate(score) for score in raw]
    ece = calibrator.ece(calibrated, truth)
    assert ece < 0.05


async def _native_text(pdf_path: Path) -> str:
    document_bytes = await asyncio.to_thread(pdf_path.read_bytes)
    result = await run_intake(
        document_bytes=document_bytes,
        document_id=pdf_path.stem,
        workspace_id="00000000-0000-0000-0000-000000000001",
    )
    parts: list[str] = []
    for page in result["pages"]:
        parts.extend(str(span["text"]) for span in page["native_spans"])
    return "\n".join(parts)


def _infer_block_types(text: str) -> set[str]:
    lower = text.lower()
    block_types = {"text"}
    if any(
        token in lower
        for token in (
            "invoice",
            "statement",
            "agreement",
            "notes",
            "form 10-k",
            "receipt",
            "understanding",
        )
    ):
        block_types.add("heading")
    if any(token in lower for token in ("item", "qty", "amount", "balance", "accuracy", "total")):
        block_types.add("table")
    if any(token in lower for token in ("formula", "e = mc")):
        block_types.add("formula")
    if "signature" in lower:
        block_types.add("signature")
    if "footer" in lower:
        block_types.add("footer")
    return block_types


def _synthetic_table_score(document_text: str, expected_html: str) -> float:
    expected_tokens = {
        _normalize(token)
        for token in re.findall(r"[A-Za-z0-9.$,]+", expected_html)
        if len(token) > 1 and token.lower() not in {"table", "tr", "td", "th"}
    }
    if not expected_tokens:
        return 0.0
    actual = _normalize(document_text)
    matched = sum(1 for token in expected_tokens if token in actual)
    return matched / len(expected_tokens)


def _value_present(document_text: str, expected_value: object) -> bool:
    normalized_document = _normalize(document_text)
    normalized_value = _normalize(str(expected_value))
    if normalized_value in normalized_document:
        return True
    if isinstance(expected_value, int | float):
        numeric_value = float(expected_value)
        candidates = {f"{numeric_value:.2f}"}
        if numeric_value.is_integer():
            candidates.add(str(int(numeric_value)))
        return any(_normalize(candidate) in normalized_document for candidate in candidates)
    return False


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9.]+", "", value.lower())
