from __future__ import annotations

from dataclasses import dataclass, replace
from math import sqrt


@dataclass(frozen=True, slots=True)
class Block:
    id: str
    bbox: tuple[float, float, float, float]
    text: str
    col_hint: int
    page: int


@dataclass(frozen=True, slots=True)
class ContentBlock:
    block_id: str
    page: int
    type: str
    bbox: dict[str, float | str]
    text: str
    html: str
    confidence_raw: float
    confidence_calibrated: float
    source: dict[str, object]
    reading_order_rank: int = 0
    children: tuple[str, ...] = ()
    citations: tuple[dict[str, object], ...] = ()


def assemble_blocks(blocks: list[ContentBlock]) -> list[ContentBlock]:
    if not blocks:
        return []
    ordered = _decode_reading_order(blocks)
    merged = _merge_truncated_paragraphs(ordered)
    stitched = _stitch_mult_page_tables(merged)
    return [
        replace(block, reading_order_rank=rank)
        for rank, block in enumerate(stitched)
    ]


def compute_edge_weight(
    bi: Block,
    bj: Block,
    alpha: float = 0.4,
    beta: float = 0.3,
    gamma: float = 0.3,
) -> float:
    """
    W(i,j) = alpha*d_spatial(i,j) + beta*d_semantic(i,j) + gamma*P_col(i,j).

    Lower weight means block j is more likely to follow block i in reading order.
    """
    d_spatial = _spatial_distance(bi.bbox, bj.bbox)
    d_semantic = _semantic_distance(bi.text, bj.text)
    p_col = 0.0 if bi.col_hint == bj.col_hint else 0.8
    return alpha * d_spatial + beta * d_semantic + gamma * p_col


def table_stitch_score(
    Ta_header: str,
    Tb_header: str,
    Ta_col_widths: list[float],
    Tb_col_widths: list[float],
    text_continuation: float,
    has_caption_cue: bool,
    alpha: float = 0.4,
    beta: float = 0.3,
    gamma: float = 0.2,
    delta: float = 0.1,
) -> float:
    header_sim = 1.0 if Ta_header.strip() == Tb_header.strip() else 0.0
    if len(Ta_col_widths) == len(Tb_col_widths):
        col_diffs = [abs(a - b) for a, b in zip(Ta_col_widths, Tb_col_widths, strict=True)]
        col_geom_sim = 1.0 - min(1.0, sum(col_diffs) / max(sum(Ta_col_widths), 1.0))
    else:
        col_geom_sim = 0.0
    caption_cue = 1.0 if has_caption_cue else 0.0
    return (
        alpha * header_sim
        + beta * col_geom_sim
        + gamma * text_continuation
        + delta * caption_cue
    )


def reading_order(blocks: list[Block]) -> list[Block]:
    return sorted(
        blocks,
        key=lambda block: (block.page, block.col_hint, block.bbox[1], block.bbox[0]),
    )


def _decode_reading_order(blocks: list[ContentBlock]) -> list[ContentBlock]:
    sortable = [
        Block(
            id=block.block_id,
            bbox=_tuple_bbox(block.bbox),
            text=block.text,
            col_hint=_column_hint(block.bbox),
            page=block.page,
        )
        for block in blocks
    ]
    by_id = {block.block_id: block for block in blocks}
    graph = _candidate_successor_graph(sortable)
    ordered_ids = _topological_sort(graph, sortable)
    return [by_id[block_id] for block_id in ordered_ids]


def _candidate_successor_graph(blocks: list[Block]) -> dict[str, set[str]]:
    graph = {block.id: set() for block in blocks}
    for current in blocks:
        candidates = [
            other
            for other in blocks
            if other.id != current.id and _is_after(current, other)
        ]
        if not candidates:
            continue
        best = min(candidates, key=lambda other: compute_edge_weight(current, other))
        graph[current.id].add(best.id)
    return graph


def _topological_sort(graph: dict[str, set[str]], blocks: list[Block]) -> list[str]:
    indegree = {block.id: 0 for block in blocks}
    for successors in graph.values():
        for successor in successors:
            indegree[successor] += 1

    rank_hint = {block.id: index for index, block in enumerate(reading_order(blocks))}
    queue = sorted(
        [block_id for block_id, degree in indegree.items() if degree == 0],
        key=lambda block_id: rank_hint[block_id],
    )
    ordered: list[str] = []
    while queue:
        block_id = queue.pop(0)
        ordered.append(block_id)
        for successor in sorted(graph[block_id], key=lambda item: rank_hint[item]):
            indegree[successor] -= 1
            if indegree[successor] == 0:
                queue.append(successor)
                queue.sort(key=lambda item: rank_hint[item])

    if len(ordered) != len(blocks):
        return [block.id for block in reading_order(blocks)]
    return ordered


