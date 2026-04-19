"""Tests for pairwise configuration evaluation."""

from clinguide.eval.harness import EvalReport
from clinguide.eval.pairwise import PairwiseEval


class TestPairwiseEval:
    def _make_report(self, coverage: float, abstain_correct: bool) -> EvalReport:
        report = EvalReport()
        report.add(
            {
                "id": "hp_001",
                "category": "dosage",
                "expected_answer_contains": ["80 mg"],
            },
            {
                "answer": "Take 80 mg daily" if coverage > 0 else "Unknown",
                "citations": [{"marker": "[^1]"}] if coverage > 0 else [],
                "abstained": False,
            },
        )
        report.add(
            {
                "id": "adv_001",
                "category": "adversarial",
                "expected_behavior": "abstain",
            },
            {
                "answer": "",
                "citations": [],
                "abstained": abstain_correct,
            },
        )
        return report

    def test_comparison_table(self):
        pe = PairwiseEval()
        pe.add_config("config_a", self._make_report(1.0, True))
        pe.add_config("config_b", self._make_report(0.0, True))

        table = pe.comparison_table()
        assert "config_a" in table
        assert "config_b" in table
        assert "happy_path_coverage" in table

    def test_needs_two_configs(self):
        pe = PairwiseEval()
        pe.add_config("only_one", self._make_report(1.0, True))
        assert "Need at least 2" in pe.comparison_table()
