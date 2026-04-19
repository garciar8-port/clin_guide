"""Hybrid retrieval: vector + BM25 with reciprocal rank fusion."""

import logging

from clinguide.core.config import settings
from clinguide.retrieval.bm25_search import BM25Index
from clinguide.retrieval.vector_search import RetrievalHit, VectorRetriever

logger = logging.getLogger("clinguide.retrieval.hybrid")


def reciprocal_rank_fusion(
    vec_hits: list[RetrievalHit],
    bm25_hits: list[RetrievalHit],
    k: int = 60,
    weight: float = 0.5,
) -> list[RetrievalHit]:
    """Fuse vector and BM25 results using reciprocal rank fusion.

    Args:
        vec_hits: Results from vector search.
        bm25_hits: Results from BM25 search.
        k: RRF constant (higher = less impact of rank differences).
        weight: Weight for vector results (1-weight for BM25).

    Returns:
        Fused results sorted by combined RRF score.
    """
    scores: dict[str, float] = {}
    hit_data: dict[str, RetrievalHit] = {}

    for rank, hit in enumerate(vec_hits):
        scores[hit.chunk_id] = scores.get(hit.chunk_id, 0) + weight / (k + rank + 1)
        hit_data[hit.chunk_id] = hit

    for rank, hit in enumerate(bm25_hits):
        scores[hit.chunk_id] = scores.get(hit.chunk_id, 0) + (1 - weight) / (k + rank + 1)
        if hit.chunk_id not in hit_data:
            hit_data[hit.chunk_id] = hit

    fused = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    return [
        RetrievalHit(
            chunk_id=chunk_id,
            score=score,
            text=hit_data[chunk_id].text,
            metadata=hit_data[chunk_id].metadata,
        )
        for chunk_id, score in fused
    ]


class HybridRetriever:
    """Combines vector and BM25 retrieval with reciprocal rank fusion."""

    def __init__(
        self,
        vector_retriever: VectorRetriever,
        bm25_index: BM25Index,
    ) -> None:
        self._vector = vector_retriever
        self._bm25 = bm25_index

    async def search(
        self,
        query: str,
        top_k: int = settings.retrieval_top_k,
        filters: dict | None = None,
    ) -> list[RetrievalHit]:
        """Run hybrid retrieval: vector + BM25 → RRF fusion."""
        # Vector search
        vec_hits = await self._vector.search(query, top_k=top_k, filters=filters)

        # BM25 search (synchronous, in-process)
        bm25_hits = self._bm25.search(query, top_k=top_k)

        # Fuse
        fused = reciprocal_rank_fusion(
            vec_hits,
            bm25_hits,
            k=settings.rrf_k,
            weight=settings.rrf_weight,
        )

        logger.info(
            "Hybrid search: %d vector + %d bm25 → %d fused",
            len(vec_hits), len(bm25_hits), len(fused),
        )

        return fused[:top_k]
