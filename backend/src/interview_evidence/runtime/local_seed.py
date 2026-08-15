from __future__ import annotations

import os
from collections.abc import Mapping
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from interview_evidence.company_management.api import ensure_company_principal


def seed_local_company(environment: Mapping[str, str] | None = None) -> None:
    values = dict(os.environ if environment is None else environment)
    engine = create_engine(_required(values, "DATABASE_URL"), pool_pre_ping=True)
    with Session(engine) as session:
        ensure_company_principal(
            session,
            company_id=UUID(_required(values, "LOCAL_COMPANY_ID")),
            company_user_id=UUID(_required(values, "LOCAL_COMPANY_USER_ID")),
            company_name=values.get(
                "LOCAL_COMPANY_NAME",
                "Local Interview Evidence Company",
            ),
            identity_subject="local-production-company-user",
            email_normalized=values.get(
                "LOCAL_COMPANY_EMAIL",
                "local-company@example.test",
            ),
            now=datetime.now(UTC),
        )
        session.commit()


def _required(environment: Mapping[str, str], name: str) -> str:
    value = environment.get(name)
    if value is None or not value.strip():
        raise RuntimeError(f"required local seed setting is missing: {name}")
    return value.strip()


def main() -> None:
    seed_local_company()


if __name__ == "__main__":
    main()
