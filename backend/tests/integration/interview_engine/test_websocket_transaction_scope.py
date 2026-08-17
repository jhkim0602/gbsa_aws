"""The websocket route must resolve the applicant principal inside a transaction scope.

The production principal provider reads the applicant session from Postgres, so a
route that calls it outside a scope raises RuntimeError and Starlette rejects the
handshake with HTTP 500 instead of the designed 4001/4003 close codes.
"""

from __future__ import annotations

import warnings
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import create_engine, text
from starlette.exceptions import StarletteDeprecationWarning

with warnings.catch_warnings():
    warnings.simplefilter("ignore", StarletteDeprecationWarning)
    from starlette.testclient import TestClient

from interview_evidence.interview_engine.api.websocket import (
    create_interview_websocket_router,
)
from interview_evidence.main import create_app
from interview_evidence.shared.database import RequestScopedDatabase
from interview_evidence.shared.security.principals import (
    ApplicantPrincipal,
    CompanyPrincipal,
    PrincipalNotFoundError,
)
from interview_evidence.shared.tenant import TenantContext

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000401")
INVITATION_ID = UUID("00000000-0000-7000-8000-000000000402")
APPLICANT_ID = UUID("00000000-0000-7000-8000-000000000403")
SESSION_ID = UUID("00000000-0000-7000-8000-000000000404")


class DatabaseBackedPrincipalProvider:
    """Mirrors the production provider: the lookup touches the request-scoped session."""

    def __init__(self, database: RequestScopedDatabase, *, credential: str) -> None:
        self._database = database
        self._credential = credential

    def get_company_principal(self, credential: str) -> CompanyPrincipal:
        raise PrincipalNotFoundError("company principal not found")

    def get_applicant_principal(self, credential: str) -> ApplicantPrincipal:
        # Any query is enough: the scope check fires before SQL is emitted.
        self._database.session.execute(text("SELECT 1"))
        if credential != self._credential:
            raise PrincipalNotFoundError("applicant principal not found")
        return ApplicantPrincipal(
            company_id=COMPANY_ID,
            invitation_id=INVITATION_ID,
            applicant_id=APPLICANT_ID,
            session_id=SESSION_ID,
        )


class RejectingStreamHandler:
    def authorize_connection(
        self,
        context: TenantContext,
        principal: ApplicantPrincipal,
        *,
        session_id: UUID,
    ) -> None:
        raise LookupError("interview session not found")


def _client(tmp_path: Path, *, credential: str) -> TestClient:
    database_file = tmp_path / "websocket-scope.db"
    database = RequestScopedDatabase(
        f"sqlite+pysqlite:///{database_file}",
        engine=create_engine(
            f"sqlite+pysqlite:///{database_file}",
            connect_args={"check_same_thread": False},
        ),
    )
    router = create_interview_websocket_router(
        principal_provider=DatabaseBackedPrincipalProvider(database, credential=credential),
        handler=RejectingStreamHandler(),
        database=database,
    )
    return TestClient(create_app([router]))


def test_authorization_failure_closes_with_the_designed_code(tmp_path: Path) -> None:
    client = _client(tmp_path, credential="applicant-session")
    client.cookies.set("iep_applicant_session", "applicant-session")

    with (
        pytest.raises(Exception) as failure,
        client.websocket_connect(
            f"/v1/applicant/interview-sessions/{SESSION_ID}/stream"
        ) as websocket,
    ):
        websocket.receive_json()

    # A raw HTTP 500 here means principal resolution ran outside a transaction scope.
    assert getattr(failure.value, "code", None) == 4003


def test_unknown_credential_closes_with_the_designed_code(tmp_path: Path) -> None:
    client = _client(tmp_path, credential="applicant-session")
    client.cookies.set("iep_applicant_session", "not-a-session")

    with (
        pytest.raises(Exception) as failure,
        client.websocket_connect(
            f"/v1/applicant/interview-sessions/{SESSION_ID}/stream"
        ) as websocket,
    ):
        websocket.receive_json()

    assert getattr(failure.value, "code", None) == 4001
