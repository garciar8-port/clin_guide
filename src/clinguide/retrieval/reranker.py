"""Cohere reranker integration with feature flag for graceful degradation."""

import logging
import time

import cohere

from clinguide.core.config import settings
from clinguide.retrieval.vector_search import RetrievalHit

logger = logging.getLogger("clinguide.retrieval.reranker")


class CohereReranker:
    """Rerank retrieved chunks using Cohere's rerank API."""

    def __init__(self, enabled: bool = True) -> None:
        self._enabled = enabled and bool(settings.cohere_api_key)
        if self._enabled:
            self._client = cohere.Client(api_key=settings.cohere_api_key)
        else:
            self._client = None
            logger.info("Cohere reranker disabled (no API key or feature-flagged off)")

    async def rerank(
        self,
        query: str,
        hits: list[RetrievalHit],
        top_n: int = settings.rerank_top_n,
    ) -> list[RetrievalHit]:
        """Rerank hits using Cohere. Falls back to passthrough if disabled."""
        if not self._enabled or not hits:
            return hits[:top_n]

        documents = [h.text for h in hits]
        start = time.perf_counter()

        try:
            response = self._client.rerank(
                model=settings.cohere_rerank_model,
                query=query,
                documents=documents,
                top_n=top_n,
            )
        except Exception:
            logger.exception("Cohere rerank failed, falling back to passthrough")
            return hits[:top_n]

        latency_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "Cohere rerank: %d → %d docs in %.1fms",
            len(hits), len(response.results), latency_ms,
        )

        reranked: list[RetrievalHit] = []
        for result in response.results:
            original = hits[result.index]
            reranked.append(
                RetrievalHit(
                    chunk_id=original.chunk_id,
                    score=result.relevance_score,
                    text=original.text,
                    metadata=original.metadata,
                )
            )

        return reranked

    @property
    def enabled(self) -> bool:
        return self._enabled
