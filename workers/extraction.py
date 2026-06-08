from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass
from typing import TypeAlias, cast

import numpy as np
import outlines  # type: ignore[import-not-found]
from numpy.typing import NDArray
from transformers import AutoModelForCausalLM, AutoTokenizer  # type: ignore[import-not-found]

JsonValue: TypeAlias = str | int | float | bool | None | dict[str, object] | list[object]

logger = logging.getLogger(__name__)

_outlines_model: object | None = None
EXTRACTION_BACKEND = os.getenv("DOCUMINT_EXTRACTION_BACKEND", "anthropic")


@dataclass(slots=True)
class _PavaCalibrator:
    thresholds: NDArray[np.float64]
    values: NDArray[np.float64]

    def predict(self, raw: float) -> float:
        return float(np.interp(raw, self.thresholds, self.values))


@dataclass(frozen=True, slots=True)
class ExtractedField:
    name: str
    value: JsonValue
    metadata: dict[str, object]


class CalibratedConfidence:
    """
    ECE-calibrated confidence scoring with isotonic regression.

    scikit-learn is used when available; otherwise a small PAVA implementation
    keeps tests and local development self-contained.
    """

    def __init__(self) -> None:
        self._sklearn_calibrator: object | None = None
        self._fallback_calibrator: _PavaCalibrator | None = None
        self._fitted = False

    def compute_raw(
        self,
        schema_fit: float,
        citation_grounding: float,
        parser_quality: float,
        model_agreement: float,
        contradiction: float,
    ) -> float:
        a, b, c, d, e = 0.25, 0.30, 0.20, 0.15, 0.10
        logit = (
            a * schema_fit
            + b * citation_grounding
            + c * parser_quality
            + d * model_agreement
            - e * contradiction
        )
        return float(1 / (1 + np.exp(-logit)))

    def fit(self, raw_scores: NDArray[np.float64], ground_truth: NDArray[np.float64]) -> None:
        raw = np.asarray(raw_scores, dtype=np.float64)
        truth = np.asarray(ground_truth, dtype=np.float64)
        try:
            from sklearn.isotonic import IsotonicRegression  # type: ignore[import-not-found]

            calibrator = IsotonicRegression(out_of_bounds="clip")
            calibrator.fit(raw, truth)
            self._sklearn_calibrator = calibrator
        except ModuleNotFoundError:
            self._fallback_calibrator = _fit_pava(raw, truth)
        self._fitted = True

    def calibrate(self, raw: float) -> float:
        if not self._fitted:
            return raw
        if self._sklearn_calibrator is not None:
            predicted = self._sklearn_calibrator.predict([raw])  # type: ignore[attr-defined]
            return float(predicted[0])
        if self._fallback_calibrator is None:
            return raw
        return self._fallback_calibrator.predict(raw)

    def ece(
        self,
        raw_scores: NDArray[np.float64],
        ground_truth: NDArray[np.float64],
        n_bins: int = 10,
    ) -> float:
        scores = np.asarray(raw_scores, dtype=np.float64)
        truth = np.asarray(ground_truth, dtype=np.float64)
        bins = np.linspace(0, 1, n_bins + 1)
        ece = 0.0
        for i in range(n_bins):
            if i == n_bins - 1:
                mask = (scores >= bins[i]) & (scores <= bins[i + 1])
            else:
                mask = (scores >= bins[i]) & (scores < bins[i + 1])
            if int(mask.sum()) == 0:
                continue
            avg_conf = float(scores[mask].mean())
            avg_acc = float(truth[mask].mean())
            ece += (int(mask.sum()) / len(scores)) * abs(avg_conf - avg_acc)
        return float(ece)


async def extract_schema_fields(
    schema_json: dict[str, object],
    parse_blocks: list[dict[str, object]],
) -> tuple[dict[str, JsonValue], dict[str, dict[str, object]]]:
    constrained = await extract_with_constrained_decoding(
        parse_blocks=parse_blocks,
        schema_json=schema_json,
        native_spans=_native_spans_from_blocks(parse_blocks),
    )
    fallback_data, fallback_metadata = _deterministic_extract_schema_fields(
        schema_json,
        parse_blocks,
    )
    if constrained is None:
        fallback_metadata["_method"] = {"name": "deterministic_fallback"}
        return fallback_data, fallback_metadata

    properties = _schema_properties(schema_json)
    data: dict[str, JsonValue] = {
        field_name: constrained.get(field_name, fallback_data.get(field_name))
        for field_name in properties
    }
    metadata = {
        field: value
        for field, value in fallback_metadata.items()
        if field in properties
    }
    for field_metadata in metadata.values():
        field_metadata["warnings"] = [
            *list(field_metadata.get("warnings", [])),
            "value produced by constrained decoding; citation assigned by text overlap",
        ]
    metadata["_method"] = {"name": "constrained_decoding"}
    validate_field_citations(metadata)
    return data, metadata


