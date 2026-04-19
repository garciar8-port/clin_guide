"""Tests for the section-aware chunker."""

from clinguide.core.models import LabelDocument, LabelSection, TableExtract
from clinguide.ingestion.chunker import chunk_label, count_tokens


def _make_doc(sections: list[LabelSection]) -> LabelDocument:
    return LabelDocument(
        set_id="test-set-001",
        version_id="1",
        drug_name="TESTDRUG",
        drug_generic="testgeneric",
        sections=sections,
    )


class TestChunkIdScheme:
    def test_chunk_id_format(self):
        doc = _make_doc([
            LabelSection(loinc_code="34067-9", section_name="Indications", text="Short text."),
        ])
        chunks = chunk_label(doc)
        assert len(chunks) == 1
        assert chunks[0].chunk_id == "test-set-001:34067-9:0"

    def test_chunk_ids_sequential(self):
        long_text = "\n".join(["This is a test sentence with enough words." for _ in range(200)])
        doc = _make_doc([
            LabelSection(loinc_code="34068-7", section_name="Dosage", text=long_text),
        ])
        chunks = chunk_label(doc)
        assert len(chunks) > 1
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_id == f"test-set-001:34068-7:{i}"


class TestChunking:
    def test_short_section_single_chunk(self):
        doc = _make_doc([
            LabelSection(
                loinc_code="34070-3",
                section_name="Contraindications",
                text="None.",
            ),
        ])
        chunks = chunk_label(doc)
        assert len(chunks) == 1
        assert chunks[0].text == "None."

    def test_long_section_splits(self):
        long_text = "\n".join([f"Paragraph {i}: " + "word " * 50 for i in range(20)])
        doc = _make_doc([
            LabelSection(loinc_code="34067-9", section_name="Indications", text=long_text),
        ])
        chunks = chunk_label(doc)
        assert len(chunks) > 1

    def test_chunk_metadata_preserved(self):
        doc = _make_doc([
            LabelSection(loinc_code="34067-9", section_name="Indications", text="Short."),
        ])
        chunks = chunk_label(doc)
        chunk = chunks[0]
        assert chunk.set_id == "test-set-001"
        assert chunk.version_id == "1"
        assert chunk.drug_name == "TESTDRUG"
        assert chunk.drug_generic == "testgeneric"
        assert chunk.loinc_code == "34067-9"
        assert chunk.section_name == "Indications"

    def test_table_preserved_in_chunk(self):
        table = TableExtract(
            caption="Dose table",
            headers=["Condition", "Dose"],
            rows=[["Renal impairment", "40 mg"]],
        )
        doc = _make_doc([
            LabelSection(
                loinc_code="34068-7",
                section_name="Dosage",
                text="Take as directed.",
                tables=[table],
            ),
        ])
        chunks = chunk_label(doc)
        assert len(chunks) == 1
        # Table content should be in the chunk text
        assert "Dose table" in chunks[0].text or chunks[0].tables

    def test_multiple_sections_chunked_separately(self):
        doc = _make_doc([
            LabelSection(loinc_code="34067-9", section_name="Indications", text="Indication text."),
            LabelSection(loinc_code="34070-3", section_name="Contraindications", text="None."),
        ])
        chunks = chunk_label(doc)
        assert len(chunks) == 2
        assert chunks[0].loinc_code == "34067-9"
        assert chunks[1].loinc_code == "34070-3"


class TestTokenCounting:
    def test_count_tokens_basic(self):
        count = count_tokens("Hello world")
        assert count > 0
        assert isinstance(count, int)

    def test_empty_string(self):
        assert count_tokens("") == 0
