"""Vector search retrieval — wraps embedder for the query pipeline."""

from dataclasses import dataclass

from clinguide.core.config import settings
from clinguide.retrieval.embedder import Embedder


@dataclass
class RetrievalHit:
    chunk_id: str
    score: float
    text: str
    metadata: dict


class VectorRetriever:
    """Retrieve relevant chunks via vector similarity search."""

    def __init__(self, embedder: Embedder) -> None:
        self._embedder = embedder

    async def search(
        self,
        query: str,
        top_k: int = settings.retrieval_top_k,
        filters: dict | None = None,
    ) -> list[RetrievalHit]:
        """Embed query and retrieve top-k similar chunks from Pinecone."""
        query_embedding = await self._embedder.embed_query(query)
        results = await self._embedder.query_similar(
            query_embedding, top_k=top_k, filters=filters
        )

        return [
            RetrievalHit(
                chunk_id=r["chunk_id"],
                score=r["score"],
                text=r["metadata"].get("text", ""),
                metadata=r["metadata"],
            )
            for r in results
        ]