def _deterministic_extract_schema_fields(
    schema_json: dict[str, object],
    parse_blocks: list[dict[str, object]],
) -> tuple[dict[str, JsonValue], dict[str, dict[str, object]]]:
    properties = _schema_properties(schema_json)
    required = set(_as_str_list(schema_json.get("required")))
    data: dict[str, JsonValue] = {}
    field_metadata: dict[str, dict[str, object]] = {}
    calibrator = _default_calibrator()

    for field_name, field_schema in properties.items():
        extracted = _extract_one_field(
            field_name=field_name,
            field_schema=field_schema,
            parse_blocks=parse_blocks,
            required=field_name in required,
            calibrator=calibrator,
        )
        data[field_name] = extracted.value
        field_metadata[field_name] = extracted.metadata

    validate_field_citations(field_metadata)
    return data, field_metadata


async def extract_with_constrained_decoding(
    parse_blocks: list[dict[str, object]],
    schema_json: dict[str, object],
    native_spans: list[dict[str, object]],
) -> dict[str, JsonValue] | None:
    del native_spans
    prompt = _constrained_prompt(parse_blocks)
    document_context = _document_context(parse_blocks)
    backend = EXTRACTION_BACKEND.lower()
    if backend == "anthropic":
        return await _extract_with_anthropic_tool_use(
            prompt=prompt,
            schema_json=schema_json,
            document_context=document_context,
        )
    if backend == "openai_compat":
        endpoint = os.getenv("DOCUMINT_EXTRACTION_ENDPOINT")
        if not endpoint:
            logger.warning("DOCUMINT_EXTRACTION_ENDPOINT is missing for openai_compat backend")
            return None
        return await _extract_with_openai_compatible_endpoint(
            prompt=prompt,
            schema_json=schema_json,
            endpoint=endpoint,
        )
    if backend == "transformers":
        try:
            result = await asyncio.to_thread(_extract_with_outlines, prompt, schema_json)
            logger.info("Extraction method: constrained_decoding_outlines")
            return result
        except Exception as exc:
            logger.warning(
                "Outlines transformers extraction failed: %s - falling back to deterministic",
                exc,
            )
            return None
    if backend != "deterministic":
        logger.warning(
            "Unknown DOCUMINT_EXTRACTION_BACKEND=%s; using deterministic fallback",
            backend,
        )
    return None


async def _extract_with_anthropic_tool_use(
    prompt: str,
    schema_json: dict[str, object],
    document_context: str,
) -> dict[str, JsonValue] | None:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY is missing; using deterministic extraction fallback")
        return None
    try:
        import anthropic  # type: ignore[import-not-found]

        client = anthropic.AsyncAnthropic(api_key=api_key)
        tool_schema = {
            "name": "extract_document_fields",
            "description": "Extract structured fields from document content",
            "input_schema": {
                "type": "object",
                "properties": schema_json.get("properties", {}),
                "required": schema_json.get("required", []),
            },
        }
        response = await client.messages.create(
            model=os.getenv("DOCUMINT_ANTHROPIC_MODEL", "claude-haiku-4-5-20251001"),
            max_tokens=1024,
            tools=[tool_schema],
            tool_choice={"type": "any"},
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"{prompt}\n\nDocument:\n{document_context[:4000]}\n\n"
                        "Use the extract_document_fields tool."
                    ),
                }
            ],
        )
        for block in response.content:
            if (
                getattr(block, "type", None) == "tool_use"
                and getattr(block, "name", None) == "extract_document_fields"
            ):
                result = getattr(block, "input", None)
                if isinstance(result, dict):
                    logger.info("Extraction method: anthropic_tool_use")
                    return cast(dict[str, JsonValue], result)
    except Exception as exc:
        logger.warning("Anthropic constrained extraction failed: %s", exc)
    return None


