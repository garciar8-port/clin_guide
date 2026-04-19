"""Tests for BM25 search."""

from clinguide.retrieval.bm25_search import BM25Index


class TestBM25Index:
    def _build_index(self):
        idx = BM25Index()
        idx.build([
            {"chunk_id": "c1", "text": "osimertinib 80 mg once daily for NSCLC EGFR mutation"},
            {"chunk_id": "c2", "text": "pembrolizumab 200 mg IV every 3 weeks for melanoma"},
            {"chunk_id": "c3", "text": "metformin 500 mg twice daily for type 2 diabetes"},
            {"chunk_id": "c4", "text": "warfarin anticoagulant INR monitoring bleeding risk"},
            {"chunk_id": "c5", "text": "lisinopril ACE inhibitor hypertension heart failure"},
        ])
        return idx

    def test_build_and_size(self):
        idx = self._build_index()
        assert idx.size == 5

    def test_search_returns_relevant(self):
        idx = self._build_index()
        results = idx.search("osimertinib EGFR", top_k=3)
        assert len(results) > 0
        assert results[0].chunk_id == "c1"

    def test_search_scores_positive(self):
        idx = self._build_index()
        results = idx.search("metformin diabetes", top_k=2)
        assert all(r.score > 0 for r in results)

    def test_search_empty_index(self):
        idx = BM25Index()
        results = idx.search("anything", top_k=5)
        assert results == []

    def test_top_k_limits(self):
        idx = self._build_index()
        results = idx.search("drug", top_k=2)
        assert len(results) <= 2
