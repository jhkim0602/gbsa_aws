from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
CRITERION_VERSION_ID = UUID("00000000-0000-7000-8000-000000000010")
CRITERION_ID = UUID("00000000-0000-7000-8000-000000000011")
INVITATION_ID = UUID("00000000-0000-7000-8000-000000000020")
APPLICANT_ID = UUID("00000000-0000-7000-8000-000000000021")
STRATEGY_ID = UUID("00000000-0000-7000-8000-000000000030")
SESSION_ID = UUID("00000000-0000-7000-8000-000000000040")
REPORT_ID = UUID("00000000-0000-7000-8000-000000000050")

Fixture = dict[str, Any]


def tenant_fixture() -> Fixture:
    return {
        "company_id": COMPANY_ID,
        "actor_type": "system",
        "actor_id": UUID("00000000-0000-7000-8000-000000000002"),
        "request_id": UUID("00000000-0000-7000-8000-000000000003"),
        "trace_id": "fixture-trace",
    }


def criterion_fixture(tenant: Fixture | None = None) -> Fixture:
    scope = tenant or tenant_fixture()
    return {
        "company_id": scope["company_id"],
        "criterion_version_id": CRITERION_VERSION_ID,
        "criterion_id": CRITERION_ID,
        "version": 1,
        "name": "문제 해결",
        "description": "근거를 바탕으로 설계 선택과 결과를 설명한다.",
        "weight": 1.0,
        "required": True,
        "status": "published",
    }


def invitation_fixture(
    tenant: Fixture | None = None,
    criterion: Fixture | None = None,
) -> Fixture:
    scope = tenant or tenant_fixture()
    criterion_snapshot = criterion or criterion_fixture(scope)
    return {
        "company_id": scope["company_id"],
        "invitation_id": INVITATION_ID,
        "applicant_id": APPLICANT_ID,
        "criterion_version_id": criterion_snapshot["criterion_version_id"],
        "status": "consented",
        "expires_at": datetime(2026, 8, 22, tzinfo=UTC),
        "consent_purposes": ["analysis", "recording", "assessment"],
    }


def strategy_fixture(
    tenant: Fixture | None = None,
    invitation: Fixture | None = None,
    criterion: Fixture | None = None,
) -> Fixture:
    scope = tenant or tenant_fixture()
    criterion_snapshot = criterion or criterion_fixture(scope)
    invitation_snapshot = invitation or invitation_fixture(scope, criterion_snapshot)
    return {
        "company_id": scope["company_id"],
        "strategy_id": STRATEGY_ID,
        "strategy_version": 1,
        "invitation_id": invitation_snapshot["invitation_id"],
        "criterion_version_id": criterion_snapshot["criterion_version_id"],
        "status": "ready",
        "time_budget_seconds": 1800,
        "criterion_ids": [criterion_snapshot["criterion_id"]],
    }


def session_fixture(
    tenant: Fixture | None = None,
    invitation: Fixture | None = None,
    strategy: Fixture | None = None,
) -> Fixture:
    scope = tenant or tenant_fixture()
    invitation_snapshot = invitation or invitation_fixture(scope)
    strategy_snapshot = strategy or strategy_fixture(scope, invitation_snapshot)
    return {
        "company_id": scope["company_id"],
        "interview_session_id": SESSION_ID,
        "invitation_id": invitation_snapshot["invitation_id"],
        "strategy_id": strategy_snapshot["strategy_id"],
        "state": "completed",
        "session_sequence": 8,
        "last_final_turn_id": UUID("00000000-0000-7000-8000-000000000041"),
    }


def report_fixture(
    tenant: Fixture | None = None,
    session: Fixture | None = None,
    criterion: Fixture | None = None,
) -> Fixture:
    scope = tenant or tenant_fixture()
    criterion_snapshot = criterion or criterion_fixture(scope)
    session_snapshot = session or session_fixture(scope)
    return {
        "company_id": scope["company_id"],
        "report_id": REPORT_ID,
        "report_version": 1,
        "interview_session_id": session_snapshot["interview_session_id"],
        "criterion_version_id": criterion_snapshot["criterion_version_id"],
        "status": "ready",
        "human_decision_status": "pending",
    }


def fixture_bundle() -> Fixture:
    tenant = tenant_fixture()
    criterion = criterion_fixture(tenant)
    invitation = invitation_fixture(tenant, criterion)
    strategy = strategy_fixture(tenant, invitation, criterion)
    session = session_fixture(tenant, invitation, strategy)
    report = report_fixture(tenant, session, criterion)
    return {
        "tenant": tenant,
        "criterion": criterion,
        "invitation": invitation,
        "strategy": strategy,
        "session": session,
        "report": report,
    }


def main() -> None:
    print(json.dumps(fixture_bundle(), default=str, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