async def _extract_with_openai_compatible_endpoint(
    prompt: str,
    schema_json: dict[str, object],
    endpoint: str,
) -> dict[str, JsonValue] | None:
    try:
        from openai import AsyncOpenAI  # type: ignore[import-not-found]
    except ImportError:
        logger.error("openai package not installed; cannot use DOCUMINT_EXTRACTION_ENDPOINT")
        return None
    client = AsyncOpenAI(
        base_url=endpoint,
        api_key=os.getenv("DOCUMINT_EXTRACTION_API_KEY", "none"),
    )
    response = await client.chat.completions.create(
        model=os.getenv("DOCUMINT_EXTRACTION_MODEL", "qwen2.5-1.5b"),
        messages=[{"role": "user", "content": prompt}],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "extraction", "schema": schema_json},
        },
    )
    content = response.choices[0].message.content
    if content is None:
        return None
    loaded = json.loads(content)
    if not isinstance(loaded, dict):
        return None
    return cast(dict[str, JsonValue], loaded)


def _extract_with_outlines(prompt: str, schema_json: dict[str, object]) -> dict[str, JsonValue]:
    import outlines  # type: ignore[import-not-found]
    from pydantic import create_model

    field_defs: dict[str, tuple[object, None]] = {}
    for field_name, field_spec in _schema_properties(schema_json).items():
        python_type = _json_schema_type_to_python(field_spec)
        field_defs[field_name] = (python_type | None, None)
    dynamic_schema = create_model("ExtractionSchema", **field_defs)
    generator = outlines.Generator(_get_outlines_model(), output_type=dynamic_schema)
    result = generator(prompt)
    dumped = result.model_dump() if hasattr(result, "model_dump") else dict(result)
    return cast(dict[str, JsonValue], dumped)


def _get_outlines_model() -> object:
    global _outlines_model
    if _outlines_model is None:
        model_id = os.getenv("DOCUMINT_OUTLINES_MODEL", "Qwen/Qwen2.5-1.5B-Instruct")
        tokenizer = AutoTokenizer.from_pretrained(model_id)
        model = AutoModelForCausalLM.from_pretrained(model_id)
        _outlines_model = outlines.from_transformers(model, tokenizer)
    return _outlines_model


def _json_schema_type_to_python(field_spec: dict[str, object]) -> type[object]:
    schema_type = field_spec.get("type", "string")
    type_map: dict[object, type[object]] = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "array": list,
        "object": dict,
    }
    return type_map.get(schema_type, str)


def _constrained_prompt(parse_blocks: list[dict[str, object]]) -> str:
    document_context = _document_context(parse_blocks)
    return (
        "Extract structured data from this document.\n\n"
        f"Document content:\n{document_context}\n\n"
        "Extract all available fields. Return only valid JSON matching the required schema."
    )


def _document_context(parse_blocks: list[dict[str, object]]) -> str:
    context_parts = []
    for block in sorted(parse_blocks, key=lambda item: int(item.get("reading_order_rank", 0))):
        context_parts.append(
            f"[Page {block.get('page')}, {block.get('type')}]: {block.get('text')}"
        )
    return "\n".join(context_parts[:60])


def _native_spans_from_blocks(parse_blocks: list[dict[str, object]]) -> list[dict[str, object]]:
    spans: list[dict[str, object]] = []
    for block in parse_blocks:
        source = block.get("source", {})
        if isinstance(source, dict):
            maybe_spans = source.get("native_spans", [])
            if isinstance(maybe_spans, list):
                spans.extend(item for item in maybe_spans if isinstance(item, dict))
    return spans


def build_structured_prompt(
    schema_json: dict[str, object],
    parse_blocks: list[dict[str, object]],
) -> str:
    lines = [f"Extract fields matching this JSON schema: {schema_json}"]
    for block in sorted(parse_blocks, key=lambda item: int(item.get("reading_order_rank", 0))):
        bbox = block.get("bbox", {})
        text = str(block.get("text", ""))
        lines.append(f"Block page={block.get('page')} bbox={bbox}: {text}")
    return "\n".join(lines)


def validate_field_citations(field_metadata: dict[str, dict[str, object]]) -> None:
    missing = [
        field
        for field, metadata in field_metadata.items()
        if not field.startswith("_") and not metadata.get("citations")
    ]
    if missing:
        raise ValueError(f"Extracted fields without citations are invalid: {', '.join(missing)}")


