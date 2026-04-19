"""Tests for the evaluation harness metrics."""

from clinguide.eval.harness import (
    precision_at_k,
    recall_at_k,
    mrr,
    answer_contains,
    abstention_correct,
    classify_failure,
    EvalReport,
    load_cases,
)


class TestRetrievalMetrics:
    def test_precision_at_k_perfect(self):
        assert precision_at_k(["a", "b", "c"], ["a", "b", "c"], k=3) == 1.0

    def test_precision_at_k_partial(self):
        assert precision_at_k(["a", "x", "y"], ["a", "b"], k=3) == 1 / 3

    def test_precision_at_k_none(self):
        assert precision_at_k(["x", "y", "z"], ["a", "b"], k=3) == 0.0

    def test_recall_at_k_perfect(self):
        assert recall_at_k(["a", "b", "c"], ["a", "b"], k=3) == 1.0

    def test_recall_at_k_partial(self):
        assert recall_at_k(["a", "x", "y"], ["a", "b"], k=3) == 0.5

    def test_recall_empty_expected(self):
        assert recall_at_k(["a", "b"], [], k=3) == 1.0

    def test_mrr_first(self):
        assert mrr(["a", "b", "c"], ["a"]) == 1.0

    def test_mrr_second(self):
        assert mrr(["x", "a", "c"], ["a"]) == 0.5

    def test_mrr_not_found(self):
        assert mrr(["x", "y", "z"], ["a"]) == 0.0


class TestGenerationMetrics:
    def test_answer_contains_all(self):
        assert answer_contains("80 mg once daily oral", ["80 mg", "once daily"]) == 1.0

    def test_answer_contains_partial(self):
        assert answer_contains("80 mg oral", ["80 mg", "once daily"]) == 0.5

    def test_answer_contains_empty(self):
        assert answer_contains("anything", []) == 1.0

    def test_answer_contains_case_insensitive(self):
        assert answer_contains("OSIMERTINIB 80 MG", ["osimertinib", "80 mg"]) == 1.0


class TestAbstention:
    def test_happy_path_no_abstain(self):
        assert abstention_correct({"abstained": False}, {"id": "hp_001"}) is True

    def test_happy_path_wrong_abstain(self):
        assert abstention_correct({"abstained": True}, {"id": "hp_001"}) is False

    def test_adversarial_correct_abstain(self):
        case = {"expected_behavior": "abstain"}
        assert abstention_correct({"abstained": True}, case) is True

    def test_adversarial_wrong_answer(self):
        case = {"expected_behavior": "abstain"}
        assert abstention_correct({"abstained": False}, case) is False


class TestFailureClassification:
    def test_no_failure(self):
        response = {"answer": "80 mg once daily", "citations": [{"marker": "[^1]"}], "abstained": False}
        case = {"expected_answer_contains": ["80 mg"], "id": "hp_001"}
        assert classify_failure(response, case) is None

    def test_over_abstain(self):
        response = {"abstained": True, "answer": ""}
        case = {"expected_answer_contains": ["80 mg"], "id": "hp_001"}
        assert classify_failure(response, case) == "over_abstain"

    def test_should_have_abstained(self):
        response = {"abstained": False, "answer": "Here's the recipe"}
        case = {"expected_behavior": "abstain"}
        assert classify_failure(response, case) == "should_have_abstained"


class TestEvalReport:
    def test_summary(self):
        report = EvalReport()
        report.add(
            {"id": "hp_001", "category": "dosage", "expected_answer_contains": ["80 mg"]},
            {"answer": "Take 80 mg daily", "citations": [{"marker": "[^1]"}], "abstained": False},
        )
        report.add(
            {"id": "adv_001", "category": "adversarial", "expected_behavior": "abstain"},
            {"answer": "", "citations": [], "abstained": True},
        )
        summary = report.summary()
        assert summary["total_cases"] == 2
        assert summary["abstention_accuracy"] == 1.0


class TestLoadCases:
    def test_load_cases(self):
        cases = load_cases()
        assert len(cases) == 40  # 30 happy-path + 10 adversarial
        assert cases[0]["id"] == "hp_001"
        assert cases[-1]["id"] == "adv_010"
