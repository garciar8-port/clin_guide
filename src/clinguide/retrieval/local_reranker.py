"""Local cross-encoder reranker using sentence-transformers (no external API)."""

import logging
import time

from clinguide.retrieval.vector_search import RetrievalHit

logger = logging.getLogger("clinguide.retrieval.local_reranker")

MODEL_NAME = "BAAI/bge-reranker-v2-m3"


class LocalReranker:
    """Rerank using a local cross-encoder model (bge-reranker-v2-m3).

    Install with: pip install "clinguide[local-reranker]"
    """

    def __init__(self, model_name: str = MODEL_NAME) -> None:
        self._model = None
        self._model_name = model_name

    def _load_model(self):
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder

                logger.info("Loading local reranker model: %s", self._model_name)
                self._model = CrossEncoder(self._model_name)
                logger.info("Local reranker model loaded")
            except ImportError as e:
                raise ImportError(
                    "sentence-transformers is required for local reranking. "
                    'Install with: pip install "clinguide[local-reranker]"'
                ) from e
        return self._model

    async def rerank(
        self,
        query: str,
        hits: list[RetrievalHit],
        top_n: int = 5,
    ) -> list[RetrievalHit]:
        """Rerank hits using the local cross-encoder model."""
        if not hits:
            return []

        model = self._load_model()

        pairs = [[query, h.text] for h in hits]

        start = time.perf_counter()
        scores = model.predict(pairs)
        latency_ms = (time.perf_counter() - start) * 1000

        logger.info(
            "Local rerank: %d docs in %.1fms (model=%s)",
            len(hits), latency_ms, self._model_name,
        )

        scored_hits = sorted(
            zip(scores, hits, strict=True),
            key=lambda x: x[0],
            reverse=True,
        )

        return [
            RetrievalHit(
                chunk_id=hit.chunk_id,
                score=float(score),
                text=hit.text,
                metadata=hit.metadata,
            )
            for score, hit in scored_hits[:top_n]
        ]

    @property
    def enabled(self) -> bool:
        return True
