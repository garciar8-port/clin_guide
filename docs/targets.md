# ClinGuide — Performance & Quality Targets

Service-level objectives for the ClinGuide query pipeline.

## Latency

| Metric | Target | Notes |
|--------|--------|-------|
| End-to-end p50 | < 3s | Embed + retrieve + generate |
| End-to-end p95 | < 8s | Includes cold-start and reranker |
| Retrieval p95 | < 500ms | Vector search + BM25 + RRF |
| Generation p95 | < 6s | Claude Sonnet response |

## Cost

| Metric | Target |
|--------|--------|
| Cost per query | < $0.05 |
| Embedding cost per 1k chunks | < $0.02 |
| Monthly budget (dev) | < $50 |

## Retrieval Quality

| Metric | Floor | Target |
|--------|-------|--------|
| Recall@5 | 0.80 | 0.90 |
| Precision@5 | 0.60 | 0.75 |
| MRR | 0.70 | 0.85 |

## Generation Quality

| Metric | Floor | Target |
|--------|-------|--------|
| Faithfulness | 0.90 | 0.95 |
| Citation accuracy | 0.90 | 0.95 |
| Answer relevance | 0.80 | 0.90 |

## Safety

| Metric | Target |
|--------|--------|
| Abstention rate (in-scope queries) | < 15% |
| Abstention rate (out-of-scope) | > 95% |
| Grounding failure rate | < 5% |
| Undetected hallucination rate | < 2% |

## Freshness

| Metric | Target |
|--------|--------|
| Max label staleness | < 7 days |
| Re-index latency (per label) | < 60s |

---

These targets are initial estimates and will be adjusted based on evaluation results.
Thresholds used for CI gating are documented in `.github/workflows/ci.yml`.
