"""FastAPI routes for the ClinGuide query pipeline."""

import logging

from fastapi import APIRouter

from clinguide.api.conversation import SessionStore
from clinguide.core.config import settings
from clinguide.core.models import QueryRequest, QueryResponse
from clinguide.core.tracing import new_trace
from clinguide.generation.classifier import QueryClassifier
from clinguide.generation.generator import Generator
from clinguide.generation.grounding import GroundingChecker, compute_confidence
from clinguide.retrieval.bm25_search import BM25Index
from clinguide.retrieval.embedder import Embedder
from clinguide.retrieval.hybrid import HybridRetriever
from clinguide.retrieval.query_expansion import QueryExpander
from clinguide.retrieval.reranker import CohereReranker
from clinguide.retrieval.vector_search import VectorRetriever

logger = logging.getLogger("clinguide.api")

router = APIRouter()

# Singletons initialized on first use
_embedder: Embedder | None = None
_vector_retriever: VectorRetriever | None = None
_hybrid_retriever: HybridRetriever | None = None
_bm25_index: BM25Index | None = None
_reranker: CohereReranker | None = None
_classifier: QueryClassifier | None = None
_generator: Generator | None = None
_grounding: GroundingChecker | None = None
_expander: QueryExpander | None = None
_sessions: SessionStore | None = None

ABSTAIN_RESPONSE = (
    "I don't have enough information in the available drug labels to answer this."
)


def _get_embedder() -> Embedder:
    global _embedder
    if _embedder is None:
        _embedder = Embedder()
    return _embedder


def _get_vector_retriever() -> VectorRetriever:
    global _vector_retriever
    if _vector_retriever is None:
        _vector_retriever = VectorRetriever(_get_embedder())
    return _vector_retriever


def _get_bm25_index() -> BM25Index:
    global _bm25_index
    if _bm25_index is None:
        _bm25_index = BM25Index()
    return _bm25_index


def _get_hybrid_retriever() -> HybridRetriever:
    global _hybrid_retriever
    if _hybrid_retriever is None:
        _hybrid_retriever = HybridRetriever(
            _get_vector_retriever(), _get_bm25_index()
        )
    return _hybrid_retriever


def _get_reranker() -> CohereReranker:
    global _reranker
    if _reranker is None:
        _reranker = CohereReranker()
    return _reranker


def _get_classifier() -> QueryClassifier:
    global _classifier
    if _classifier is None:
        _classifier = QueryClassifier()
    return _classifier


def _get_generator() -> Generator:
    global _generator
    if _generator is None:
        _generator = Generator()
    return _generator


def _get_grounding() -> GroundingChecker:
    global _grounding
    if _grounding is None:
        _grounding = GroundingChecker()
    return _grounding


def _get_expander() -> QueryExpander:
    global _expander
    if _expander is None:
        _expander = QueryExpander()
    return _expander


def _get_sessions() -> SessionStore:
    global _sessions
    if _sessions is None:
        _sessions = SessionStore()
    return _sessions


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest) -> QueryResponse:
    trace = new_trace(query=req.q)

    # Multi-turn: enrich query with conversation context
    effective_query = req.q
    session = None
    if req.session_id:
        session = _get_sessions().get_or_create(req.session_id)
        if session.messages:
            effective_query = session.format_contextual_query(req.q)
            trace.start_span("multi_turn", turns=len(session.messages))
            trace.end_span(enriched=True)

    # 1. Classify query
    trace.start_span("classify_query")
    classification = await _get_classifier().classify(req.q)
    trace.end_span(verdict=classification)

    if classification == "non_clinical":
        return _abstain_response("non_clinical", trace)
    if classification == "unsafe":
        return _abstain_response("unsafe", trace)

    # 2. Query expansion (use effective_query for multi-turn context)
    trace.start_span("expand_query")
    expanded_q = _get_expander().expand(effective_query)
    trace.end_span(original=effective_query, expanded=expanded_q)

    # 3. Hybrid retrieval (vector + BM25 + RRF)
    trace.start_span("hybrid_retrieval", top_k=settings.retrieval_top_k)
    hits = await _get_hybrid_retriever().search(
        query=expanded_q,
        top_k=settings.retrieval_top_k,
        filters=req.filters,
    )
    trace.end_span(
        num_results=len(hits),
        top_score=hits[0].score if hits else 0.0,
    )

    # 4. Rerank
    trace.start_span("rerank", enabled=_get_reranker().enabled)
    reranked = await _get_reranker().rerank(
        query=req.q,  # Use original query for reranking, not expanded
        hits=hits,
        top_n=settings.rerank_top_n,
    )
    trace.end_span(
        num_results=len(reranked),
        top_score=reranked[0].score if reranked else 0.0,
    )

    # 5. Abstention gate
    if not reranked or reranked[0].score < settings.abstain_threshold:
        return _abstain_response("low_confidence", trace)

    # 6. Generate
    trace.start_span("generate", model=settings.claude_model, num_chunks=len(reranked))
    response = await _get_generator().generate(query=req.q, chunks=reranked)
    trace.end_span(
        confidence=response.confidence,
        num_citations=len(response.citations),
    )

    # 7. Grounding check (fail-closed)
    trace.start_span("grounding_check")
    grounding = await _get_grounding().check(
        answer=response.answer,
        citations=response.citations,
        chunks=reranked,
    )
    trace.end_span(
        ok=grounding.ok,
        score=grounding.score,
        failed_claims=len(grounding.failed_claims),
    )

    if not grounding.ok:
        logger.warning(
            "Grounding check failed: %d ungrounded claims",
            len(grounding.failed_claims),
        )
        return _abstain_response("ungrounded", trace)

    # Update confidence with grounding signal
    response.confidence = compute_confidence(
        reranker_top_score=reranked[0].score,
        grounding=grounding,
    )

    # Save to conversation history
    if session:
        session.add_user_message(req.q)
        session.add_assistant_message(response.answer)

    logger.info("trace=%s %s", trace.trace_id, trace.to_dict())
    return response


def _abstain_response(reason: str, trace) -> QueryResponse:
    trace.start_span("abstain")
    trace.end_span(reason=reason)
    logger.info("Abstaining (%s): trace=%s %s", reason, trace.trace_id, trace.to_dict())
    return QueryResponse(
        answer=ABSTAIN_RESPONSE,
        citations=[],
        confidence=0.0,
        disclaimer=f"Query classified as {reason}. No answer generated.",
        abstained=True,
        abstain_reason=reason,
    )


@router.get("/chunks/{chunk_id}")
async def get_chunk(chunk_id: str) -> dict:
    """Fetch a chunk's full text for the source viewer."""
    index = _get_embedder()._get_index()
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
