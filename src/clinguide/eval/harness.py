"""Evaluation harness — retrieval and generation metrics over gold dataset."""

import json
import logging
import re
from pathlib import Path

logger = logging.getLogger("clinguide.eval")

CASES_PATH = Path(__file__).parent.parent.parent.parent / "eval" / "datasets" / "cases.json"


def load_cases(path: Path | None = None) -> list[dict]:
    p = path or CASES_PATH
    with open(p) as f:
        return json.load(f)


# --- Retrieval Metrics ---


def precision_at_k(retrieved_ids: list[str], expected_ids: list[str], k: int = 5) -> float:
    """Fraction of top-k retrieved chunks that are relevant."""
    if k == 0:
        return 0.0
    top_k = retrieved_ids[:k]
    expected = set(expected_ids)
    return len(set(top_k) & expected) / k


def recall_at_k(retrieved_ids: list[str], expected_ids: list[str], k: int = 5) -> float:
    """Fraction of expected chunks found in top-k."""
    if not expected_ids:
        return 1.0
    top_k = set(retrieved_ids[:k])
    expected = set(expected_ids)
    return len(top_k & expected) / len(expected)


def mrr(retrieved_ids: list[str], expected_ids: list[str]) -> float:
    """Mean reciprocal rank — position of the first relevant result."""
    expected = set(expected_ids)
    for i, chunk_id in enumerate(retrieved_ids):
        if chunk_id in expected:
            return 1.0 / (i + 1)
    return 0.0


# --- Generation Metrics ---


def answer_contains(answer: str, expected_terms: list[str]) -> float:
    """Fraction of expected terms found in the answer."""
    if not expected_terms:
        return 1.0
    found = sum(1 for t in expected_terms if t.lower() in answer.lower())
    return found / len(expected_terms)


def citation_count(answer: str) -> int:
    """Count citation markers [^n] in the answer."""
    return len(re.findall(r'\[\^\d+\]', answer))


def abstention_correct(response: dict, case: dict) -> bool:
    """Did the system correctly abstain (or not) based on expected behavior?"""
    expected = case.get("expected_behavior")
    if expected is None:
        # Happy-path case — should NOT abstain
        return not response.get("abstained", False)

    if expected == "abstain":
        return response.get("abstained", False)
    elif expected == "answer":
        return not response.get("abstained", False)
    elif expected == "answer_or_abstain":
        return True  # Either is acceptable
    return True


# --- Failure Mode Classification ---


def classify_failure(
    response: dict,
    case: dict,
    retrieved_ids: list[str] | None = None,
) -> str | None:
    """Classify the failure mode. Returns None if no failure."""
    if case.get("expected_behavior") == "abstain":
        if not response.get("abstained"):
            return "should_have_abstained"
        return None

    if response.get("abstained"):
        return "over_abstain"

    expected_terms = case.get("expected_answer_contains", [])
    if expected_terms:
        answer = response.get("answer", "")
        if answer_contains(answer, expected_terms) < 0.5:
            # Check if it's a retrieval or generation issue
            if retrieved_ids is not None:
                expected_section = case.get("expected_section", "")
                if not any(expected_section in cid for cid in retrieved_ids[:10]):
                    return "not_in_corpus"
                elif not any(expected_section in cid for cid in retrieved_ids[:5]):
                    return "under_ranked"
            return "bad_generation"

    citations = response.get("citations", [])
    if not response.get("abstained") and not citations:
        return "missing_citations"

    return None


# --- Aggregate Report ---


class EvalReport:
    """Aggregates per-case results into a summary report."""

    def __init__(self) -> None:
        self.results: list[dict] = []

    def add(self, case: dict, response: dict, retrieved_ids: list[str] | None = None) -> None:
        failure = classify_failure(response, case, retrieved_ids)
        self.results.append({
            "id": case["id"],
            "category": case.get("category", ""),
            "abstention_correct": abstention_correct(response, case),
            "answer_coverage": answer_contains(
                response.get("answer", ""),
                case.get("expected_answer_contains", []),
            ),
            "has_citations": len(response.get("citations", [])) > 0,
            "failure_mode": failure,
        })

    def summary(self) -> dict:
        n = len(self.results)
        if n == 0:
            return {}

        happy = [r for r in self.results if not r["category"].startswith("adv")]
        adversarial = [r for r in self.results if r["category"] == "adversarial"]

        failures = {}
        for r in self.results:
            fm = r["failure_mode"]
            if fm:
                failures[fm] = failures.get(fm, 0) + 1

        return {
            "total_cases": n,
            "abstention_accuracy": sum(r["abstention_correct"] for r in self.results) / n,
            "happy_path_coverage": (
                sum(r["answer_coverage"] for r in happy) / len(happy) if happy else 0.0
            ),
            "adversarial_abstention_rate": (
                sum(1 for r in adversarial if r["abstention_correct"]) / len(adversarial)
                if adversarial else 0.0
            ),
            "citation_rate": sum(1 for r in happy if r["has_citations"]) / len(happy) if happy else 0.0,
            "failure_modes": failures,
        }

    def to_json(self, path: Path) -> None:
        output = {
            "summary": self.summary(),
            "per_case": self.results,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(output, f, indent=2)
        logger.info("Eval report written to %s", path)
