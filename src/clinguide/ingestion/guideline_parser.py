"""PDF parser for CDC/NIH clinical practice guidelines."""

import logging
import re
from pathlib import Path

import fitz  # pymupdf

from clinguide.core.models import LabelDocument, LabelSection

logger = logging.getLogger("clinguide.ingestion.guideline_parser")

# Map common guideline section headings to LOINC-like categories
SECTION_PATTERNS: dict[str, str] = {
    r"(?i)recommendation": "recommendations",
    r"(?i)contraindication": "contraindications",
    r"(?i)indication": "indications",
    r"(?i)dosage|dosing|dose": "dosage",
    r"(?i)warning|precaution|safety": "warnings",
    r"(?i)adverse|side effect": "adverse_reactions",
    r"(?i)drug interaction|interaction": "drug_interactions",
    r"(?i)screening|prevention": "screening",
    r"(?i)diagnosis|diagnostic": "diagnosis",
    r"(?i)treatment|management|therapy": "treatment",
    r"(?i)monitoring|follow.?up": "monitoring",
    r"(?i)epidemiology|prevalence|incidence": "epidemiology",
    r"(?i)summary|abstract|overview": "summary",
}


def classify_section(heading: str) -> str:
    """Map a section heading to a normalized category."""
    for pattern, category in SECTION_PATTERNS.items():
        if re.search(pattern, heading):
            return category
    return "general"


def parse_guideline_pdf(
    pdf_path: Path,
    source: str = "CDC",
    guideline_name: str = "",
) -> LabelDocument:
    """Parse a clinical guideline PDF into a LabelDocument.

    Unlike SPL XML, PDFs don't have deterministic structure.
    We extract text by page, detect section headings via font size heuristics,
    and group paragraphs into sections.
    """
    doc = fitz.open(str(pdf_path))

    if not guideline_name:
        guideline_name = pdf_path.stem

    # Extract blocks with font metadata
    raw_sections = _extract_sections(doc)

    sections: list[LabelSection] = []
    for heading, text in raw_sections:
        category = classify_section(heading)
        if not text.strip():
            continue
        sections.append(
            LabelSection(
                loinc_code=f"guideline-{category}",
                section_name=heading,
                text=text.strip(),
            )
        )

    doc.close()

    set_id = f"{source.lower()}-{_slugify(guideline_name)}"

    logger.info(
        "Parsed guideline '%s': %d sections from %s",
        guideline_name, len(sections), pdf_path.name,
    )

    return LabelDocument(
        set_id=set_id,
        version_id="1",
        drug_name=guideline_name,
        drug_generic=guideline_name,
        sections=sections,
    )


def _extract_sections(doc: fitz.Document) -> list[tuple[str, str]]:
    """Extract sections from a PDF using font size heuristics for headings."""
    sections: list[tuple[str, str]] = []
    current_heading = "Introduction"
    current_text: list[str] = []

    for page in doc:
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            if "lines" not in block:
                continue
            for line in block["lines"]:
                line_text = ""
                max_font_size = 0
                for span in line["spans"]:
                    line_text += span["text"]
                    max_font_size = max(max_font_size, span["size"])

                line_text = line_text.strip()
                if not line_text:
                    continue

                # Heuristic: headings have larger font size (>= 12pt)
                # and are typically short (< 100 chars)
                is_heading = (
                    max_font_size >= 12
                    and len(line_text) < 100
                    and not line_text.endswith(".")
                )

                if is_heading:
                    # Save previous section
                    if current_text:
                        sections.append((current_heading, "\n".join(current_text)))
                    current_heading = line_text
                    current_text = []
                else:
                    current_text.append(line_text)

    # Save last section
    if current_text:
        sections.append((current_heading, "\n".join(current_text)))

    return sections


def _slugify(text: str) -> str:
    """Convert text to a URL-safe slug."""
    slug = re.sub(r"[^\w\s-]", "", text.lower())
    return re.sub(r"[\s_]+", "-", slug).strip("-")[:60]


async def ingest_guideline(
    pdf_path: Path,
    source: str = "CDC",
    guideline_name: str = "",
) -> dict:
    """Parse, chunk, embed, and upsert a clinical guideline PDF."""
    from clinguide.ingestion.chunker import chunk_label
    from clinguide.retrieval.embedder import Embedder

    doc = parse_guideline_pdf(pdf_path, source=source, guideline_name=guideline_name)

    chunks = chunk_label(doc)
    logger.info("Chunked guideline into %d chunks", len(chunks))

    embedder = Embedder()
    upserted = await embedder.upsert_chunks(chunks)

    return {
        "source": source,
        "guideline": guideline_name or pdf_path.stem,
        "sections": len(doc.sections),
        "chunks": len(chunks),
        "upserted": upserted,
    }