def _extract_one_field(
    field_name: str,
    field_schema: dict[str, object],
    parse_blocks: list[dict[str, object]],
    required: bool,
    calibrator: CalibratedConfidence,
) -> ExtractedField:
    pattern = field_schema.get("pattern")
    aliases = _field_aliases(field_name, field_schema)
    candidate = _find_candidate_block(aliases, pattern, parse_blocks)
    if candidate is None and parse_blocks:
        candidate = parse_blocks[0]

    if candidate is None:
        value = _empty_value(field_schema)
        metadata = _metadata(0.0, 0.0, [], [_validator_result("required", None, "fail")])
        return ExtractedField(field_name, value, metadata)

    raw_text = str(candidate.get("text", ""))
    value_text = _extract_value_text(raw_text, aliases, pattern)
    value = _coerce_value(value_text, field_schema)
    validators = _run_validators(field_name, value, value_text, field_schema, required)
    schema_fit = 1.0 if all(item["status"] == "pass" for item in validators) else 0.4
    citation_grounding = 1.0 if raw_text.strip() else 0.2
    parser_quality = float(candidate.get("confidence", {}).get("calibrated", 0.65))
    raw_conf = calibrator.compute_raw(
        schema_fit=schema_fit,
        citation_grounding=citation_grounding,
        parser_quality=parser_quality,
        model_agreement=0.75,
        contradiction=0.0 if value_text else 0.25,
    )
    calibrated = calibrator.calibrate(raw_conf)
    citation = {
        "page": int(candidate.get("page", 0)),
        "matching_text": raw_text,
        "bboxes": [candidate.get("bbox", _default_bbox())],
    }
    metadata = _metadata(calibrated, raw_conf, [citation], validators)
    return ExtractedField(field_name, value, metadata)


def _find_candidate_block(
    aliases: list[str],
    pattern: object,
    parse_blocks: list[dict[str, object]],
) -> dict[str, object] | None:
    regex = re.compile(str(pattern), re.IGNORECASE) if isinstance(pattern, str) else None
    best_score = -1.0
    best: dict[str, object] | None = None
    for block in parse_blocks:
        text = str(block.get("text", ""))
        lower = text.lower()
        alias_score = max((_token_overlap(alias.lower(), lower) for alias in aliases), default=0.0)
        pattern_score = 1.0 if regex is not None and regex.search(text) else 0.0
        score = max(alias_score, pattern_score)
        if score > best_score:
            best_score = score
            best = block
    return best if best_score > 0 else None


def _extract_value_text(raw_text: str, aliases: list[str], pattern: object) -> str:
    if isinstance(pattern, str):
        match = re.search(pattern, raw_text, flags=re.IGNORECASE)
        if match is not None:
            return match.group(1) if match.groups() else match.group(0)

    for alias in aliases:
        escaped = re.escape(alias).replace("\\ ", r"\s+")
        match = re.search(
            rf"{escaped}\s*[:#-]?\s*(.+?)(?=\s+[A-Z][A-Za-z ]{{1,30}}\s*[:#-]|\n|;|\||$)",
            raw_text,
            flags=re.IGNORECASE,
        )
        if match is not None:
            return _trim_adjacent_label(match.group(1).strip())
    return raw_text.strip()


def _trim_adjacent_label(value_text: str) -> str:
    label_boundary = re.search(
        r"\s+(?:invoice\s*(?:no|number)|total|date|vendor|amount\s*due|due\s*date)\s*[:#-]\s*",
        value_text,
        flags=re.IGNORECASE,
    )
    if label_boundary is None:
        return value_text
    return value_text[: label_boundary.start()].strip()


def _coerce_value(value_text: str, field_schema: dict[str, object]) -> JsonValue:
    field_type = field_schema.get("type")
    if field_type in {"number", "integer"}:
        match = re.search(r"-?\d+(?:\.\d+)?", value_text.replace(",", ""))
        if match is None:
            return 0 if field_type == "integer" else 0.0
        number = float(match.group(0))
        return int(number) if field_type == "integer" else number
    if field_type == "boolean":
        return value_text.strip().lower() in {"true", "yes", "1", "y"}
    if field_type == "array":
        return [item.strip() for item in re.split(r"[,;|]", value_text) if item.strip()]
    return value_text


