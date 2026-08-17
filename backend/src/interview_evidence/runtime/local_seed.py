from __future__ import annotations

import os
from collections.abc import Mapping
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from interview_evidence.company_management.api import (
    ensure_company_principal,
    ensure_local_demo_recruiting,
)
from interview_evidence.interview_engine.api import ensure_local_demo_interview_session
from interview_evidence.reporting.api import (
    LocalDemoAnswerRange,
    ensure_local_demo_review_projections,
)


def seed_local_company(environment: Mapping[str, str] | None = None) -> None:
    values = dict(os.environ if environment is None else environment)
    engine = create_engine(_required(values, "DATABASE_URL"), pool_pre_ping=True)
    with Session(engine) as session:
        company_id = UUID(_required(values, "LOCAL_COMPANY_ID"))
        company_user_id = UUID(_required(values, "LOCAL_COMPANY_USER_ID"))
        now = datetime.now(UTC)
        ensure_company_principal(
            session,
            company_id=company_id,
            company_user_id=company_user_id,
            company_name=values.get(
                "LOCAL_COMPANY_NAME",
                "Local Interview Evidence Company",
            ),
            identity_subject="local-production-company-user",
            email_normalized=values.get(
                "LOCAL_COMPANY_EMAIL",
                "local-company@example.test",
            ),
            now=now,
        )
        if _enabled(values.get("LOCAL_DEMO_DATA_ENABLED")):
            demo = ensure_local_demo_recruiting(
                session,
                company_id=company_id,
                company_user_id=company_user_id,
                now=now,
            )
            # The reviewed applicant gets a finished interview and its review projections
            # so the local console has one row where 검토 시작 actually opens something.
            # Both helpers live in the lane that owns the tables; this only sequences them.
            interview = ensure_local_demo_interview_session(
                session,
                company_id=company_id,
                company_user_id=company_user_id,
                invitation_id=demo.reviewed_invitation_id,
                applicant_id=demo.reviewed_applicant_id,
                competency_model_version_id=demo.competency_model_version_id,
                criterion_id=demo.criterion_id,
                interview_strategy_id=uuid5(
                    NAMESPACE_URL,
                    f"local-interview-demo-strategy:{demo.reviewed_invitation_id}",
                ),
                now=now,
            )
            ensure_local_demo_review_projections(
                session,
                company_id=company_id,
                company_user_id=company_user_id,
                interview_session_id=interview.interview_session_id,
                invitation_id=demo.reviewed_invitation_id,
                competency_model_version_id=demo.competency_model_version_id,
                criterion_id=demo.criterion_id,
                criterion_name=demo.criterion_name,
                answers=tuple(
                    LocalDemoAnswerRange(
                        turn_id=answer.turn_id,
                        question_turn_id=answer.question_turn_id,
                        question_text=answer.question_text,
                        answer_text=answer.answer_text,
                        session_start_ms=answer.session_start_ms,
                        session_end_ms=answer.session_end_ms,
                    )
                    for answer in interview.answers
                ),
                recording_object_key=interview.recording_object_key,
                recording_duration_ms=interview.recording_duration_ms,
                now=now,
            )
        session.commit()


def _required(environment: Mapping[str, str], name: str) -> str:
    value = environment.get(name)
    if value is None or not value.strip():
        raise RuntimeError(f"required local seed setting is missing: {name}")
    return value.strip()


def _enabled(value: str | None) -> bool:
    return value is not None and value.strip().lower() in {"1", "true", "yes", "on"}


def main() -> None:
    seed_local_company()


if __name__ == "__main__":
    main()
