"""Embedding generation and Pinecone upsert."""

import asyncio

from openai import AsyncOpenAI
from pinecone import Pinecone, ServerlessSpec

from clinguide.core.config import settings
from clinguide.core.models import Chunk


class Embedder:
    """Generate embeddings via OpenAI and manage Pinecone index."""

    def __init__(self) -> None:
        self._openai = AsyncOpenAI(api_key=settings.openai_api_key)
        self._pinecone = Pinecone(api_key=settings.pinecone_api_key)
        self._index = None

    def _get_index(self):
        if self._index is None:
            self._ensure_index_exists()
            self._index = self._pinecone.Index(settings.pinecone_index)
        return self._index

    def _ensure_index_exists(self) -> None:
        existing = [idx.name for idx in self._pinecone.list_indexes()]
        if settings.pinecone_index not in existing:
            self._pinecone.create_index(
                name=settings.pinecone_index,
                dimension=settings.embedding_dimensions,
                metric="cosine",
                spec=ServerlessSpec(
                    cloud=settings.pinecone_cloud,
                    region=settings.pinecone_region,
                ),
            )

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts."""
        # OpenAI allows up to 2048 texts per batch, but we'll chunk at 100
        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), 100):
            batch = texts[i : i + 100]
            response = await self._openai.embeddings.create(
                model=settings.embedding_model,
                input=batch,
            )
            all_embeddings.extend([d.embedding for d in response.data])
        return all_embeddings

    async def embed_query(self, query: str) -> list[float]:
        """Embed a single query string."""
        result = await self.embed_texts([query])
        return result[0]

    async def upsert_chunks(self, chunks: list[Chunk]) -> int:
        """Embed and upsert chunks to Pinecone. Returns count of upserted vectors."""
        if not chunks:
            return 0

        texts = [c.text for c in chunks]
        embeddings = await self.embed_texts(texts)
        index = self._get_index()

        vectors = []
        for chunk, embedding in zip(chunks, embeddings):
            metadata = {
                "drug_name": chunk.drug_name,
                "drug_generic": chunk.drug_generic,
                "section_name": chunk.section_name,
                "loinc_code": chunk.loinc_code,
                "set_id": chunk.set_id,
                "version_id": chunk.version_id,
                "text": chunk.text[:40000],  # Pinecone metadata limit
            }
            if chunk.drug_class:
                metadata["drug_class"] = chunk.drug_class
            if chunk.approval_date:
                metadata["approval_date"] = chunk.approval_date.isoformat()

            vectors.append({
                "id": chunk.chunk_id,
                "values": embedding,
                "metadata": metadata,
            })

        # Upsert in batches of 100
        upserted = 0
        for i in range(0, len(vectors), 100):
            batch = vectors[i : i + 100]
            index.upsert(vectors=batch)
            upserted += len(batch)

        return upserted

    async def query_similar(
        self, query_embedding: list[float], top_k: int = 20, filters: dict | None = None
    ) -> list[dict]:
        """Query Pinecone for similar chunks."""
        index = self._get_index()

        query_params: dict = {
            "vector": query_embedding,
            "top_k": top_k,
            "include_metadata": True,
        }
        if filters:
            query_params["filter"] = filters

        results = index.query(**query_params)

        return [
            {
                "chunk_id": match.id,
                "score": match.score,
                "metadata": match.metadata,
            }
            for match in results.matches
        ]
