from __future__ import annotations

import smtplib
from collections.abc import Mapping
from dataclasses import replace
from email.message import EmailMessage
from html import escape
from typing import Protocol, cast
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from interview_evidence.main import LocalRuntime
from interview_evidence.runtime.aws import AwsRuntimeDependencies, create_aws_runtime_dependencies
from interview_evidence.runtime.production import create_production_runtime
from interview_evidence.shared.aws_clients.ports import (
    DeterministicSpeechToText,
    DeterministicTextToSpeech,
)
from interview_evidence.shared.database import RequestScopedDatabase
from interview_evidence.shared.operations import DependencyReadiness, NullMetricRecorder
from interview_evidence.shared.security.principals import (
    ApplicantPrincipal,
    CompanyPrincipal,
    PrincipalNotFoundError,
    PrincipalProvider,
)
from interview_evidence.shared.tenant import TenantContext, require_tenant_context
from interview_evidence.workers.analysis.document_extract import (
    DeterministicTextract,
    TextractPage,
)

LOCAL_COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
LOCAL_COMPANY_USER_ID = UUID("00000000-0000-7000-8000-000000000002")


class LocalCompanyPrincipalProvider(PrincipalProvider):
    def __init__(
        self,
        *,
        token: str,
        company_id: UUID = LOCAL_COMPANY_ID,
        company_user_id: UUID = LOCAL_COMPANY_USER_ID,
    ) -> None:
        if len(token) < 8:
            raise ValueError("local company token must contain at least 8 characters")
        self._token = token
        self._principal = CompanyPrincipal(
            company_id=company_id,
            company_user_id=company_user_id,
            identity_subject="local-production-company-user",
        )

    def get_company_principal(self, credential: str) -> CompanyPrincipal:
        if credential != self._token:
            raise PrincipalNotFoundError("company principal not found")
        return self._principal

    def get_applicant_principal(self, credential: str) -> ApplicantPrincipal:
        del credential
        raise PrincipalNotFoundError("applicant principal not found")


class LocalSmtpEmailSender:
    def __init__(self, *, host: str, port: int, from_address: str) -> None:
        self._host = host
        self._port = port
        self._from_address = from_address

    def send_template(
        self,
        context: TenantContext,
        template_id: str,
        recipient_ref: UUID,
        recipient_address: str,
        template_data: Mapping[str, object],
    ) -> UUID:
        require_tenant_context(context)
        message_id = f"<{uuid4()}@local.interview-evidence.test>"
        invitation_url = escape(str(template_data.get("invitation_url", "")))
        message = EmailMessage()
        message["Message-ID"] = message_id
        message["From"] = self._from_address
        message["To"] = recipient_address
        message["Subject"] = "Interview invitation"
        message["X-IEP-Template"] = template_id
        message["X-IEP-Recipient-Ref"] = str(recipient_ref)
        message.set_content("Open the HTML version of this invitation.")
        message.add_alternative(
            (
                "<p>Your interview invitation is ready.</p>"
                f'<p><a href="{invitation_url}">Open invitation</a></p>'
            ),
            subtype="html",
        )
        with smtplib.SMTP(self._host, self._port, timeout=5) as smtp:
            smtp.send_message(message)
        return uuid5(NAMESPACE_URL, message_id)


class LocalDeterministicModel:
    def generate(
        self,
        context: TenantContext,
        model_input: Mapping[str, object],
    ) -> Mapping[str, object]:
        require_tenant_context(context)
        if model_input.get("task") == "next_interview_question":
            criterion_id = str(model_input["target_criterion_id"])
            raw_context = model_input.get("context")
            source_ids: tuple[str, ...] = ()
            if isinstance(raw_context, Mapping):
                raw_sources = raw_context.get("retrieved_sources")
                if isinstance(raw_sources, list):
                    source_ids = tuple(
                        str(item["source_id"])
                        for item in raw_sources
                        if isinstance(item, Mapping) and "source_id" in item
                    )[:1]
            return {
                "text": "방금 설명한 선택에서 가장 중요한 트레이드오프를 말씀해 주세요.",
                "target_criterion_id": criterion_id,
                "source_reference_ids": source_ids,
            }
        raw_criteria = model_input.get("criterion_ids")
        criterion_ids = (
            tuple(str(value) for value in raw_criteria)
            if isinstance(raw_criteria, list | tuple)
            else ()
        )
        raw_sources = model_input.get("source_candidates", ())
        source_ids = (
            tuple(
                str(item["source_id"])
                for item in raw_sources
                if isinstance(item, Mapping) and "source_id" in item
            )
            if isinstance(raw_sources, list | tuple)
            else ()
        )
        return {
            "verification_points": [
                {
                    "criterion_id": criterion_id,
                    "prompt": "구체적인 역할과 판단 근거를 확인합니다.",
                    "source_ids": list(source_ids[:1]),
                }
                for criterion_id in criterion_ids
            ],
            "common_topics": ["역할", "판단 근거", "트레이드오프"],
            "follow_up_directions": {
                criterion_id: ["구체적인 상황과 결과를 확인합니다."]
                for criterion_id in criterion_ids
            },
            "time_budget": {criterion_id: 180 for criterion_id in criterion_ids},
            "required_evidence_plan": {criterion_id: 1 for criterion_id in criterion_ids},
        }


