from pathlib import Path
from typing import cast

import pytest
from interview_evidence.reporting.api.company_routes import LaneDRuntime
from interview_evidence.reporting.application.review_service import ReviewService
from interview_evidence.reporting.domain.review import Decision
from interview_evidence.shared.tenant import ActorType

from tests.e2e.support import run_thin_journey

ROOT = Path(__file__).parents[2]


def test_ai_and_workers_have_no_final_decision_path_or_nonverbal_scoring() -> None:
    forbidden_terms = (
        "facial_emotion",
        "emotion_score",
        "eye_contact_score",
        "voice_confidence_score",
        "nonverbal_score",
    )
    production_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "backend" / "src" / "interview_evidence").rglob("*.py")
    ).casefold()
    worker_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "backend" / "src" / "interview_evidence" / "workers").rglob("*.py")
    ).casefold()

    assert not any(term in production_text for term in forbidden_terms)
    assert "record_final_decision" not in worker_text
    assert "final_decision" not in worker_text


def test_final_decision_rejects_non_human_actor_at_runtime() -> None:
    result = run_thin_journey()
    lane_d = cast(LaneDRuntime, result.runtime.lanes["reporting"])
    report = lane_d.repository.get_report(
        result.company_context,
        result.report_id,
    )
    system_context = result.company_context.model_copy(update={"actor_type": ActorType.SYSTEM})

    with pytest.raises(PermissionError):
        ReviewService(lane_d.repository).record_final_decision(
            system_context,
            report_id=report.report_id,
            invitation_id=result.invitation_id,
            decision=Decision.ADVANCE,
            reason="AI가 결정해서는 안 된다.",
            occurred_at=result.runtime.resources["clock"].now(),
        )
