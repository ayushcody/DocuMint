from workers.assembly import Block, compute_edge_weight, table_stitch_score


def test_edge_weight_same_column_continuation() -> None:
    bi = Block(id="a", bbox=(0.1, 0.1, 0.5, 0.2), text="Hello,", col_hint=0, page=0)
    bj = Block(id="b", bbox=(0.1, 0.22, 0.5, 0.32), text="world.", col_hint=0, page=0)

    weight = compute_edge_weight(bi, bj)

    assert weight < 0.3


def test_edge_weight_column_jump_penalised() -> None:
    bi = Block(id="a", bbox=(0.1, 0.1, 0.4, 0.2), text="Column 1.", col_hint=0, page=0)
    bj = Block(id="b", bbox=(0.6, 0.1, 0.9, 0.2), text="Column 2.", col_hint=1, page=0)

    weight = compute_edge_weight(bi, bj)

    assert weight >= 0.5


def test_table_stitch_score_rewards_matching_headers_and_geometry() -> None:
    score = table_stitch_score(
        Ta_header="Date Description Amount",
        Tb_header="Date Description Amount",
        Ta_col_widths=[0.2, 0.6, 0.2],
        Tb_col_widths=[0.2, 0.59, 0.21],
        text_continuation=0.9,
        has_caption_cue=True,
    )

    assert score > 0.9