def _merge_truncated_paragraphs(blocks: list[ContentBlock]) -> list[ContentBlock]:
    merged: list[ContentBlock] = []
    skip_next = False
    for index, block in enumerate(blocks):
        if skip_next:
            skip_next = False
            continue
        if index + 1 >= len(blocks):
            merged.append(block)
            continue
        next_block = blocks[index + 1]
        if _should_merge_paragraphs(block, next_block):
            text = f"{block.text.rstrip('-')} {next_block.text.lstrip()}".strip()
            html = f"<p>{_escape_html(text)}</p>"
            merged.append(
                replace(
                    block,
                    text=text,
                    html=html,
                    children=block.children + (next_block.block_id,),
                    citations=block.citations + next_block.citations,
                )
            )
            skip_next = True
        else:
            merged.append(block)
    return merged


def _stitch_mult_page_tables(blocks: list[ContentBlock]) -> list[ContentBlock]:
    stitched: list[ContentBlock] = []
    for block in blocks:
        if stitched and _should_stitch_tables(stitched[-1], block):
            previous = stitched[-1]
            stitched[-1] = replace(
                previous,
                text=f"{previous.text}\n{block.text}".strip(),
                html=f"{previous.html}{block.html}",
                children=previous.children + (block.block_id,),
                citations=previous.citations + block.citations,
            )
        else:
            stitched.append(block)
    return stitched


def _should_merge_paragraphs(left: ContentBlock, right: ContentBlock) -> bool:
    if left.type != "paragraph" or right.type != "paragraph":
        return False
    if right.page not in {left.page, left.page + 1}:
        return False
    same_column = _column_hint(left.bbox) == _column_hint(right.bbox)
    return same_column and _semantic_distance(left.text, right.text) == 0.0


def _should_stitch_tables(left: ContentBlock, right: ContentBlock) -> bool:
    if left.type != "table" or right.type != "table" or right.page != left.page + 1:
        return False
    score = table_stitch_score(
        Ta_header=_first_line(left.text),
        Tb_header=_first_line(right.text),
        Ta_col_widths=[float(left.bbox["w"])],
        Tb_col_widths=[float(right.bbox["w"])],
        text_continuation=0.8 if right.text else 0.0,
        has_caption_cue="continued" in right.text.lower(),
    )
    return score > 0.7


def _is_after(left: Block, right: Block) -> bool:
    if right.page != left.page:
        return right.page > left.page
    if right.col_hint != left.col_hint:
        return right.col_hint > left.col_hint and right.bbox[1] >= left.bbox[1] - 0.08
    return right.bbox[1] > left.bbox[1] or (
        abs(right.bbox[1] - left.bbox[1]) < 0.02 and right.bbox[0] > left.bbox[0]
    )


def _spatial_distance(
    left: tuple[float, float, float, float],
    right: tuple[float, float, float, float],
) -> float:
    left_cx = (left[0] + left[2]) / 2
    left_cy = (left[1] + left[3]) / 2
    right_cx = (right[0] + right[2]) / 2
    right_cy = (right[1] + right[3]) / 2
    return min(1.0, sqrt((right_cx - left_cx) ** 2 + (right_cy - left_cy) ** 2))


def _semantic_distance(left_text: str, right_text: str) -> float:
    ends_incomplete = left_text.rstrip().endswith(("-", ",", ";"))
    starts_lower = right_text.lstrip()[0].islower() if right_text.strip() else False
    return 0.0 if ends_incomplete and starts_lower else 0.2


def _column_hint(bbox: dict[str, float | str]) -> int:
    center_x = float(bbox["x"]) + float(bbox["w"]) / 2
    if center_x < 0.38:
        return 0
    if center_x > 0.62:
        return 1
    return 0


def _tuple_bbox(bbox: dict[str, float | str]) -> tuple[float, float, float, float]:
    x = float(bbox["x"])
    y = float(bbox["y"])
    return (x, y, x + float(bbox["w"]), y + float(bbox["h"]))


def _first_line(text: str) -> str:
    return text.strip().splitlines()[0] if text.strip() else ""


def _escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
