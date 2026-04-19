"""Freshness pipeline — detect SPL updates and re-ingest affected labels."""

import logging

from clinguide.ingestion.chunker import chunk_label
from clinguide.ingestion.dailymed_client import DailyMedClient
from clinguide.ingestion.spl_parser import parse_spl
from clinguide.retrieval.embedder import Embedder

logger = logging.getLogger("clinguide.ingestion.freshness")


async def check_freshness(
    tracked_set_ids: list[str],
    client: DailyMedClient | None = None,
    embedder: Embedder | None = None,
) -> dict:
    """Check for updated labels and re-ingest any that have changed.

    Args:
        tracked_set_ids: List of setIds currently in the index.
        client: DailyMed API client.
        embedder: Embedder for re-embedding and upserting.

    Returns:
        Stats dict with counts of checked, updated, and failed labels.
    """
    client = client or DailyMedClient()
    embedder = embedder or Embedder()

    stats = {"checked": 0, "updated": 0, "failed": 0, "unchanged": 0}

    for set_id in tracked_set_ids:
        stats["checked"] += 1
        try:
            # Fetch current version from DailyMed
            remote_xml = await client.fetch_spl_xml(set_id)
            remote_doc = parse_spl(remote_xml)

            # Check if we have a cached version
            cached_xml = client.load_cached_xml(set_id)
            if cached_xml:
                cached_doc = parse_spl(cached_xml)
                if cached_doc.version_id == remote_doc.version_id:
                    stats["unchanged"] += 1
                    continue

            logger.info(
                "Label updated: %s (%s) — version %s",
                set_id, remote_doc.drug_name, remote_doc.version_id,
            )

            # Re-chunk and re-embed
            chunks = chunk_label(remote_doc)
            await embedder.upsert_chunks(chunks)

            # Cache the new XML
            await client.fetch_and_store(set_id)

            stats["updated"] += 1

        except Exception:
            logger.exception("Failed to check freshness for %s", set_id)
            stats["failed"] += 1

    logger.info("Freshness check complete: %s", stats)
    return stats


async def manual_reingest(
    drug_names: list[str],
    client: DailyMedClient | None = None,
    embedder: Embedder | None = None,
) -> dict:
    """Manual re-ingest: fetch latest labels for given drugs and update the index."""
    from clinguide.ingestion.pipeline import ingest_drugs

    results = await ingest_drugs(drug_names)
    total = {
        "drugs": len(results),
        "labels": sum(r["labels_processed"] for r in results),
        "chunks": sum(r["total_chunks"] for r in results),
    }
    logger.info("Manual re-ingest complete: %s", total)
    return total


if __name__ == "__main__":
    import asyncio
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    drugs = sys.argv[1:] or ["osimertinib", "pembrolizumab", "metformin", "lisinopril", "warfarin"]
    print(f"Re-ingesting: {drugs}")
    result = asyncio.run(manual_reingest(drugs))
    print(f"Done: {result}")
