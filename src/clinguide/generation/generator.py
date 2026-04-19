"""Claude-powered answer generation with inline citations."""

import json
from datetime import datetime, timezone

from anthropic import AsyncAnthropic

from clinguide.core.config import settings
from clinguide.core.models import Citation, QueryResponse
from clinguide.retrieval.vector_search import RetrievalHit

DISCLAIMER_TEMPLATE = (
    "This information is derived from FDA drug labeling retrieved on {retrieved_at}. "
    "It is intended for informational purposes only and does not constitute medical advice. "
    "Always verify against the current prescribing information and consult a qualified "
    "healthcare professional before making clinical decisions."
)

SYSTEM_PROMPT = """\
You are a clinical information assistant. Answer ONLY from the provided source passages.

Rules:
1. Cite every factual claim using [^n] markers mapped to the source chunks.
2. If the sources do not contain the answer, respond exactly: \
"I don't have enough information in the available drug labels to answer this."
3. Never invent drug names, doses, or indications not present in the sources.
4. Be concise and clinically precise.
5. Structure your answer with the most important information first.

Respond in JSON format with this schema:
{
  "answer": "Your answer with [^1] citation markers",
  "citations": [
    {"marker": "[^1]", "chunk_id": "chunk_id_here", "quoted_span": "exact quote from source"}
  ],
  "confidence": 0.0 to 1.0
}"""


class Generator:
    """Generate grounded answers from retrieved chunks using Claude."""

    def __init__(self) -> None:
        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def generate(
        self,
        query: str,
        chunks: list[RetrievalHit],
    ) -> QueryResponse:
        """Generate an answer with inline citations from retrieved chunks."""
        if not chunks:
            return self._abstain("no_chunks_retrieved")

        context = self._format_context(chunks)
        user_message = f"Question: {query}\n\nSource passages:\n{context}"

        response = await self._client.messages.create(
            model=settings.claude_model,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        return self._parse_response(response)

    def _format_context(self, chunks: list[RetrievalHit]) -> str:
        """Format retrieved chunks as numbered source passages."""
        parts: list[str] = []
        for i, chunk in enumerate(chunks, 1):
            drug = chunk.metadata.get("drug_name", "Unknown")
            section = chunk.metadata.get("section_name", "Unknown")
            parts.append(
                f"[^{i}] (chunk_id: {chunk.chunk_id})\n"
                f"Drug: {drug} | Section: {section}\n"
                f"{chunk.text}\n"
            )
        return "\n---\n".join(parts)

    def _parse_response(self, response) -> QueryResponse:
        """Parse Claude's JSON response into a QueryResponse."""
        raw_text = response.content[0].text

        # Extract JSON from the response (handle markdown code blocks)
        json_str = raw_text
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0]
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0]

        try:
            data = json.loads(json_str.strip())
        except json.JSONDecodeError:
            # If Claude didn't return valid JSON, treat the whole response as the answer
            return QueryResponse(
                answer=raw_text,
                citations=[],
                confidence=0.5,
                disclaimer=DISCLAIMER_TEMPLATE.format(
                    retrieved_at=datetime.now(timezone.utc).isoformat()
                ),
            )

        citations = [
            Citation(
                marker=c.get("marker", f"[^{i+1}]"),
                chunk_id=c.get("chunk_id", ""),
                quoted_span=c.get("quoted_span", ""),
            )
            for i, c in enumerate(data.get("citations", []))
        ]

        return QueryResponse(
            answer=data.get("answer", ""),
            citations=citations,
            confidence=data.get("confidence", 0.5),
            disclaimer=DISCLAIMER_TEMPLATE.format(
                retrieved_at=datetime.now(timezone.utc).isoformat()
            ),
        )

    def _abstain(self, reason: str) -> QueryResponse:
        return QueryResponse(
            answer="I don't have enough information in the available drug labels to answer this.",
            citations=[],
            confidence=0.0,
            disclaimer=DISCLAIMER_TEMPLATE.format(
                retrieved_at=datetime.now(timezone.utc).isoformat()
            ),
            abstained=True,
            abstain_reason=reason,
        )
