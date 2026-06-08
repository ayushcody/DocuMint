from __future__ import annotations

import asyncio
import io
import logging
import os
from dataclasses import dataclass

from workers.layout import NativeSpan

logger = logging.getLogger(__name__)

_olmocr_model: object | None = None
_olmocr_tokenizer: object | None = None

OLMOCR_STUB = os.getenv("DOCUMINT_OLMOCR_STUB", "false").lower() == "true"
OLMOCR_FAIL_CLOSED = os.getenv("DOCUMINT_OLMOCR_FAIL_CLOSED", "false").lower() == "true"


@dataclass(frozen=True, slots=True)
class OlmOCRResult:
    text: str
    html: str
    confidence: float
    handwriting_detected: bool
    prompt: str
    engine: str
    stub: bool
    stub_reason: str | None = None
    needs_review: bool = False


async def parse_degraded_or_handwritten_region(
    crop_bytes: bytes,
    native_spans: list[NativeSpan],
) -> OlmOCRResult:
    prompt = _anchored_prompt(native_spans)
    if OLMOCR_STUB:
        logger.warning(
            "olmOCR STUB mode active (DOCUMINT_OLMOCR_STUB=true). "
            "Returning native spans. NOT suitable for scanned docs."
        )
        return _native_span_fallback(
            native_spans,
            prompt,
            "olmocr_stub_env",
        )

    try:
        text = await asyncio.to_thread(_run_olmocr_model, crop_bytes, prompt)
        if text:
            return OlmOCRResult(
                text=text,
                html=f"<p>{_escape_html(text)}</p>",
                confidence=0.80,
                handwriting_detected=True,
                prompt=prompt,
                engine="olmOCR-7B",
                stub=False,
            )
    except Exception as exc:
        if OLMOCR_FAIL_CLOSED:
            raise RuntimeError(
                "olmOCR inference failed and DOCUMINT_OLMOCR_FAIL_CLOSED=true: "
                f"{exc}"
            ) from exc
        logger.error(
            "olmOCR inference failed: %s. Falling back to native spans. "
            "Set DOCUMINT_OLMOCR_FAIL_CLOSED=true to fail hard on olmOCR errors. "
            "This block will have low confidence and be flagged for review.",
            exc,
        )

    return _native_span_fallback(
        native_spans,
        prompt,
        "olmocr_failed_or_empty_output",
    )


def _run_olmocr_model(crop_bytes: bytes, prompt: str) -> str:
    import torch  # type: ignore[import-not-found]
    from PIL import Image

    model, tokenizer = _get_olmocr()
    image = Image.open(io.BytesIO(crop_bytes)).convert("RGB")
    try:
        inputs = tokenizer(prompt, images=image, return_tensors="pt")  # type: ignore[operator]
    except TypeError:
        logger.warning(
            "Installed olmOCR tokenizer does not accept images; running text-only prompt. "
            "Upgrade to a multimodal processor/tokenizer before production."
        )
        inputs = tokenizer(prompt, return_tensors="pt")  # type: ignore[operator]

    device = getattr(model, "device", "cpu")
    inputs = {key: value.to(device) for key, value in inputs.items()}
    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=1024,
            temperature=0.0,
            do_sample=False,
        )
    input_length = inputs["input_ids"].shape[1]
    generated = tokenizer.decode(output_ids[0][input_length:], skip_special_tokens=True)
    return str(generated).strip()


def _get_olmocr() -> tuple[object, object]:
    global _olmocr_model, _olmocr_tokenizer
    if _olmocr_model is None or _olmocr_tokenizer is None:
        from transformers import (  # type: ignore[import-not-found]
            AutoModelForCausalLM,
            AutoTokenizer,
        )

        model_id = os.getenv("DOCUMINT_OLMOCR_MODEL", "allenai/olmOCR-7B-0924-preview")
        try:
            from transformers import BitsAndBytesConfig  # type: ignore[import-not-found]

            quant_config = BitsAndBytesConfig(load_in_4bit=True)
            _olmocr_model = AutoModelForCausalLM.from_pretrained(
                model_id,
                quantization_config=quant_config,
                device_map="auto",
            )
        except Exception as exc:
            logger.warning(
                "Loading olmOCR without 4-bit quantization (%s). "
                "This may require roughly 14GB RAM.",
                exc,
            )
            _olmocr_model = AutoModelForCausalLM.from_pretrained(model_id, device_map="auto")
        _olmocr_tokenizer = AutoTokenizer.from_pretrained(model_id)
    return _olmocr_model, _olmocr_tokenizer


def _native_span_fallback(
    native_spans: list[NativeSpan],
    prompt: str,
    reason: str,
) -> OlmOCRResult:
    logger.warning("olmOCR STUB: %s", reason)
    text = " ".join(span["text"] for span in native_spans if span["text"].strip()).strip()
    return OlmOCRResult(
        text=text,
        html=f"<p>{_escape_html(text)}</p>",
        confidence=0.25 if text else 0.10,
        handwriting_detected=False,
        prompt=prompt,
        engine="olmocr_native_anchor_fallback",
        stub=True,
        stub_reason=reason,
        needs_review=True,
    )


def _anchored_prompt(native_spans: list[NativeSpan]) -> str:
    anchor_text = "\n".join(
        span.get("anchor_prompt")
        or f"Native text at bbox [{span['bbox']}]: '{span['text']}'"
        for span in native_spans
        if span.get("text", "").strip()
    )
    return (
        "<image>\n"
        f"Native PDF text in this region:\n{anchor_text}\n\n"
        "Transcribe the complete content of this document region accurately. "
        "Preserve table structure, mathematical notation, and reading order."
    )


def _escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
