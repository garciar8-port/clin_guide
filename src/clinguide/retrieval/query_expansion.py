"""Query expansion: synonym dictionary + optional LLM synonym pass."""

import logging

from clinguide.ingestion.synonyms import SynonymDictionary

logger = logging.getLogger("clinguide.retrieval.expansion")


class QueryExpander:
    """Expand clinical queries with drug name synonyms."""

    def __init__(self, synonyms: SynonymDictionary | None = None) -> None:
        self._synonyms = synonyms or SynonymDictionary()

    def expand(self, query: str) -> str:
        """Expand query by appending synonym terms.

        Example: "tagrisso dosage" → "tagrisso dosage osimertinib"
        """
        words = query.lower().split()
        additions: set[str] = set()

        for word in words:
            # Strip common punctuation
            clean = word.strip("?.,;:!\"'()")
            expanded = self._synonyms.expand(clean)
            for term in expanded:
                if term.lower() not in query.lower():
                    additions.add(term)

        if additions:
            expanded_query = f"{query} {' '.join(sorted(additions))}"
            logger.info("Expanded query: '%s' → '%s'", query, expanded_query)
            return expanded_query

        return query
