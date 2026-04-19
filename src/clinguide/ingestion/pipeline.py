"""End-to-end ingestion pipeline: fetch → parse → chunk → embed → upsert."""

import asyncio
import logging

from clinguide.ingestion.dailymed_client import DailyMedClient
from clinguide.ingestion.spl_parser import parse_spl
from clinguide.ingestion.chunker import chunk_label
from clinguide.ingestion.synonyms import SynonymDictionary
from clinguide.retrieval.embedder import Embedder

logger = logging.getLogger("clinguide.ingestion")


async def ingest_drug(
    drug_name: str,
    client: DailyMedClient | None = None,
    embedder: Embedder | None = None,
    synonyms: SynonymDictionary | None = None,
) -> dict:
    """Ingest all labels for a drug name. Returns stats."""
    client = client or DailyMedClient()
    embedder = embedder or Embedder()
    synonyms = synonyms or SynonymDictionary()

    # Search for labels
    results = await client.search_labels(drug_name=drug_name)
    entries = results.get("data", [])
    logger.info("Found %d labels for '%s'", len(entries), drug_name)

    total_chunks = 0
    total_upserted = 0

    for entry in entries:
        set_id = entry["setid"]
        title = entry.get("title", "")
        logger.info("Processing %s: %s", set_id, title)

        # Fetch and cache XML
        xml_path = await client.fetch_and_store(set_id)
        raw_xml = xml_path.read_bytes()

        # Parse
        doc = parse_spl(raw_xml)
        logger.info(
            "Parsed %s: %s (%s), %d sections",
            set_id, doc.drug_name, doc.drug_generic, len(doc.sections),
        )

        # Update synonym dictionary
        if doc.drug_name and doc.drug_generic:
            synonyms.add(doc.drug_name, doc.drug_generic, doc.drug_class)

        # Chunk
        chunks = chunk_label(doc)
        total_chunks += len(chunks)
        logger.info("Chunked %s into %d chunks", set_id, len(chunks))

        # Embed and upsert
        upserted = await embedder.upsert_chunks(chunks)
        total_upserted += upserted
        logger.info("Upserted %d chunks for %s", upserted, set_id)

    # Save updated synonyms
    synonyms.save()

    return {
        "drug_name": drug_name,
        "labels_processed": len(entries),
        "total_chunks": total_chunks,
        "total_upserted": total_upserted,
    }


async def ingest_drugs(drug_names: list[str]) -> list[dict]:
    """Ingest multiple drugs sequentially."""
    client = DailyMedClient()
    embedder = Embedder()
    synonyms = SynonymDictionary()

    results = []
    for name in drug_names:
        result = await ingest_drug(
            name, client=client, embedder=embedder, synonyms=synonyms
        )
        results.append(result)
        logger.info("Completed ingestion for %s: %s", name, result)

    return results


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    drugs = sys.argv[1:] or ["osimertinib", "pembrolizumab", "metformin", "lisinopril", "warfarin"]
    print(f"Ingesting: {drugs}")
    results = asyncio.run(ingest_drugs(drugs))
    for r in results:
        print(r)
