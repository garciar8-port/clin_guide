"""Embedding model benchmark — compare OpenAI vs Bedrock Titan on retrieval quality."""

import json
import logging
import time
from pathlib import Path

from clinguide.core.models import Chunk
from clinguide.ingestion.chunker import count_tokens

logger = logging.getLogger("clinguide.eval.embedding_benchmark")

RESULTS_PATH = Path(__file__).parent.parent.parent.parent / "eval" / "results"


class EmbeddingBenchmark:
    """Benchmark embedding models on retrieval quality, latency, and cost."""

    def __init__(self) -> None:
        self.results: dict[str, dict] = {}

    async def benchmark_openai(
        self,
        chunks: list[Chunk],
        queries: list[str],
    ) -> dict:
        """Benchmark OpenAI text-embedding-3-small."""
        from clinguide.retrieval.embedder import Embedder

        embedder = Embedder()
        return await self._run_benchmark(
            name="openai-text-embedding-3-small",
            embedder=embedder,
            chunks=chunks,
            queries=queries,
            cost_per_1k_tokens=0.00002,
        )

    async def _run_benchmark(
        self,
        name: str,
        embedder,
        chunks: list[Chunk],
        queries: list[str],
        cost_per_1k_tokens: float,
    ) -> dict:
        """Run a benchmark for a single embedding model."""
        texts = [c.text for c in chunks]
        total_tokens = sum(count_tokens(t) for t in texts)

        # Embedding latency
        start = time.perf_counter()
        embeddings = await embedder.embed_texts(texts)
        embed_latency = (time.perf_counter() - start) * 1000

        # Query latency (average over queries)
        query_latencies: list[float] = []
        for q in queries:
            q_start = time.perf_counter()
            await embedder.embed_query(q)
            query_latencies.append((time.perf_counter() - q_start) * 1000)

        avg_query_latency = sum(query_latencies) / len(query_latencies) if query_latencies else 0

        result = {
            "model": name,
            "num_chunks": len(chunks),
            "total_tokens": total_tokens,
            "embedding_dimensions": len(embeddings[0]) if embeddings else 0,
            "bulk_embed_latency_ms": round(embed_latency, 1),
            "avg_query_embed_latency_ms": round(avg_query_latency, 1),
            "p95_query_embed_latency_ms": round(
                sorted(query_latencies)[int(len(query_latencies) * 0.95)] if query_latencies else 0,
                1,
            ),
            "estimated_cost_per_1k_chunks": round(
                (total_tokens / len(chunks)) * cost_per_1k_tokens if chunks else 0,
                6,
            ),
        }

        self.results[name] = result
        logger.info("Benchmark %s: %s", name, result)
        return result

    def comparison_table(self) -> str:
        """Generate a markdown comparison table."""
        if not self.results:
            return "No results yet."

        headers = [
            "Model", "Dims", "Bulk Embed (ms)", "Avg Query (ms)",
            "P95 Query (ms)", "$/1k chunks",
        ]
        rows: list[list[str]] = []
        for name, r in self.results.items():
            rows.append([
                name,
                str(r["embedding_dimensions"]),
                str(r["bulk_embed_latency_ms"]),
                str(r["avg_query_embed_latency_ms"]),
                str(r["p95_query_embed_latency_ms"]),
                str(r["estimated_cost_per_1k_chunks"]),
            ])

        table = "| " + " | ".join(headers) + " |\n"
        table += "| " + " | ".join(["---"] * len(headers)) + " |\n"
        for row in rows:
            table += "| " + " | ".join(row) + " |\n"

        return table

    def save(self) -> None:
        RESULTS_PATH.mkdir(parents=True, exist_ok=True)
        path = RESULTS_PATH / "embedding_benchmark.json"
        with open(path, "w") as f:
            json.dump(self.results, f, indent=2)
        logger.info("Saved benchmark results to %s", path)
