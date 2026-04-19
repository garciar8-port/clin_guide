"""Tests for hybrid retrieval (RRF)."""

from clinguide.retrieval.hybrid import reciprocal_rank_fusion
from clinguide.retrieval.vector_search import RetrievalHit


def _hit(chunk_id: str, score: float) -> RetrievalHit:
    return RetrievalHit(chunk_id=chunk_id, score=score, text="", metadata={})


class TestRRF:
    def test_fuses_results(self):
        vec = [_hit("a", 0.9), _hit("b", 0.8), _hit("c", 0.7)]
        bm25 = [_hit("b", 5.0), _hit("d", 4.0), _hit("a", 3.0)]

        fused = reciprocal_rank_fusion(vec, bm25, k=60, weight=0.5)

        ids = [h.chunk_id for h in fused]
        # "b" appears in both, should rank high
        assert "b" in ids[:2]
        # All unique chunks present
        assert set(ids) == {"a", "b", "c", "d"}

    def test_weight_bias_vector(self):
        vec = [_hit("a", 0.9)]
        bm25 = [_hit("b", 5.0)]

        fused = reciprocal_rank_fusion(vec, bm25, k=60, weight=0.9)
        # With weight=0.9, vector result "a" should score higher
        assert fused[0].chunk_id == "a"

    def test_weight_bias_bm25(self):
        vec = [_hit("a", 0.9)]
        bm25 = [_hit("b", 5.0)]

        fused = reciprocal_rank_fusion(vec, bm25, k=60, weight=0.1)
        # With weight=0.1, BM25 result "b" should score higher
        assert fused[0].chunk_id == "b"

    def test_empty_inputs(self):
        fused = reciprocal_rank_fusion([], [], k=60, weight=0.5)
        assert fused == []

    def test_single_source(self):
        vec = [_hit("a", 0.9), _hit("b", 0.8)]
        fused = reciprocal_rank_fusion(vec, [], k=60, weight=0.5)
        assert len(fused) == 2
        assert fused[0].chunk_id == "a"
