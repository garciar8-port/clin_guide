"""Chunking experiment — compare 3 strategies on the gold dataset."""

import logging

from clinguide.core.models import LabelDocument, LabelSection, Chunk
from clinguide.ingestion.chunker import chunk_label, count_tokens

logger = logging.getLogger("clinguide.eval.chunking")

FIXED_CHUNK_SIZE = 512
FIXED_OVERLAP = 77  # ~15% of 512


def strategy_section_only(doc: LabelDocument) -> list[Chunk]:
    """Strategy 1: One chunk per section, no splitting."""
    chunks: list[Chunk] = []
    for i, section in enumerate(doc.sections):
        full_text = section.text
        for table in section.tables:
            lines = []
            if table.caption:
                lines.append(table.caption)
            if table.headers:
                lines.append(" | ".join(table.headers))
            for row in table.rows:
                lines.append(" | ".join(row))
            full_text += "\n\n" + "\n".join(lines)

        chunks.append(Chunk(
            chunk_id=f"{doc.set_id}:{section.loinc_code}:{i}",
            set_id=doc.set_id,
            version_id=doc.version_id,
            drug_name=doc.drug_name,
            drug_generic=doc.drug_generic,
            drug_class=doc.drug_class,
            loinc_code=section.loinc_code,
            section_name=section.section_name,
            text=full_text,
            tables=section.tables,
            approval_date=doc.approval_date,
            last_updated=doc.last_updated,
        ))
    return chunks


def strategy_fixed_512(doc: LabelDocument) -> list[Chunk]:
    """Strategy 2: Fixed 512-token chunks with 15% overlap, ignoring section boundaries."""
    import tiktoken
    enc = tiktoken.get_encoding("cl100k_base")

    # Concatenate all section text
    all_text = ""
    for section in doc.sections:
        all_text += f"\n\n{section.section_name}\n{section.text}"
        for table in section.tables:
            if table.caption:
                all_text += f"\n{table.caption}"
            for row in table.rows:
                all_text += "\n" + " | ".join(row)

    tokens = enc.encode(all_text)
    chunks: list[Chunk] = []
    idx = 0
    start = 0

    while start < len(tokens):
        end = min(start + FIXED_CHUNK_SIZE, len(tokens))
        chunk_text = enc.decode(tokens[start:end])

        chunks.append(Chunk(
            chunk_id=f"{doc.set_id}:fixed:{idx}",
            set_id=doc.set_id,
            version_id=doc.version_id,
            drug_name=doc.drug_name,
            drug_generic=doc.drug_generic,
            drug_class=doc.drug_class,
            loinc_code="mixed",
            section_name="fixed_512",
            text=chunk_text,
            approval_date=doc.approval_date,
            last_updated=doc.last_updated,
        ))

        idx += 1
        start = end - FIXED_OVERLAP

    return chunks


def strategy_hybrid(doc: LabelDocument) -> list[Chunk]:
    """Strategy 3: Section-aware with overlap (the default chunker)."""
    return chunk_label(doc)


def run_experiment(docs: list[LabelDocument]) -> dict:
    """Run all 3 strategies on a set of documents and report stats."""
    strategies = {
        "section_only": strategy_section_only,
        "fixed_512": strategy_fixed_512,
        "hybrid": strategy_hybrid,
    }

    results: dict[str, dict] = {}

    for name, strategy_fn in strategies.items():
        all_chunks: list[Chunk] = []
        for doc in docs:
            all_chunks.extend(strategy_fn(doc))

        token_counts = [count_tokens(c.text) for c in all_chunks]

        results[name] = {
            "total_chunks": len(all_chunks),
            "avg_tokens": sum(token_counts) / len(token_counts) if token_counts else 0,
            "min_tokens": min(token_counts) if token_counts else 0,
            "max_tokens": max(token_counts) if token_counts else 0,
            "total_tokens": sum(token_counts),
        }

        logger.info(
            "Strategy '%s': %d chunks, avg %.0f tokens (min=%d, max=%d)",
            name, results[name]["total_chunks"],
            results[name]["avg_tokens"],
            results[name]["min_tokens"],
            results[name]["max_tokens"],
        )

    return results
