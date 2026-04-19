# ClinGuide

**Clinical Guidelines RAG Assistant** — retrieval-augmented generation over FDA drug labels for clinical decision support.

A clinician types a natural language question, the system retrieves relevant sections from FDA drug labels via hybrid search, generates an evidence-backed answer with inline citations, and validates every claim against the source text.

## Architecture

```
                         QUERY PIPELINE

  User Query
      │
      ▼
  ┌─────────────────┐
  │ Query Classifier │  Claude Haiku
  │ clinical/unsafe/ │  (non-clinical → abstain)
  │ non_clinical     │
  └────────┬────────┘
           │
      ▼
  ┌─────────────────┐
  │ Query Expansion  │  Brand→generic synonym dictionary
  └────────┬────────┘
           │
      ▼
  ┌─────────────────────────────────┐
  │       Hybrid Retrieval          │
  │  ┌──────────┐  ┌─────────────┐ │
  │  │ Vector   │  │ BM25        │ │
  │  │ Search   │  │ Keyword     │ │
  │  │(Pinecone)│  │ (rank_bm25) │ │
  │  └────┬─────┘  └──────┬──────┘ │
  │       └───────┬────────┘        │
  │        Reciprocal Rank Fusion   │
  └────────────────┬────────────────┘
                   │
      ▼
  ┌─────────────────┐
  │ Cohere Reranker  │  rerank-english-v3.0
  │ (feature-flagged)│
  └────────┬────────┘
           │
      ▼
  ┌─────────────────┐
  │ Abstention Gate  │  top-1 score < threshold → abstain
  └────────┬────────┘
           │
      ▼
  ┌─────────────────┐
  │ Claude Sonnet    │  Answer with [^n] citations
  │ Generation       │
  └────────┬────────┘
           │
      ▼
  ┌─────────────────┐
  │ Grounding Check  │  Claim-extract-and-verify (fail-closed)
  └────────┬────────┘
           │
      ▼
  Response: answer + citations + confidence + disclaimer
```

```
                      DATA INGESTION

  DailyMed API ──▶ SPL Parser ──▶ Chunker ──▶ Embedder ──▶ Pinecone
  (FDA labels)     (LOINC        (section-    (text-emb      ↕
                    sections)     aware +      -3-small)   BM25 Index
                                  tables)
```

## Quick Start

```bash
# Clone and install
git clone https://github.com/garciar8-port/clin_guide.git
cd clin_guide
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,ui]"

# Configure
cp .env.example .env
# Fill in API keys: ANTHROPIC, OPENAI, PINECONE, COHERE

# Ingest drug labels
python -m clinguide.ingestion.pipeline osimertinib pembrolizumab metformin lisinopril warfarin

# Start the API
uvicorn clinguide.api.app:app --port 8000

# Start the UI (separate terminal)
streamlit run ui/app.py

# Query
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"q": "What is the recommended starting dose of osimertinib for EGFR-mutated NSCLC?"}'
```

### Docker Compose

```bash
cp .env.example .env  # fill in keys
docker compose up
# API: http://localhost:8000
# UI:  http://localhost:8501
```

## Project Structure

```
src/clinguide/
├── api/                 # FastAPI endpoints
│   ├── app.py           # App factory, CORS, lifespan
│   ├── routes.py        # POST /query, GET /chunks/{id}, GET /health
│   └── streaming.py     # POST /query/stream (SSE)
├── core/
│   ├── config.py        # Pydantic Settings, pinned model IDs
│   ├── models.py        # Chunk, LabelDocument, QueryResponse, SECTION_CODES
│   └── tracing.py       # Per-stage latency + attribute logging
├── ingestion/
│   ├── dailymed_client.py  # Async DailyMed SPL API client
│   ├── spl_parser.py       # SPL XML → LabelDocument (LOINC sections + tables)
│   ├── chunker.py          # Section-aware chunking with overlap
│   ├── synonyms.py         # Brand/generic synonym dictionary
│   ├── pipeline.py         # End-to-end ingest CLI
│   └── freshness.py        # Version detection + re-ingest
├── retrieval/
│   ├── embedder.py         # OpenAI embeddings + Pinecone upsert/query
│   ├── vector_search.py    # Vector similarity retrieval
│   ├── bm25_search.py      # BM25 keyword index
│   ├── hybrid.py           # Reciprocal rank fusion (vector + BM25)
│   ├── reranker.py         # Cohere reranker (feature-flagged)
│   └── query_expansion.py  # Synonym-based query expansion
├── generation/
│   ├── generator.py        # Claude Sonnet with citation prompt
│   ├── classifier.py       # Clinical query classifier (Haiku)
│   └── grounding.py        # Citation grounding check (fail-closed)
└── eval/
    ├── harness.py              # Eval metrics + failure-mode classification
    ├── chunking_experiment.py  # 3-strategy comparison framework
    └── embedding_benchmark.py  # Embedding model benchmarking
```

## Key RAG Decisions

| Decision | Choice | Rationale | Doc |
|----------|--------|-----------|-----|
| **Chunking** | Section-aware + overlap | Preserves FDA section semantics, never breaks tables | [chunking.md](docs/decisions/chunking.md) |
| **Embedding** | text-embedding-3-small | Best cost/quality for MVP; Bedrock Titan planned | [embedding-model.md](docs/decisions/embedding-model.md) |
| **Retrieval** | Hybrid (vector + BM25 + RRF) | Drug names are exact-match terms vectors miss | — |
| **Reranker** | Cohere rerank-english-v3.0 | Feature-flagged; degrades gracefully to hybrid-only | — |
| **Grounding** | Claim-extract-and-verify | Fail-closed: ungrounded claims → abstention | — |
| **Abstention** | 3-layer | Classifier → retrieval confidence → grounding check | — |

## Evaluation

- **40 gold cases**: 30 happy-path Q&A pairs + 10 adversarial (injection, misspelling, non-clinical, negation)
- **Retrieval metrics**: Precision@k, Recall@k, MRR with failure-mode breakdown
- **Generation metrics**: Answer coverage, citation rate, abstention accuracy
- **CI gating**: GitHub Actions runs unit tests + eval thresholds on every PR

```bash
# Run unit tests
pytest tests/unit/ -v

# Run eval harness (requires API keys + populated index)
pytest tests/integration/ -v -m smoke
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI (Python 3.12, async) |
| Vector DB | Pinecone (serverless) |
| BM25 | rank_bm25 (in-process) |
| Embeddings | OpenAI text-embedding-3-small |
| LLM | Claude Sonnet (generation), Claude Haiku (classifier/grounding) |
| Reranker | Cohere rerank-english-v3.0 |
| Data source | DailyMed API (FDA drug labels, SPL XML) |
| Frontend | Streamlit |
| CI | GitHub Actions |
| Infra | Docker Compose |

## Performance Targets

See [docs/targets.md](docs/targets.md) for SLOs covering latency, cost, retrieval quality, generation quality, and safety.

## License

MIT
