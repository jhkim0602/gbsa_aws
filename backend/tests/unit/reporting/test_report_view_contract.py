"""The report response and the published contract describe the same thing.

Nothing else checks this. ``get_report`` has no ``response_model`` and returns a plain dict, the
Lane D contract test only compares paths and operation ids, and the generator that used to diff
``openapi/`` against generated code was removed in ``7d977f7``. So a field added to the response
and forgotten in ``packages/contracts/openapi/root.yaml`` ships silently, leaving the published
contract describing an API that no longer exists.

This test closes that specific hole for the report response: every key the view emits has to
exist in ``ReportView``/``ReportItemView``/``AxisAssessmentView``/``ScoreBreakdown``, and those
schemas forbid additional properties, so the check runs both ways.
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import yaml
from interview_evidence.reporting.api.company_routes import _report_view
from interview_evidence.reporting.domain.report import (
    AssessmentState,
    AxisAssessment,
    Report,
    ReportItem,
    ReportKind,
    ReportStatus,
)

ROOT = Path(__file__).resolve().parents[4]
CONTRACT = ROOT / "packages/contracts/openapi/root.yaml"

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
EVIDENCE_ID = UUID("00000000-0000-7000-8000-000000000009")


def schemas() -> dict[str, Any]:
    document = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    return dict(document["components"]["schemas"])


def item(index: int, *, scored: bool, weight: float) -> ReportItem:
    axes = (
        (
            AxisAssessment(
                axis="depth",
                label="깊이",
                score=80,
                rationale="근거",
                quoted_evidence_ids=(EVIDENCE_ID,),
            ),
        )
        if scored
        else ()
    )
    return ReportItem(
        report_item_id=UUID(int=0x7000 + index),
        company_id=COMPANY_ID,
        report_id=UUID(int=2),
        criterion_id=UUID(int=0x8000 + index),
        competency_model_version_id=UUID(int=5),
        assessment_state=AssessmentState.INSUFFICIENT_EVIDENCE,
        observation="관찰",
        rationale="근거",
        sufficiency="insufficient",
        uncertainty="답변이 나오지 않았음",
        evidence=(),
        criterion_name=f"기준{index}",
        axis_assessments=axes,
        criterion_weight=weight,
        axis_weights={"depth": 100.0} if scored else {},
    )


def report() -> Report:
    return Report(
        report_id=UUID(int=2),
        company_id=COMPANY_ID,
        interview_session_id=UUID(int=3),
        invitation_id=UUID(int=4),
        version=1,
        kind=ReportKind.AI_ORIGINAL,
        model_version="m",
        prompt_version="p",
        config_version="c",
        status=ReportStatus.READY,
        summary="요약",
        created_at=datetime(2026, 8, 20, tzinfo=UTC),
        # One scored and one unreached, so the breakdown carries both a contribution and an
        # exclusion and every key in both shapes is exercised.
        items=(item(1, scored=True, weight=70.0), item(2, scored=False, weight=30.0)),
    )


def assert_keys_declared(value: Any, schema_name: str, available: dict[str, Any]) -> None:
    schema = available[schema_name]
    declared = set(schema["properties"])
    assert schema.get("additionalProperties") is False, (
        f"{schema_name} must forbid extra properties for this check to mean anything"
    )
    assert set(value) <= declared, f"{schema_name} is missing {sorted(set(value) - declared)}"


def test_every_report_response_key_is_declared_in_the_contract() -> None:
    available = schemas()
    view = _report_view(report(), ())

    assert_keys_declared(view, "ReportView", available)
    for item_view in view["items"]:  # type: ignore[union-attr]
        assert_keys_declared(item_view, "ReportItemView", available)
        for axis_view in item_view["axis_assessments"]:
            assert_keys_declared(axis_view, "AxisAssessmentView", available)
        assert_keys_declared(item_view["axis_breakdown"], "ScoreBreakdown", available)


def test_the_scoring_breakdown_matches_its_schema_including_the_joined_reasons() -> None:
    available = schemas()
    breakdown = _report_view(report(), ())["scoring_breakdown"]

    assert_keys_declared(breakdown, "ScoreBreakdown", available)
    for contribution in breakdown["contributions"]:  # type: ignore[index]
        assert_keys_declared(contribution, "ScoreContribution", available)
    for exclusion in breakdown["exclusions"]:  # type: ignore[index]
        assert_keys_declared(exclusion, "ScoreExclusion", available)

    # The exclusion carries its reason, which is the whole point of joining the items in.
    assert [exclusion["reason"] for exclusion in breakdown["exclusions"]] == [  # type: ignore[index]
        "답변이 나오지 않았음"
    ]


def test_the_divisor_reports_the_share_that_could_not_be_scored() -> None:
    breakdown = _report_view(report(), ())["scoring_breakdown"]

    assert round(breakdown["denominator"], 10) == 0.7  # type: ignore[index]
    assert round(breakdown["numerator"], 10) == 56.0  # type: ignore[index]
