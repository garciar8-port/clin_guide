from fastapi import APIRouter

from clinguide.core.models import QueryRequest, QueryResponse

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest) -> QueryResponse:
    # Stub — will be wired up in CRE-57/CRE-58
    return QueryResponse(
        answer="Not yet implemented.",
        citations=[],
        confidence=0.0,
        disclaimer="This is a stub response. Not for clinical use.",
        abstained=True,
        abstain_reason="not_implemented",
    )
