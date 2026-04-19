"""Server-Sent Events (SSE) streaming endpoint for generation."""

import json
import logging
from collections.abc import AsyncGenerator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from clinguide.core.config import settings
from clinguide.core.models import QueryRequest
from clinguide.generation.classifier import QueryClassifier
from clinguide.retrieval.embedder import Embedder
from clinguide.retrieval.hybrid import HybridRetriever
from clinguide.retrieval.bm25_search import BM25Index
from clinguide.retrieval.query_expansion import QueryExpander
from clinguide.retrieval.reranker import CohereReranker
from clinguide.retrieval.vector_search import VectorRetriever

from anthropic import AsyncAnthropic

logger = logging.getLogger("clinguide.api.streaming")

stream_router = APIRouter()


async def _stream_generate(
    query: str,
    chunks: list[dict],
) -> AsyncGenerator[str, None]:
    """Stream Claude's response token by token via SSE."""
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    system = (
        "You are a clinical information assistant. Answer ONLY from the provided "
        "source passages. Cite every factual claim using [^n] markers mapped to the "
        "source chunks. If the sources do not contain the answer, respond: "
        '"I don\'t have enough information in the available drug labels to answer this." '
        "Never invent drug names, doses, or indications."
    )

    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        drug = chunk.get("drug_name", "Unknown")
        section = chunk.get("section_name", "Unknown")
        text = chunk.get("text", "")
        context_parts.append(f"[^{i}] Drug: {drug} | Section: {section}\n{text}")

    user_msg = f"Question: {query}\n\nSource passages:\n" + "\n---\n".join(context_parts)

    # Send retrieval metadata first
    yield _sse_event("retrieval", {"chunks": len(chunks)})

    # Stream generation
    async with client.messages.stream(
        model=settings.claude_model,
        max_tokens=2048,
        system=system,
        messages=[{"role": "user", "content": user_msg}],
    ) as stream:
        async for text in stream.text_stream:
            yield _sse_event("token", {"text": text})

    # Signal completion
    yield _sse_event("done", {"disclaimer": "Not for clinical use. Verify against current prescribing information."})


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@stream_router.post("/query/stream")
async def stream_query(req: QueryRequest) -> StreamingResponse:
    """Streaming query endpoint — returns SSE with token-by-token generation."""
    # Classify
    classifier = QueryClassifier()
    classification = await classifier.classify(req.q)

    if classification in ("non_clinical", "unsafe"):
        async def abstain_stream() -> AsyncGenerator[str, None]:
            yield _sse_event("abstain", {"reason": classification})

        return StreamingResponse(abstain_stream(), media_type="text/event-stream")

    # Expand + retrieve + rerank
    expander = QueryExpander()
    expanded = expander.expand(req.q)

    embedder = Embedder()
    vector_retriever = VectorRetriever(embedder)
    bm25 = BM25Index()
    hybrid = HybridRetriever(vector_retriever, bm25)

    hits = await hybrid.search(expanded, top_k=settings.retrieval_top_k)

    reranker = CohereReranker()
    reranked = await reranker.rerank(req.q, hits, top_n=settings.rerank_top_n)

    if not reranked or reranked[0].score < settings.abstain_threshold:
        async def low_conf_stream() -> AsyncGenerator[str, None]:
            yield _sse_event("abstain", {"reason": "low_confidence"})

        return StreamingResponse(low_conf_stream(), media_type="text/event-stream")

    # Build chunk data for generation
    chunk_data = [
        {
            "text": h.text,
            "drug_name": h.metadata.get("drug_name", ""),
            "section_name": h.metadata.get("section_name", ""),
        }
        for h in reranked
    ]

    return StreamingResponse(
        _stream_generate(req.q, chunk_data),
        media_type="text/event-stream",
    )
