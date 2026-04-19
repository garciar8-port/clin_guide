"""Tests for query expansion."""

from clinguide.retrieval.query_expansion import QueryExpander


class TestQueryExpander:
    def test_expands_brand_to_generic(self):
        expander = QueryExpander()
        result = expander.expand("What is the dosage for tagrisso?")
        assert "osimertinib" in result.lower()

    def test_expands_generic_to_brand(self):
        expander = QueryExpander()
        result = expander.expand("osimertinib side effects")
        assert "tagrisso" in result.lower()

    def test_no_expansion_for_unknown(self):
        expander = QueryExpander()
        original = "What is the dosage for unknowndrug?"
        result = expander.expand(original)
        assert result == original

    def test_no_duplicate_terms(self):
        expander = QueryExpander()
        result = expander.expand("tagrisso osimertinib dosage")
        # Should not add terms already present
        words = result.lower().split()
        assert words.count("tagrisso") == 1
        assert words.count("osimertinib") == 1
