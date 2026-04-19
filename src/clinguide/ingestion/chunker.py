"""Section-aware chunker for FDA drug label sections."""

import tiktoken

from clinguide.core.config import settings
from clinguide.core.models import Chunk, LabelDocument, LabelSection, TableExtract

_enc = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    return len(_enc.encode(text))


def chunk_label(doc: LabelDocument) -> list[Chunk]:
    """Chunk all sections of a LabelDocument into Chunk objects with stable IDs."""
    chunks: list[Chunk] = []
    for section in doc.sections:
        chunks.extend(_chunk_section(section, doc))
    return chunks


def _chunk_section(section: LabelSection, doc: LabelDocument) -> list[Chunk]:
    """Chunk a single section. Short sections stay whole; long ones are split with overlap."""
    full_text = _section_text_with_tables(section)
    token_count = count_tokens(full_text)

    if token_count <= settings.chunk_target_tokens:
        # Single chunk for the whole section
        return [_build_chunk(section, full_text, section.tables, 0, doc)]

    # Split long sections with sliding window, preserving table boundaries
    return _sliding_window_chunks(section, doc)


def _section_text_with_tables(section: LabelSection) -> str:
    """Combine section text and table text for token counting."""
    parts = [section.text]
    for table in section.tables:
        parts.append(_table_to_text(table))
    return "\n\n".join(p for p in parts if p)


def _table_to_text(table: TableExtract) -> str:
    """Render a table as readable text for embedding."""
    lines: list[str] = []
    if table.caption:
        lines.append(table.caption)
    if table.headers:
        lines.append(" | ".join(table.headers))
        lines.append("-" * len(lines[-1]))
    for row in table.rows:
        lines.append(" | ".join(row))
    return "\n".join(lines)


def _sliding_window_chunks(
    section: LabelSection, doc: LabelDocument
) -> list[Chunk]:
    """Split a long section into overlapping chunks, never breaking mid-table."""
    # Build a list of text blocks: paragraphs + tables (tables are atomic)
    blocks: list[tuple[str, list[TableExtract]]] = []

    # Split section text into paragraphs
    for para in section.text.split("\n"):
        stripped = para.strip()
        if stripped:
            blocks.append((stripped, []))

    # Add tables as atomic blocks
    for table in section.tables:
        blocks.append((_table_to_text(table), [table]))

    chunks: list[Chunk] = []
    chunk_idx = 0
    current_texts: list[str] = []
    current_tables: list[TableExtract] = []
    current_tokens = 0

    for block_text, block_tables in blocks:
        block_tokens = count_tokens(block_text)

        # If a single block exceeds the target, it becomes its own chunk
        if block_tokens > settings.chunk_target_tokens and not current_texts:
            chunks.append(
                _build_chunk(section, block_text, block_tables, chunk_idx, doc)
            )
            chunk_idx += 1
            continue

        # Would adding this block exceed the target?
        if current_tokens + block_tokens > settings.chunk_target_tokens and current_texts:
            # Emit current chunk
            chunk_text = "\n".join(current_texts)
            chunks.append(
                _build_chunk(section, chunk_text, current_tables, chunk_idx, doc)
            )
            chunk_idx += 1

            # Overlap: keep the tail of the current chunk
            overlap_texts, overlap_tables, overlap_tokens = _compute_overlap(
                current_texts, current_tables
            )
            current_texts = overlap_texts
            current_tables = overlap_tables
            current_tokens = overlap_tokens

        current_texts.append(block_text)
        current_tables.extend(block_tables)
        current_tokens += block_tokens

    # Emit remaining
    if current_texts:
        chunk_text = "\n".join(current_texts)
        chunks.append(
            _build_chunk(section, chunk_text, current_tables, chunk_idx, doc)
        )

    return chunks


def _compute_overlap(
    texts: list[str], tables: list[TableExtract]
) -> tuple[list[str], list[TableExtract], int]:
    """Keep the trailing blocks that fit within the overlap budget."""
    target = settings.chunk_overlap_tokens
    overlap_texts: list[str] = []
    overlap_tables: list[TableExtract] = []
    total = 0

    for text in reversed(texts):
        tokens = count_tokens(text)
        if total + tokens > target:
            break
        overlap_texts.insert(0, text)
        total += tokens

    # Tables in the overlap region
    # (simplified: we don't split tables across overlap boundaries)
    return overlap_texts, overlap_tables, total


def _build_chunk(
    section: LabelSection,
    text: str,
    tables: list[TableExtract],
    chunk_idx: int,
    doc: LabelDocument,
) -> Chunk:
    """Build a Chunk with a stable ID."""
    return Chunk(
        chunk_id=f"{doc.set_id}:{section.loinc_code}:{chunk_idx}",
        set_id=doc.set_id,
        version_id=doc.version_id,
        drug_name=doc.drug_name,
        drug_generic=doc.drug_generic,
        drug_class=doc.drug_class,
        loinc_code=section.loinc_code,
        section_name=section.section_name,
        text=text,
        tables=tables,
        approval_date=doc.approval_date,
        last_updated=doc.last_updated,
    )
