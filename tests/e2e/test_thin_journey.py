from tests.e2e.support import run_thin_journey


def test_company_to_human_decision_thin_journey() -> None:
    result = run_thin_journey()

    assert result.analysis_ready is True
    assert result.answer_turn_id != result.question_turn_id
    assert result.question_source_reference_count >= 1
    assert result.evidence_answer_turn_id == result.answer_turn_id
    assert result.human_decision == "hold"
    assert {
        result.campaign_criterion_version_id,
        result.strategy_criterion_version_id,
        result.session_criterion_version_id,
        result.report_criterion_version_id,
    } == {result.campaign_criterion_version_id}
