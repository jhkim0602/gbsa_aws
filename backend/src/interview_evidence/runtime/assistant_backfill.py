from __future__ import annotations

import argparse
import os
from typing import cast
from uuid import UUID

from sqlalchemy import text

from interview_evidence.company_management.application.company_service import (
    CompanyManagementPublic,
)
from interview_evidence.main import Runtime
from interview_evidence.recruiting_assistant.application import (
    ASSISTANT_PROJECTION_VERSION,
    ReportSearchProjector,
)
from interview_evidence.reporting.api.company_routes import LaneDRuntime
from interview_evidence.shared.aws_clients.ports import TextEmbedder
from interview_evidence.shared.database import RequestScopedDatabase
from interview_evidence.shared.ids import new_uuid7
from interview_evidence.shared.tenant import ActorType, TenantContext


def backfill_missing_assistant_documents(runtime: Runtime, *, limit: int) -> int:
    if limit < 1:
        raise ValueError("assistant backfill limit must be positive")
    database = cast(RequestScopedDatabase, runtime.resources["database"])
    embedder = cast(TextEmbedder, runtime.resources["text_embedder"])
    projector = cast(ReportSearchProjector, runtime.resources["assistant_projector"])
    company = cast(CompanyManagementPublic, runtime.boundaries["company_management"])
    reporting = cast(LaneDRuntime, runtime.lanes["reporting"])
    token = database.begin_scope()
    try:
        rows = database.session.execute(
            text(
                """
                SELECT reports.company_id, reports.report_id
                FROM reports
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM assistant_retrieval_documents AS documents
                    WHERE documents.company_id = reports.company_id
                      AND documents.report_id = reports.report_id
                      AND documents.deleted_at IS NULL
                      AND documents.embedding_model = :embedding_model
                      AND documents.embedding_version = :embedding_version
                      AND documents.source_version = (
                          CAST(reports.version AS VARCHAR) || :projection_suffix
                      )
                )
                ORDER BY reports.created_at, reports.report_id
                LIMIT :limit
                """
            ),
            {
                "embedding_model": embedder.model_id,
                "embedding_version": embedder.embedding_version,
                "projection_suffix": f":{ASSISTANT_PROJECTION_VERSION}",
                "limit": limit,
            },
        ).tuples()
        projected = 0
        for company_id, report_id in rows:
            context = TenantContext(
                company_id=cast(UUID, company_id),
                actor_type=ActorType.SYSTEM,
                actor_id=UUID(int=0),
                request_id=new_uuid7(),
                trace_id="assistant-report-backfill",
            )
            report = reporting.repository.get_report(context, cast(UUID, report_id))
            subject = company.get_recruiting_assistant_subject(
                context,
                report.invitation_id,
            )
            projector.project(
                context,
                position_id=subject.position_id,
                position_title=subject.position_title,
                applicant_id=subject.applicant_id,
                applicant_display_name=subject.applicant_display_name,
                report=report,
            )
            projected += 1
        database.session.commit()
        return projected
    except BaseException:
        database.session.rollback()
        raise
    finally:
        database.end_scope(token)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill missing recruiting-assistant report search documents.",
    )
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()

    from interview_evidence.runtime.production import create_production_runtime

    runtime = create_production_runtime(os.environ)
    count = backfill_missing_assistant_documents(runtime, limit=args.limit)
    print(f"assistant report projections backfilled: {count}")


if __name__ == "__main__":
    main()
