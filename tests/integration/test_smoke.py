"""Smoke tests — 5 seed queries against a live pipeline.

These tests require API keys and a populated Pinecone index.
Run with: pytest tests/integration/ -v -m smoke

To populate the index first:
    python -m clinguide.ingestion.pipeline osimertinib pembrolizumab metformin lisinopril warfarin
"""

import pytest
from httpx import ASGITransport, AsyncClient

from clinguide.api.app import app

pytestmark = pytest.mark.smoke

SEED_QUERIES = [
    {
        "query": "What is the recommended starting dose of osimertinib for EGFR-mutated NSCLC?",
        "expect_in_answer": ["80 mg", "once daily"],
        "expect_drug": "osimertinib",
    },
    {
        "query": "What are the contraindications for pembrolizumab?",
        "expect_in_answer": [],  # May vary
        "expect_drug": "pembrolizumab",
    },
    {
        "query": "What drug interactions should be monitored with warfarin?",
        "expect_in_answer": [],
        "expect_drug": "warfarin",
    },
    {
        "query": "What is the maximum dose of metformin for type 2 diabetes?",
        "expect_in_answer": [],
        "expect_drug": "metformin",
    },
    {
        "query": "What are the adverse reactions associated with lisinopril?",
        "expect_in_answer": [],
        "expect_drug": "lisinopril",
    },
]


@pytest.fixture
def async_client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_health(async_client):
    resp = await async_client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
@pytest.mark.parametrize("seed", SEED_QUERIES, ids=[s["expect_drug"] for s in SEED_QUERIES])
async def test_seed_query(async_client, seed):
    resp = await async_client.post("/query", json={"q": seed["query"]})
    assert resp.status_code == 200

    data = resp.json()

    # Should not be a stub response
    assert data["answer"] != "Not yet implemented."

    # If not abstaining, should have citations and a disclaimer
    if not data.get("abstained"):
        assert len(data["citations"]) > 0, f"No citations for: {seed['query']}"
        assert "drug label" in data["disclaimer"].lower() or "informational" in data["disclaimer"].lower()

        # Check expected terms appear in answer
        for term in seed["expect_in_answer"]:
            assert term.lower() in data["answer"].lower(), (
                f"Expected '{term}' in answer for: {seed['query']}"
            )
