"""Tests for SPL XML parser."""

from clinguide.ingestion.spl_parser import parse_spl


class TestParseSPL:
    def test_extracts_set_id_and_version(self, sample_spl_xml):
        doc = parse_spl(sample_spl_xml)
        assert doc.set_id == "test-set-001"
        assert doc.version_id == "3"

    def test_extracts_drug_names(self, sample_spl_xml):
        doc = parse_spl(sample_spl_xml)
        assert doc.drug_name == "TESTDRUG"
        assert doc.drug_generic == "testgeneric"

    def test_extracts_correct_sections(self, sample_spl_xml):
        doc = parse_spl(sample_spl_xml)
        loinc_codes = {s.loinc_code for s in doc.sections}
        assert "34067-9" in loinc_codes  # Indications
        assert "34068-7" in loinc_codes  # Dosage
        assert "34070-3" in loinc_codes  # Contraindications
        assert "34074-5" in loinc_codes  # Drug Interactions
        # Product section (48780-1) should NOT be extracted
        assert "48780-1" not in loinc_codes

    def test_section_count(self, sample_spl_xml):
        doc = parse_spl(sample_spl_xml)
        assert len(doc.sections) == 4

    def test_indications_text_content(self, sample_spl_xml):
        doc = parse_spl(sample_spl_xml)
        indications = next(s for s in doc.sections if s.loinc_code == "34067-9")
        assert "metastatic non-small cell lung cancer" in indications.text
        assert "EGFR" in indications.text
        assert "adjuvant therapy" in indications.text

    def test_dosage_text_content(self, sample_spl_xml):
        doc = parse_spl(sample_spl_xml)
        dosage = next(s for s in doc.sections if s.loinc_code == "34068-7")
        assert "80 mg" in dosage.text
        assert "once daily" in dosage.text

    def test_table_extraction(self, sample_spl_xml):
        doc = parse_spl(sample_spl_xml)
        dosage = next(s for s in doc.sections if s.loinc_code == "34068-7")
        assert len(dosage.tables) == 1

        table = dosage.tables[0]
        assert table.caption == "Table 1. Recommended Dose Modifications for Adverse Reactions"
        assert "Adverse Reaction" in table.headers
        assert "Dose Modification" in table.headers
        assert len(table.rows) == 2
        assert "QTc" in table.rows[0][0]
        assert "Permanently discontinue" in table.rows[1][1]

    def test_contraindications_minimal(self, sample_spl_xml):
        doc = parse_spl(sample_spl_xml)
        contra = next(s for s in doc.sections if s.loinc_code == "34070-3")
        assert "None" in contra.text

    def test_drug_interactions_content(self, sample_spl_xml):
        doc = parse_spl(sample_spl_xml)
        interactions = next(s for s in doc.sections if s.loinc_code == "34074-5")
        assert "CYP3A4" in interactions.text
        assert "40 mg" in interactions.text
