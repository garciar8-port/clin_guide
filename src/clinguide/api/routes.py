"""FastAPI routes for the ClinGuide query pipeline."""

import logging

from fastapi import APIRouter

from clinguide.core.config import settings
from clinguide.core.models import QueryRequest, QueryResponse
from clinguide.core.tracing import new_trace
from clinguide.generation.generator import Generator
from clinguide.retrieval.embedder import Embedder
from clinguide.retrieval.vector_search import VectorRetriever

logger = logging.getLogger("clinguide.api")

router = APIRouter()

# Singletons initialized on first use
_embedder: Embedder | None = None
_retriever: VectorRetriever | None = None
_generator: Generator | None = None


def _get_retriever() -> VectorRetriever:
    global _embedder, _retriever
    if _retriever is None:
        _embedder = Embedder()
        _retriever = VectorRetriever(_embedder)
    return _retriever


def _get_generator() -> Generator:
    global _generator
    if _generator is None:
        _generator = Generator()
    return _generator


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest) -> QueryResponse:
    trace = new_trace(query=req.q)
    retriever = _get_retriever()
    generator = _get_generator()

    # 1. Retrieve
    trace.start_span("vector_search", top_k=settings.rerank_top_n)
    hits = await retriever.search(
        query=req.q,
        top_k=settings.rerank_top_n,
        filters=req.filters,
    )
    trace.end_span(
        num_results=len(hits),
        top_score=hits[0].score if hits else 0.0,
    )

    # 2. Abstention check
    if not hits or hits[0].score < settings.abstain_threshold:
        trace.start_span("abstain")
        trace.end_span(reason="low_confidence")
        logger.info("trace=%s %s", trace.trace_id, trace.to_dict())
        return QueryResponse(
            answer="I don't have enough information in the available drug labels to answer this.",
            citations=[],
            confidence=0.0,
            disclaimer="No sufficiently relevant drug label sections were found.",
            abstained=True,
            abstain_reason="low_confidence",
        )

    # 3. Generate
    trace.start_span("generate", model=settings.claude_model, num_chunks=len(hits))
    response = await generator.generate(query=req.q, chunks=hits)
    trace.end_span(
        confidence=response.confidence,
        num_citations=len(response.citations),
    )

    logger.info("trace=%s %s", trace.trace_id, trace.to_dict())
    return response


@router.get("/chunks/{chunk_id}")
async def get_chunk(chunk_id: str) -> dict:
    """Fetch a chunk's full text for the source viewer."""
    embedder = _get_retriever()._embedder
    index = embedder._get_index()
    result = index.fetch(ids=[chunk_id])

    vectors = result.get("vectors", {})
    if chunk_id not in vectors:
        return {"error": "Chunk not found", "chunk_id": chunk_id}

    vec = vectors[chunk_id]
    return {
        "chunk_id": chunk_id,
        "text": vec.metadata.get("text", ""),
        "metadata": dict(vec.metadata),
    }
