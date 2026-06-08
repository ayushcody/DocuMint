from uuid import UUID

import numpy as np

from workers.indexing import (
    binary_quantize,
    hybrid_retrieval_score,
    maxsim_late_interaction,
    reciprocal_rank_fusion,
)


def test_maxsim_late_interaction_uses_best_patch_per_query_token() -> None:
    query = np.array([[1.0, 0.0], [0.0, 1.0]])
    document = np.array([[1.0, 0.0], [0.0, 1.0], [-1.0, 0.0]])

    score = maxsim_late_interaction(query, document)

    assert score == 2.0


def test_hybrid_retrieval_score_matches_guideline_weights() -> None:
    score = hybrid_retrieval_score(1.0, 0.5, 1.0, 0.0, 0.5)

    assert score == 0.75


def test_reciprocal_rank_fusion_combines_rankings() -> None:
    fused = reciprocal_rank_fusion([["a", "b"], ["b", "c"]], k=60)

    assert fused["b"] > fused["a"]
    assert fused["b"] > fused["c"]


def test_binary_quantization_outputs_signed_bits() -> None:
    quantized = binary_quantize(np.array([[-0.1, 0.0, 0.3]]))

    assert quantized.tolist() == [[-1, 1, 1]]


def test_qdrant_point_id_no_collision() -> None:
    from workers.indexing import _stable_page_point_id

    doc1 = UUID("00000000-0000-0000-0000-000000000001")
    doc2 = UUID("00000000-0000-0000-0000-000000000002")

    assert _stable_page_point_id(doc1, 1) != _stable_page_point_id(doc2, 1)
    assert _stable_page_point_id(doc1, 0) != _stable_page_point_id(doc1, 1)
    assert _stable_page_point_id(doc1, 5) == _stable_page_point_id(doc1, 5)

    old_collision = f"{doc1.int + 1:032x}"[-32:] == f"{doc2.int + 0:032x}"[-32:]
    new_collision = _stable_page_point_id(doc1, 1) == _stable_page_point_id(doc2, 0)
    assert old_collision
    assert not new_collision
