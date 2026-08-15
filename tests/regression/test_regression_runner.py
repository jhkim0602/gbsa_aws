from tests.regression.run_regression import run_all


def test_fixed_regression_corpora_meet_all_thresholds() -> None:
    report = run_all()

    assert report["passed"] is True
    assert report["retrieval"]["recall_at_k"] >= 0.95
    assert report["questions"]["pass_rate"] == 1
    assert report["evidence"]["pass_rate"] == 1
    assert report["failed_cases"] == []
