"""Tests for the synonym dictionary."""

from clinguide.ingestion.synonyms import SynonymDictionary


class TestSynonymDictionary:
    def test_expand_known_brand(self):
        d = SynonymDictionary()
        terms = d.expand("tagrisso")
        assert "osimertinib" in terms
        assert "tagrisso" in terms

    def test_expand_known_generic(self):
        d = SynonymDictionary()
        terms = d.expand("osimertinib")
        assert "tagrisso" in terms

    def test_expand_unknown_returns_original(self):
        d = SynonymDictionary()
        terms = d.expand("unknowndrug123")
        assert terms == ["unknowndrug123"]

    def test_case_insensitive(self):
        d = SynonymDictionary()
        terms = d.expand("TAGRISSO")
        assert "osimertinib" in terms

    def test_get_generic(self):
        d = SynonymDictionary()
        assert d.get_generic("tagrisso") == "osimertinib"
        assert d.get_generic("keytruda") == "pembrolizumab"
        assert d.get_generic("unknowndrug") is None

    def test_add_and_expand(self):
        d = SynonymDictionary()
        d.add("BrandNew", "genericnew", ["test class"])
        terms = d.expand("brandnew")
        assert "genericnew" in terms
