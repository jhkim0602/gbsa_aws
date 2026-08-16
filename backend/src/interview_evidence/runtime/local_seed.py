from __future__ import annotations

import os
from collections.abc import Mapping
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from interview_evidence.company_management.api import (
    ensure_company_principal,
    ensure_local_demo_recruiting,
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
            ensure_local_demo_recruiting(
                session,
                company_id=company_id,
                company_user_id=company_user_id,
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
