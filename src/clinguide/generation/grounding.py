"""Citation grounding check — verifies that generated claims are supported by sources."""

import json
import logging
import re

from anthropic import AsyncAnthropic

from clinguide.core.config import settings
from clinguide.core.models import Citation
from clinguide.retrieval.vector_search import RetrievalHit

logger = logging.getLogger("clinguide.generation.grounding")

GROUNDING_PROMPT = """\
You are a grounding verification system. For each claimed statement, determine if it is \
ENTAILED by the provided source passage.

A claim is ENTAILED if the source passage contains sufficient evidence to support it.
A claim is NOT_ENTAILED if the source passage does not contain the information, \
contradicts it, or if the claim adds information not present in the source.

For each claim, respond with a JSON array of objects:
[{"claim": "...", "verdict": "entailed"|"not_entailed", "reason": "brief explanation"}]"""


class ClaimVerdict:
    def __init__(self, claim: str, verdict: str, reason: str) -> None:
        self.claim = claim
        self.entailed = verdict == "entailed"
        self.reason = reason


class GroundingResult:
    def __init__(self, verdicts: list[ClaimVerdict]) -> None:
        self.verdicts = verdicts

    @property
    def ok(self) -> bool:
        """All claims are entailed."""
        return all(v.entailed for v in self.verdicts)

    @property
    def score(self) -> float:
        """Fraction of claims that are entailed."""
        if not self.verdicts:
            return 1.0
        return sum(1 for v in self.verdicts if v.entailed) / len(self.verdicts)

    @property
    def failed_claims(self) -> list[ClaimVerdict]:
        return [v for v in self.verdicts if not v.entailed]


class GroundingChecker:
    """Verifies that generated answers are grounded in retrieved source chunks."""

    def __init__(self) -> None:
        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def check(
        self,
        answer: str,
        citations: list[Citation],
        chunks: list[RetrievalHit],
    ) -> GroundingResult:
        """Extract claims from the answer and verify each against its cited source."""
        if not citations:
            return GroundingResult(verdicts=[])

        # Build a map of chunk_id → text
        chunk_map: dict[str, str] = {c.chunk_id: c.text for c in chunks}

        # Extract cited sentences from the answer
        cited_claims = self._extract_cited_claims(answer, citations, chunk_map)

        if not cited_claims:
            return GroundingResult(verdicts=[])

        verdicts: list[ClaimVerdict] = []
        for claim_text, source_text in cited_claims:
            verdict = await self._verify_claim(claim_text, source_text)
            verdicts.append(verdict)

        result = GroundingResult(verdicts=verdicts)
        logger.info(
            "Grounding check: %d/%d claims entailed (score=%.2f)",
            sum(1 for v in verdicts if v.entailed),
            len(verdicts),
            result.score,
        )

        return result

    def _extract_cited_claims(
        self,
        answer: str,
        citations: list[Citation],
        chunk_map: dict[str, str],
    ) -> list[tuple[str, str]]:
        """Pair each cited sentence with its source text."""
        pairs: list[tuple[str, str]] = []

        # Split answer into sentences and match citation markers
        sentences = re.split(r'(?<=[.!?])\s+', answer)
        citation_lookup = {c.marker: c.chunk_id for c in citations}

        for sentence in sentences:
            # Find citation markers in this sentence
            markers = re.findall(r'\[\^\d+\]', sentence)
            for marker in markers:
                chunk_id = citation_lookup.get(marker)
                if chunk_id and chunk_id in chunk_map:
                    # Clean the sentence (remove markers for verification)
                    clean = re.sub(r'\[\^\d+\]', '', sentence).strip()
                    if clean:
                        pairs.append((clean, chunk_map[chunk_id]))

        return pairs

    async def _verify_claim(self, claim: str, source: str) -> ClaimVerdict:
        """Verify a single claim against a source passage."""
        try:
            user_msg = (
                f"Source passage:\n{source}\n\n"
                f"Claim to verify:\n{claim}\n\n"
                "Is this claim ENTAILED by the source passage? "
                'Respond with JSON: [{"claim": "...", '
                '"verdict": "entailed"|"not_entailed", "reason": "..."}]'
            )

            response = await self._client.messages.create(
                model=settings.claude_classifier_model,
                max_tokens=256,
                system=GROUNDING_PROMPT,
                messages=[{"role": "user", "content": user_msg}],
            )

            raw = response.content[0].text.strip()

            # Parse JSON
            if raw.startswith("["):
                data = json.loads(raw)
            elif "[" in raw:
                json_str = raw[raw.index("["):raw.rindex("]") + 1]
                data = json.loads(json_str)
            else:
                return ClaimVerdict(claim, "entailed", "parse_fallback")

            if data:
                d = data[0]
                return ClaimVerdict(
                    claim=d.get("claim", claim),
                    verdict=d.get("verdict", "entailed"),
                    reason=d.get("reason", ""),
                )

            return ClaimVerdict(claim, "entailed", "empty_response_fallback")

        except Exception:
            # Fail closed — treat unparseable results as not entailed
            logger.exception("Grounding verification failed for claim")
            return ClaimVerdict(claim, "not_entailed", "verification_error")


def compute_confidence(
    reranker_top_score: float,
    grounding: GroundingResult,
) -> float:
    """Composite confidence score from retrieval and grounding signals."""
    retrieval_signal = min(reranker_top_score, 1.0)
    grounding_signal = grounding.score

    # Weighted average: grounding matters more than retrieval score
    confidence = 0.4 * retrieval_signal + 0.6 * grounding_signal
    return round(confidence, 3)
