from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import httpx
import pytest
from interview_evidence.main import create_app
from interview_evidence.shared.database import RequestScopedDatabase
from interview_evidence.shared.messaging.outbox import OutboxEvent, ProcessedMessage
from interview_evidence.shared.persistence import (
    Base,
    SQLApplicantSessionStore,
    SQLAuditAppender,
    SQLCommandIdempotencyStore,
    SQLOutbox,
    SQLProcessedMessageStore,
    SQLUploadIntentStore,
)
from interview_evidence.shared.security.principals import ApplicantPrincipal
from interview_evidence.shared.tenant import ActorType, TenantContext
from interview_evidence.shared.uploads import StoredUploadIntent
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
APPLICANT_ID = UUID("00000000-0000-7000-8000-000000000002")
INVITATION_ID = UUID("00000000-0000-7000-8000-000000000003")
SESSION_ID = UUID("00000000-0000-7000-8000-000000000004")
EVENT_ID = UUID("00000000-0000-7000-8000-000000000005")
RESOURCE_ID = UUID("00000000-0000-7000-8000-000000000006")


def _context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.APPLICANT,
        actor_id=APPLICANT_ID,
        request_id=UUID("00000000-0000-7000-8000-000000000007"),
        trace_id="production-persistence-test",
    )


def test_shared_runtime_state_survives_store_recreation(tmp_path: Path) -> None:
    database = tmp_path / "runtime.db"
    engine = create_engine(f"sqlite+pysqlite:///{database}")
    Base.metadata.create_all(engine)
    now = datetime(2026, 8, 15, tzinfo=UTC)

    with Session(engine) as session:
        outbox = SQLOutbox(session)
        processed = SQLProcessedMessageStore(session)
        audit = SQLAuditAppender(session)
        applicant_sessions = SQLApplicantSessionStore(session)
        uploads = SQLUploadIntentStore(session)
        idempotency = SQLCommandIdempotencyStore(session)

        outbox.append(
            OutboxEvent(
                outbox_event_id=EVENT_ID,
                company_id=COMPANY_ID,
                aggregate_type="submission",
                aggregate_id=RESOURCE_ID,
                aggregate_version=1,
                event_type="submission.analysis_requested",
                event_version=1,
                payload={"submission_id": str(RESOURCE_ID)},
                idempotency_key="production-outbox-0001",
                trace_id="production-persistence-test",
                occurred_at=now,
            )
        )
        processed.record(
            ProcessedMessage(
                consumer_name="analysis-worker",
                event_id=EVENT_ID,
                event_version=1,
                idempotency_key="production-outbox-0001",
                first_processed_at=now,
                outcome_digest="ready",
            )
        )
        audit.append(
            _context(),
            action="submission.view",
            resource_type="submission",
            resource_id=RESOURCE_ID,
            result="allowed",
            metadata={"version": 1},
        )
        applicant_sessions.save_token(
            token_hash="a" * 64,
            company_id=COMPANY_ID,
            invitation_id=INVITATION_ID,
            applicant_id=APPLICANT_ID,
            expires_at=now + timedelta(hours=1),
        )
        applicant_sessions.consume_token("a" * 64, consumed_at=now)
        applicant_sessions.save_session(
            session_hash="b" * 64,
            principal=ApplicantPrincipal(
                company_id=COMPANY_ID,
                invitation_id=INVITATION_ID,
                applicant_id=APPLICANT_ID,
                session_id=SESSION_ID,
            ),
            expires_at=now + timedelta(hours=1),
        )
        uploads.save(
            StoredUploadIntent(
                upload_id=RESOURCE_ID,
                company_id=COMPANY_ID,
                invitation_id=INVITATION_ID,
                applicant_id=APPLICANT_ID,
                source_type="resume",
                original_filename="resume.pdf",
                media_type="application/pdf",
                byte_size=1024,
                sha256="c" * 64,
                object_key=f"tenants/{COMPANY_ID}/resume/{RESOURCE_ID}",
                method="PUT",
                url="https://uploads.example.invalid/presigned",
                required_headers={"content-type": "application/pdf"},
                expires_at=now + timedelta(minutes=15),
            )
        )
        idempotency.put(
            _context(),
            operation="submission.register",
            idempotency_key="production-command-0001",
            resource_id=RESOURCE_ID,
        )
        session.commit()

    with Session(engine) as session:
        assert SQLOutbox(session).pending()[0].outbox_event_id == EVENT_ID
        assert SQLProcessedMessageStore(session).contains(
            consumer_name="analysis-worker",
            event_id=EVENT_ID,
            event_version=1,
        )
        assert SQLAuditAppender(session).count_for_company(COMPANY_ID) == 1
        principal = SQLApplicantSessionStore(session).get_session("b" * 64, now=now)
        assert principal is not None and principal.session_id == SESSION_ID
        assert SQLUploadIntentStore(session).get(_context(), RESOURCE_ID, APPLICANT_ID) is not None
        assert (
            SQLCommandIdempotencyStore(session).get(
                _context(),
                operation="submission.register",
                idempotency_key="production-command-0001",
            )
            == RESOURCE_ID
        )


@pytest.mark.anyio
async def test_http_transaction_commits_or_rolls_back_shared_state(
    tmp_path: Path,
) -> None:
    database = tmp_path / "requests.db"
    engine = create_engine(
        f"sqlite+pysqlite:///{database}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    registry = RequestScopedDatabase(
        f"sqlite+pysqlite:///{database}",
        engine=engine,
    )
    application = create_app()
    registry.install_http_transaction_middleware(application)
    now = datetime(2026, 8, 15, tzinfo=UTC)

    @application.post("/test/transaction/{outcome}")
    def persist(outcome: str) -> dict[str, str]:
        SQLOutbox(registry.session).append(
            OutboxEvent(
                outbox_event_id=EVENT_ID,
                company_id=COMPANY_ID,
                aggregate_type="submission",
                aggregate_id=RESOURCE_ID,
                aggregate_version=1,
                event_type="submission.analysis_requested",
                event_version=1,
                payload={"submission_id": str(RESOURCE_ID)},
                idempotency_key=f"transaction-{outcome}",
                trace_id="transaction-test",
                occurred_at=now,
            )
        )
        if outcome == "rollback":
            raise RuntimeError("force rollback")
        return {"status": "committed"}

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        assert (await client.post("/test/transaction/commit")).status_code == 200
        assert (await client.post("/test/transaction/rollback")).status_code == 500

    with Session(engine) as session:
        events = SQLOutbox(session).pending()
        assert tuple(event.idempotency_key for event in events) == ("transaction-commit",)
