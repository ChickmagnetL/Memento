"""Tests for Reciprocal Rank Fusion."""

from core.rag.fusion import rrf_fuse


def test_rrf_combines_two_rankings():
    # Rankings are lists of keys, best first.
    fused = rrf_fuse(
        rankings={"vector": ["a", "b", "c"], "bm25": ["b", "a"]},
        weights={"vector": 0.7, "bm25": 0.3},
        k=60,
    )

    # "a": 0.7/(60+1) + 0.3/(60+2); "b": 0.7/(60+2) + 0.3/(60+1)
    # weights tip the balance toward vector's first choice.
    assert fused[0] == "a"
    assert fused[1] == "b"
    assert fused[2] == "c"


def test_rrf_item_in_single_ranking_still_scored():
    fused = rrf_fuse(
        rankings={"vector": ["a"], "bm25": []},
        weights={"vector": 0.7, "bm25": 0.3},
        k=60,
    )
    assert fused == ["a"]


def test_rrf_equal_weights_interleaves_by_rank():
    fused = rrf_fuse(
        rankings={"x": ["a", "b"], "y": ["b", "a"]},
        weights={"x": 0.5, "y": 0.5},
        k=60,
    )
    # Symmetric scores; both present, order stable (sorted by key on ties).
    assert fused == ["a", "b"]
