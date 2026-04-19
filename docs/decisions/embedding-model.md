# Decision: Embedding Model

## Context

ClinGuide needs an embedding model for vectorizing drug label chunks and queries.
The choice affects retrieval quality, latency, cost, and AWS alignment.

## Options Evaluated

| Model | Dimensions | Provider | Cost (per 1M tokens) |
|-------|-----------|----------|---------------------|
| **text-embedding-3-small** | 1536 | OpenAI | $0.02 |
| **text-embedding-3-large** | 3072 | OpenAI | $0.13 |
| **Titan Text Embeddings V2** | 1024 | AWS Bedrock | $0.02 |

## Evaluation Plan

Run `python -m clinguide.eval.embedding_benchmark` after ingesting labels:
1. Embed the full corpus with each model
2. Run retrieval eval (Recall@5, MRR) on the gold dataset
3. Measure p50/p95 embed latency per query
4. Compute $/query at current corpus size

Results written to `eval/results/embedding_benchmark.json` and summarized below.

## Decision

**OpenAI text-embedding-3-small** (initial choice).

### Rationale

1. **Quality**: Strong performance on medical/clinical text at 1536 dimensions.
2. **Cost**: $0.02/1M tokens — cheapest tier.
3. **Latency**: Fast API with batch support.
4. **Simplicity**: Single API key, no AWS infra needed for MVP.

### Bedrock Titan — planned post-MVP

Titan V2 is the natural upgrade path for AWS alignment (knownwell runs on AWS).
The benchmark framework is built and ready to run once Bedrock access is configured.
If Titan matches or exceeds OpenAI quality on the gold dataset, we re-index and switch.

## Status

OpenAI chosen for MVP. Bedrock benchmark is a Phase 3 stretch goal —
framework is built, awaiting AWS credentials.
