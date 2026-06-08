from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_classify_invoice_vs_contract() -> None:
    from workers.classify_worker import classify_document

    blocks = [
        {
            "page": 0,
            "type": "text",
            "reading_order_rank": 0,
            "text": (
                "INVOICE No: INV-912371. Bill To: Acme Corp. "
                "Total Amount Due: $4,250.00. Payment due Net 30."
            ),
        },
    ]
    taxonomy = [
        {"label": "invoice", "description": "Financial document requesting payment"},
        {"label": "contract", "description": "Legal agreement between parties"},
        {"label": "scientific_paper", "description": "Academic research publication"},
    ]

    results = await classify_document(blocks, taxonomy)

    assert results, "No results returned"
    assert results[0]["label"] == "invoice"
    assert float(results[0]["confidence"]) > 0.25


@pytest.mark.asyncio
async def test_split_detects_section_boundary() -> None:
    from workers.split_worker import split_document

    blocks = [
        {
            "page": 0,
            "type": "text",
            "reading_order_rank": 0,
            "text": "Invoice No INV-001. Bill to customer. Total $500. Payment Net 30.",
        },
        {
            "page": 1,
            "type": "text",
            "reading_order_rank": 10,
            "text": "Invoice No INV-001. Line items: product A qty 5 price $100.",
        },
        {
            "page": 2,
            "type": "heading",
            "reading_order_rank": 20,
            "text": "LEGAL AGREEMENT. This agreement entered into by undersigned parties.",
        },
        {
            "page": 3,
            "type": "text",
            "reading_order_rank": 30,
            "text": (
                "Section 1 Obligations. Section 2 Payment. Section 3 Termination. "
                "Governing law: State of California."
            ),
        },
    ]

    segments = await split_document(blocks, {"min_segment_pages": 1})

    assert segments, "No segments returned"
    assert len(segments) >= 2
    assert segments[0]["label"] == "invoice"


@pytest.mark.asyncio
async def test_classify_uncertain_threshold() -> None:
    from workers.classify_worker import classify_document

    blocks = [
        {
            "page": 0,
            "type": "text",
            "reading_order_rank": 0,
            "text": "xxxxxxx yyyyyyy zzzzzzz",
        },
    ]
    taxonomy = [
        {"label": "invoice", "description": "Financial payment document"},
        {"label": "contract", "description": "Legal agreement"},
    ]

    results = await classify_document(blocks, taxonomy)

    assert results[0]["label"] == "uncertain" or float(results[0]["confidence"]) < 0.4