class LocalMediaConvert:
    def create_hls_job(
        self,
        context: TenantContext,
        *,
        input_key: str,
        output_prefix: str,
    ) -> str:
        tenant = require_tenant_context(context)
        return str(
            uuid5(
                tenant.company_id,
                f"{input_key}:{output_prefix}",
            )
        )


class HealthcheckPort(Protocol):
    def healthcheck(self) -> None: ...


def create_local_aws_runtime_dependencies(
    environment: Mapping[str, str],
) -> AwsRuntimeDependencies:
    aws = create_aws_runtime_dependencies(environment)
    return replace(
        aws,
        principal_provider=LocalCompanyPrincipalProvider(
            token=_required(environment, "LOCAL_COMPANY_TOKEN"),
            company_id=UUID(environment.get("LOCAL_COMPANY_ID", str(LOCAL_COMPANY_ID))),
            company_user_id=UUID(
                environment.get("LOCAL_COMPANY_USER_ID", str(LOCAL_COMPANY_USER_ID))
            ),
        ),
        email_sender=LocalSmtpEmailSender(
            host=_required(environment, "SMTP_HOST"),
            port=int(_required(environment, "SMTP_PORT")),
            from_address=_required(environment, "SES_FROM_ADDRESS"),
        ),
        model=LocalDeterministicModel(),
        speech_to_text=DeterministicSpeechToText(
            {"text": "로컬 테스트 최종 답변", "confidence": 0.99}
        ),
        text_to_speech=DeterministicTextToSpeech(
            {
                "audio_url": None,
                "audio_expires_at": None,
                "speech_marks_url": None,
            }
        ),
        textract=DeterministicTextract(
            (
                TextractPage(
                    page_number=1,
                    lines=(
                        "로컬 production parity 문서입니다.",
                        "설계 선택과 트레이드오프를 설명합니다.",
                    ),
                ),
            )
        ),
        media_convert=LocalMediaConvert(),
        metrics=NullMetricRecorder(),
    )


def create_local_production_runtime(environment: Mapping[str, str]) -> LocalRuntime:
    aws = create_local_aws_runtime_dependencies(environment)
    database = RequestScopedDatabase(aws.database_url)
    readiness = DependencyReadiness(
        {
            "database": database.healthcheck,
            "object_storage": cast(HealthcheckPort, aws.object_storage).healthcheck,
            "media_storage": cast(HealthcheckPort, aws.media_storage).healthcheck,
            "recent_context": cast(HealthcheckPort, aws.recent_context).healthcheck,
            "search": cast(HealthcheckPort, aws.search_index).healthcheck,
            **{f"{name}_queue": queue.healthcheck for name, queue in aws.queues.items()},
        }
    )
    return create_production_runtime(
        environment,
        principal_provider=aws.principal_provider,
        object_storage=aws.object_storage,
        media_storage=aws.media_storage,
        email_sender=aws.email_sender,
        recent_context=aws.recent_context,
        search_index=aws.search_index,
        database=database,
        metrics=aws.metrics,
        readiness=readiness,
        queues=aws.queues,
        model=aws.model,
        speech_to_text=aws.speech_to_text,
        text_to_speech=aws.text_to_speech,
    )


def _required(environment: Mapping[str, str], name: str) -> str:
    value = environment.get(name)
    if value is None or not value.strip():
        raise RuntimeError(f"required local production setting is missing: {name}")
    return value.strip()
