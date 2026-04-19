# Decision: Cost-Tier Routing

## Context

The ClinGuide pipeline uses Claude for multiple stages: query classification,
answer generation, and citation grounding verification. Not all stages need the
same model capability, so routing tasks to the appropriate model tier reduces
cost without sacrificing quality where it matters.

## Routing Strategy

| Pipeline Stage | Model | Why |
|----------------|-------|-----|
| **Query Classification** | Claude Haiku | Simple classification (clinical/non_clinical/unsafe). Haiku handles this well at ~10x lower cost. |
| **Answer Generation** | Claude Sonnet | Core output quality — needs strong reasoning, citation formatting, clinical accuracy. |
| **Grounding Verification** | Claude Haiku | Binary entailment judgments per claim. Structured task, doesn't need Sonnet-level reasoning. |

## Cost Impact

| Scenario | Model | Input Tokens (est.) | Output Tokens (est.) | Cost/query |
|----------|-------|--------------------|--------------------|-----------|
| Classify | Haiku | ~200 | ~20 | $0.0002 |
| Generate | Sonnet | ~3000 | ~500 | $0.0135 |
| Ground (3 claims) | Haiku | ~1500 | ~150 | $0.0013 |
| **Total** | | | | **~$0.015** |

vs. all-Sonnet:

| Scenario | Model | Cost/query |
|----------|-------|-----------|
| All Sonnet | Sonnet | ~$0.035 |

**Savings: ~57% per query** from tiered routing.

## Configuration

Model IDs are pinned in `src/clinguide/core/config.py`:

```python
claude_model = "claude-sonnet-4-20250514"              # generation
claude_classifier_model = "claude-haiku-4-5-20251001"   # classification + grounding
```

## Quality Guardrails

- If Haiku classification accuracy drops below 95% on the eval set, upgrade to Sonnet
- If Haiku grounding check produces >5% false positives (ungrounded claims passing),
  upgrade to Sonnet
- Monitor both via the eval harness failure-mode breakdown

## Status

Implemented. Classification and grounding use Haiku; generation uses Sonnet.
Cost savings validated by architecture, pending production measurement.
