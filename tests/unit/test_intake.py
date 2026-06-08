import pytest

from workers.intake import run_intake


@pytest.mark.asyncio
async def test_run_intake_rasterizes_pdf_and_normalizes_native_spans() -> None:
    import fitz  # type: ignore[import-not-found]

    doc = fitz.open()
    page = doc.new_page(width=200, height=100)
    page.insert_text((20, 30), "Hello DocuMind", fontsize=12)
    pdf_bytes = doc.tobytes()
    doc.close()

    result = await run_intake(pdf_bytes, "doc_1", "workspace_1")

    assert result["page_count"] == 1
    assert result["file_hash_sha256"]
    page_result = result["pages"][0]
    assert page_result["page_num"] == 0
    assert page_result["dpi"] == 300
    assert page_result["render_bytes"].startswith(b"\x89PNG")
    assert page_result["native_spans"]

    span = page_result["native_spans"][0]
    bbox = span["bbox"]
    assert bbox["coord_space"] == "page_norm"
    assert 0.0 <= float(bbox["x"]) <= 1.0
    assert 0.0 <= float(bbox["y"]) <= 1.0
    assert 0.0 < float(bbox["w"]) <= 1.0
    assert 0.0 < float(bbox["h"]) <= 1.0
    assert "Native text at bbox" in span["anchor_prompt"]
    assert "Hello DocuMind" in page_result["anchor_text"]
