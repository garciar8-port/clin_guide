"""Tests for the guideline PDF section classifier."""

from clinguide.ingestion.guideline_parser import classify_section


class TestClassifySection:
    def test_recommendation(self):
        assert classify_section("Recommendations for Treatment") == "recommendations"

    def test_dosage(self):
        assert classify_section("Dosage and Administration") == "dosage"

    def test_contraindications(self):
        assert classify_section("Contraindications") == "contraindications"

    def test_drug_interactions(self):
        assert classify_section("Drug Interactions") == "drug_interactions"

    def test_screening(self):
        assert classify_section("Screening Guidelines") == "screening"

    def test_treatment(self):
        assert classify_section("Treatment and Management") == "treatment"

    def test_unknown(self):
        assert classify_section("Appendix A: References") == "general"

    def test_case_insensitive(self):
        assert classify_section("WARNINGS AND PRECAUTIONS") == "warnings"
