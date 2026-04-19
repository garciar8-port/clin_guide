"""BM25 keyword search over chunked documents."""

import logging

from rank_bm25 import BM25Okapi

from clinguide.retrieval.vector_search import RetrievalHit

logger = logging.getLogger("clinguide.retrieval.bm25")


class BM25Index:
    """In-process BM25 keyword index over chunk texts."""

    def __init__(self) -> None:
        self._index: BM25Okapi | None = None
        self._chunks: list[dict] = []  # chunk_id + metadata for each doc

    def build(self, chunks: list[dict]) -> None:
        """Build BM25 index from a list of chunk dicts with 'chunk_id', 'text', and metadata.

        Each chunk dict must have at least: chunk_id, text.
        """
        self._chunks = chunks
        tokenized = [self._tokenize(c["text"]) for c in chunks]
        self._index = BM25Okapi(tokenized)
        logger.info("Built BM25 index with %d documents", len(chunks))

    def search(self, query: str, top_k: int = 20) -> list[RetrievalHit]:
        """Search the BM25 index. Returns hits sorted by BM25 score descending."""
        if self._index is None or not self._chunks:
            return []

        tokenized_query = self._tokenize(query)
        scores = self._index.get_scores(tokenized_query)

        # Pair scores with chunks, sort descending
        scored = sorted(
            zip(scores, self._chunks, strict=False),
            key=lambda x: x[0],
            reverse=True,
        )

        results: list[RetrievalHit] = []
        for score, chunk in scored[:top_k]:
            if score <= 0:
                break
            results.append(
                RetrievalHit(
                    chunk_id=chunk["chunk_id"],
                    score=float(score),
                    text=chunk["text"],
                    metadata=chunk.get("metadata", {}),
                )
            )

        return results

    def _tokenize(self, text: str) -> list[str]:
        """Simple whitespace + lowercase tokenization."""
        return text.lower().split()

    @property
    def size(self) -> int:
        return len(self._chunks)
