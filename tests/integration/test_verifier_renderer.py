from __future__ import annotations

import io

import pytest
from PIL import Image

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_html_renderer_returns_valid_image_bytes() -> None:
    from workers.verifier import _render_html_to_image

    html = (
        "<table><tr><th>Item</th><th>Amount</th></tr>"
        "<tr><td>Tax</td><td>$10</td></tr></table>"
    )
    rendered, degraded = await _render_html_to_image(html, target_width=600)

    assert degraded is False
    assert rendered
    assert len(rendered) > 500
    image = Image.open(io.BytesIO(rendered))
    assert image.size[0] > 0
    assert image.size[1] > 0


@pytest.mark.asyncio
async def test_verifier_ssim_differentiates_good_vs_bad() -> None:
    from workers.verifier import _align_sizes, _compute_ssim, _render_html_to_image

    good_html = "<table><tr><td>Invoice #</td><td>INV-001</td></tr></table>"
    bad_html = "<p>Xxxxxxxx xxxxxxx xxxxxxxx xxxxxxxxx</p>"

    good_render, good_degraded = await _render_html_to_image(good_html)
    bad_render, bad_degraded = await _render_html_to_image(bad_html)
    assert good_degraded is False
    assert bad_degraded is False
    original, aligned_good = _align_sizes(good_render, good_render)
    _, aligned_bad = _align_sizes(good_render, bad_render)

    good_ssim = _compute_ssim(original, aligned_good)
    bad_ssim = _compute_ssim(original, aligned_bad)

    assert good_ssim > bad_ssim, f"good={good_ssim:.4f} bad={bad_ssim:.4f}"
