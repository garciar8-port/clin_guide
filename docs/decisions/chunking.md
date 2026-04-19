# Decision: Chunking Strategy

## Context

FDA drug labels (SPL) have well-defined section structure via LOINC codes. The chunking
strategy determines how these sections are split into embedding units for retrieval.

## Options Evaluated

| Strategy | Description |
|----------|-------------|
| **Section-only** | One chunk per LOINC section. No splitting. |
| **Fixed 512** | Fixed 512-token windows with 15% overlap. Ignores section boundaries. |
| **Hybrid (chosen)** | Chunk by section; split long sections (>800 tokens) with 15% overlap. Never break mid-table. |

## Evaluation

Run `python -m clinguide.eval.chunking_experiment` after ingesting labels to produce
per-strategy stats. Then run the retrieval eval harness to compare Recall@5 and MRR.

### Expected Tradeoffs

| Metric | Section-only | Fixed 512 | Hybrid |
|--------|-------------|-----------|--------|
| Avg chunk size | Large (variable) | ~512 tokens | ~400-800 tokens |
| Context preservation | Best | Worst (splits mid-sentence) | Good |
| Retrieval precision | Lower (diluted by long chunks) | Higher (smaller targets) | Good balance |
| Table integrity | Preserved | Broken | Preserved |

## Decision

**Hybrid chunking** — section-aware splitting with overlap.

### Rationale

1. **Section boundaries are meaningful.** FDA label sections map to specific clinical
   questions (dosing, contraindications, interactions). Preserving these boundaries keeps
   chunks semantically coherent.

2. **Long sections need splitting.** Some sections (Warnings, Adverse Reactions) can be
   thousands of tokens. Without splitting, the embedding is diluted and retrieval suffers.

3. **Tables must not be split.** Dose modification tables are critical clinical content.
   Fixed-size chunking breaks table rows across chunks, destroying their meaning.

4. **Overlap prevents context loss.** 15% overlap at split boundaries ensures that
   information at the edge of a chunk is retrievable from adjacent chunks.

## Status

Chosen prior to eval — will be validated by Recall@5 comparison. If section-only
outperforms on the gold dataset, we'll revisit.