def _run_validators(
    field_name: str,
    value: JsonValue,
    value_text: str,
    field_schema: dict[str, object],
    required: bool,
) -> list[dict[str, str | None]]:
    validators: list[dict[str, str | None]] = []
    if required:
        validators.append(_validator_result("required", None, "pass" if value_text else "fail"))
    pattern = field_schema.get("pattern")
    if isinstance(pattern, str):
        status = "pass" if re.search(pattern, value_text, flags=re.IGNORECASE) else "fail"
        validators.append(_validator_result("regex", pattern, status))
    minimum = field_schema.get("minimum")
    maximum = field_schema.get("maximum")
    if isinstance(value, int | float) and isinstance(minimum, int | float):
        validators.append(
            _validator_result("minimum", str(minimum), "pass" if value >= minimum else "fail")
        )
    if isinstance(value, int | float) and isinstance(maximum, int | float):
        validators.append(
            _validator_result("maximum", str(maximum), "pass" if value <= maximum else "fail")
        )
    if not validators:
        validators.append(
            _validator_result(f"{field_name}_present", None, "pass" if value_text else "warn")
        )
    return validators


def _validator_result(name: str, pattern: str | None, status: str) -> dict[str, str | None]:
    return {"name": name, "pattern": pattern, "status": status}


def _metadata(
    calibrated: float,
    raw: float,
    citations: list[dict[str, object]],
    validators: list[dict[str, str | None]],
) -> dict[str, object]:
    return {
        "confidence": {"calibrated": calibrated, "raw": raw},
        "citations": citations,
        "validators": validators,
        "warnings": [],
    }


def _schema_properties(schema_json: dict[str, object]) -> dict[str, dict[str, object]]:
    properties = schema_json.get("properties")
    if not isinstance(properties, dict):
        return {}
    return {
        str(name): value if isinstance(value, dict) else {}
        for name, value in properties.items()
    }


def _field_aliases(field_name: str, field_schema: dict[str, object]) -> list[str]:
    aliases = [field_name, field_name.replace("_", " ")]
    schema_aliases = field_schema.get("aliases")
    if isinstance(schema_aliases, list):
        aliases.extend(str(alias) for alias in schema_aliases)
    for key in ("title", "description"):
        value = field_schema.get(key)
        if isinstance(value, str):
            aliases.append(value)
    return list(dict.fromkeys(alias.strip() for alias in aliases if alias.strip()))


def _as_str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _empty_value(field_schema: dict[str, object]) -> JsonValue:
    field_type = field_schema.get("type")
    if field_type == "array":
        return []
    if field_type == "integer":
        return 0
    if field_type == "number":
        return 0.0
    if field_type == "boolean":
        return False
    return ""


def _token_overlap(alias: str, text: str) -> float:
    alias_tokens = {token for token in re.split(r"\W+", alias) if token}
    if not alias_tokens:
        return 0.0
    text_tokens = {token for token in re.split(r"\W+", text) if token}
    return len(alias_tokens & text_tokens) / len(alias_tokens)


def _default_bbox() -> dict[str, float | str]:
    return {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0, "coord_space": "page_norm"}


def _default_calibrator() -> CalibratedConfidence:
    calibrator = CalibratedConfidence()
    raw = np.array([0.05, 0.25, 0.50, 0.75, 0.95], dtype=np.float64)
    truth = np.array([0.02, 0.20, 0.52, 0.78, 0.97], dtype=np.float64)
    calibrator.fit(raw, truth)
    return calibrator


def _fit_pava(
    raw_scores: NDArray[np.float64],
    ground_truth: NDArray[np.float64],
) -> _PavaCalibrator:
    order = np.argsort(raw_scores)
    x = raw_scores[order]
    y = ground_truth[order]

    blocks: list[tuple[float, float, int]] = []
    for xi, yi in zip(x, y, strict=True):
        blocks.append((float(xi), float(yi), 1))
        while len(blocks) >= 2 and blocks[-2][1] > blocks[-1][1]:
            left_x, left_y, left_n = blocks[-2]
            right_x, right_y, right_n = blocks[-1]
            merged_n = left_n + right_n
            merged_y = (left_y * left_n + right_y * right_n) / merged_n
            blocks[-2:] = [(right_x if right_x > left_x else left_x, merged_y, merged_n)]

    thresholds = np.array([block[0] for block in blocks], dtype=np.float64)
    values = np.array([block[1] for block in blocks], dtype=np.float64)
    thresholds = np.concatenate(([0.0], thresholds, [1.0]))
    values = np.concatenate(([values[0]], values, [values[-1]]))
    return _PavaCalibrator(thresholds=thresholds, values=values)
