import io

import numpy as np
import pytest
from PIL import Image

from workers import verifier


def _png(width: int, height: int) -> bytes:
    output = io.BytesIO()
    image = Image.new("RGB", (width, height), "white")
    image.paste("black", (8, 8, width // 2, 24))
    image.save(output, format="PNG")
    return output.getvalue()


@pytest.mark.asyncio
async def test_verifier_does_not_self_compare_crop_to_itself(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rng = np.random.default_rng(11)
    dummy = rng.integers(0, 255, (200, 300, 3), dtype=np.uint8)

    async def fake_render(_html: str, target_width: int = 800) -> tuple[bytes, bool]:
        return _png(target_width, 160), False

    monkeypatch.setattr(verifier, "_render_html_to_image", fake_render)
    result = await verifier.verify_parse_block(dummy, "# Test", "<h1>Test</h1>")

    assert result["score"] < 1.0
    assert result["L_verify"] > 0.0


@pytest.mark.asyncio
async def test_verifier_scores_clean_text_render_with_real_components(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    crop = np.full((120, 240, 3), 255, dtype=np.uint8)
    crop[16:28, 12:140] = 0

    async def fake_render(_html: str, target_width: int = 800) -> tuple[bytes, bool]:
        return _png(target_width, 120), False

    monkeypatch.setattr(verifier, "_render_html_to_image", fake_render)
    result = await verifier.verify_parse_block(crop, "Hello DocuMind", "<p>Hello DocuMind</p>")

    assert 0.0 <= result["score"] <= 1.0
    assert set(result["components"]) == {"ssim", "ocr_consistency", "layout_iou", "clip_sim"}
