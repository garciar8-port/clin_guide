"""Pairwise configuration evaluation — A/B compare two RAG configs."""

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from clinguide.eval.harness import (
    EvalReport,
)

logger = logging.getLogger("clinguide.eval.pairwise")


@dataclass
class ConfigResult:
    name: str
    report: EvalReport


class PairwiseEval:
    """Compare two RAG configurations side-by-side on the gold dataset."""

    def __init__(self) -> None:
        self.configs: list[ConfigResult] = []

    def add_config(self, name: str, report: EvalReport) -> None:
        self.configs.append(ConfigResult(name=name, report=report))

    def comparison_table(self) -> str:
        """Generate a markdown comparison table."""
        if len(self.configs) < 2:
            return "Need at least 2 configs to compare."

        summaries = [(c.name, c.report.summary()) for c in self.configs]

        metrics = [
            "total_cases",
            "abstention_accuracy",
            "happy_path_coverage",
            "adversarial_abstention_rate",
            "citation_rate",
        ]

        header = "| Metric | " + " | ".join(s[0] for s in summaries) + " | Winner |"
        separator = "| --- | " + " | ".join(["---"] * len(summaries)) + " | --- |"
        rows = [header, separator]

        for metric in metrics:
            values = [s[1].get(metric, 0) for s in summaries]
            cells = []
            for v in values:
                if isinstance(v, float):
                    cells.append(f"{v:.3f}")
                else:
                    cells.append(str(v))

            # Determine winner (higher is better for these metrics)
            if all(isinstance(v, (int, float)) for v in values):
                max_val = max(values)
                if values.count(max_val) == 1:
                    winner = summaries[values.index(max_val)][0]
                else:
                    winner = "Tie"
            else:
                winner = "—"

            row = f"| {metric} | " + " | ".join(cells) + f" | {winner} |"
            rows.append(row)

        return "\n".join(rows)

    def per_case_diff(self) -> list[dict]:
        """Show per-case differences between configs."""
        if len(self.configs) < 2:
            return []

        a, b = self.configs[0], self.configs[1]
        diffs: list[dict] = []

        for r_a, r_b in zip(
            a.report.results, b.report.results, strict=False
        ):
            if r_a["id"] != r_b["id"]:
                continue

            if r_a["failure_mode"] != r_b["failure_mode"]:
                diffs.append({
                    "case_id": r_a["id"],
                    f"{a.name}_failure": r_a["failure_mode"],
                    f"{b.name}_failure": r_b["failure_mode"],
                    f"{a.name}_coverage": r_a["answer_coverage"],
                    f"{b.name}_coverage": r_b["answer_coverage"],
                })

        return diffs

    def save(self, path: Path) -> None:
        output = {
            "configs": [c.name for c in self.configs],
            "comparison": self.comparison_table(),
            "per_case_diffs": self.per_case_diff(),
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(output, f, indent=2)
        logger.info("Pairwise eval saved to %s", path)
