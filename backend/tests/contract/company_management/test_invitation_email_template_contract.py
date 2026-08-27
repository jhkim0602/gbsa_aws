from datetime import UTC, datetime
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from interview_evidence.company_management.api import create_lane_a_app
from interview_evidence.company_management.domain.company import MAX_LOGO_BYTES, Company
from interview_evidence.company_management.repositories.postgres import (
    InMemoryCompanyRepository,
)
from interview_evidence.shared.audit import InMemoryAuditAppender
from interview_evidence.shared.ids import FrozenClock
from interview_evidence.shared.security.principals import (
    CompanyPrincipal,
    FakePrincipalProvider,
)
from interview_evidence.shared.tenant import ActorType, TenantContext

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
COMPANY_USER_ID = UUID("00000000-0000-7000-8000-000000000002")
NOW = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)
AUTH = {"Authorization": "Bearer company-token"}
LOGO_BASE_URL = "https://console.example"
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"logo-pixels"

TEMPLATE_PAYLOAD = {
    "subject": "[{{회사명}}] {{포지션명}} 면접 안내",
    "headline": "서류 전형 합격을 축하드립니다",
    "intro": "{{지원자명}}님, 지원해주셔서 감사합니다.",
    "guides": ["소요 시간 | 약 25분"],
    "cta_label": "면접 시작하기",
    "outro": "좋은 결과로 만나뵙기를 기대합니다.",
    "footer": "본 메일은 발신 전용입니다",
    "brand_color": "#0F766E",
    "use_applicant_name": True,
    "emphasize_deadline": True,
    "show_security_notice": True,
}


def _context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.COMPANY_USER,
        actor_id=COMPANY_USER_ID,
        request_id=UUID("00000000-0000-7000-8000-000000000003"),
        trace_id="invitation-email-template-contract",
    )


def _app() -> object:
    repository = InMemoryCompanyRepository()
    repository.save_company(
        _context(),
        Company(company_id=COMPANY_ID, name="넥스트하이어", created_at=NOW, updated_at=NOW),
    )
    return create_lane_a_app(
        principal_provider=FakePrincipalProvider(
            company_principals={
                "company-token": CompanyPrincipal(
                    company_id=COMPANY_ID,
                    company_user_id=COMPANY_USER_ID,
                    identity_subject="oidc|company-user",
                )
            }
        ),
        repository=repository,
        audit=InMemoryAuditAppender(),
        clock=FrozenClock(NOW),
        logo_base_url=LOGO_BASE_URL,
    )


async def _create_position(client: AsyncClient) -> str:
    created = await client.post(
        "/v1/positions",
        headers={**AUTH, "Idempotency-Key": "invitation-template-position"},
        json={"title": "백엔드 엔지니어", "description": "서비스 개발"},
    )
    assert created.status_code == 201
    return str(created.json()["position_id"])


@pytest.mark.asyncio
async def test_company_template_defaults_then_persists_company_edits() -> None:
    app = _app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://testserver") as (
        client
    ):
        default = await client.get("/v1/invitation-email-template", headers=AUTH)
        saved = await client.put(
            "/v1/invitation-email-template",
            headers=AUTH,
            json=TEMPLATE_PAYLOAD,
        )
        reread = await client.get("/v1/invitation-email-template", headers=AUTH)
        reverted = await client.delete("/v1/invitation-email-template", headers=AUTH)

    assert default.status_code == 200
    assert default.json()["headline"] == "지원해주셔서 감사합니다"
    assert default.json()["is_position_override"] is False
    assert default.json()["logo_url"] is None

    assert saved.status_code == 200
    assert reread.json() == saved.json()
    # Colours are normalised so the stored value is what the renderer emits.
    assert reread.json()["brand_color"] == "#0f766e"
    assert reread.json()["guides"] == ["소요 시간 | 약 30분 (중간 저장되며 이어서 진행 가능)"]

    # Reverting hands the platform default back, so the console never has to hold its
    # own copy of the Korean wording.
    assert reverted.status_code == 200
    assert reverted.json() == default.json()


@pytest.mark.asyncio
async def test_position_template_inherits_overrides_then_reverts() -> None:
    app = _app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://testserver") as (
        client
    ):
        position_id = await _create_position(client)
        await client.put("/v1/invitation-email-template", headers=AUTH, json=TEMPLATE_PAYLOAD)

        inherited = await client.get(
            f"/v1/positions/{position_id}/invitation-email-template",
            headers=AUTH,
        )
        overridden = await client.put(
            f"/v1/positions/{position_id}/invitation-email-template",
            headers=AUTH,
            json={**TEMPLATE_PAYLOAD, "cta_label": "지금 응답하기"},
        )
        company_unchanged = await client.get("/v1/invitation-email-template", headers=AUTH)
        reverted = await client.delete(
            f"/v1/positions/{position_id}/invitation-email-template",
            headers=AUTH,
        )

    assert inherited.status_code == 200
    assert inherited.json()["is_position_override"] is False
    assert inherited.json()["cta_label"] == "면접 시작하기"

    assert overridden.status_code == 200
    assert overridden.json()["is_position_override"] is True
    assert overridden.json()["cta_label"] == "지금 응답하기"
    # A position override must not leak into the company-wide copy.
    assert company_unchanged.json()["cta_label"] == "면접 시작하기"

    assert reverted.status_code == 200
    assert reverted.json()["is_position_override"] is False
    assert reverted.json()["cta_label"] == "면접 시작하기"


@pytest.mark.asyncio
async def test_preview_renders_sample_data_without_sending() -> None:
    app = _app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://testserver") as (
        client
    ):
        preview = await client.post(
            "/v1/invitation-email-template/preview",
            headers=AUTH,
            json=TEMPLATE_PAYLOAD,
        )
        # Previewing must not persist anything.
        stored = await client.get("/v1/invitation-email-template", headers=AUTH)

    assert preview.status_code == 200
    assert set(preview.json()) == {"subject", "html_body"}
    assert preview.json()["subject"] == "[넥스트하이어] 백엔드 엔지니어 면접 안내"
    assert "김지원님" in preview.json()["html_body"]
    assert "#0f766e" in preview.json()["html_body"]
    assert "약 30분" in preview.json()["html_body"]
    assert "약 25분" not in preview.json()["html_body"]
    assert stored.json()["cta_label"] == "면접 시작하기"


@pytest.mark.asyncio
async def test_uploaded_logo_is_served_publicly_and_linked_by_the_server() -> None:
    app = _app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://testserver") as (
        client
    ):
        missing = await client.get(f"/v1/public/companies/{COMPANY_ID}/logo")
        uploaded = await client.put(
            "/v1/invitation-email-template/logo",
            headers={**AUTH, "Content-Type": "image/png"},
            content=PNG_BYTES,
        )
        template = await client.get("/v1/invitation-email-template", headers=AUTH)
        served = await client.get(f"/v1/public/companies/{COMPANY_ID}/logo")
        removed = await client.delete("/v1/invitation-email-template/logo", headers=AUTH)
        after_removal = await client.get("/v1/invitation-email-template", headers=AUTH)

    assert missing.status_code == 404

    assert uploaded.status_code == 200
    expected_url = f"{LOGO_BASE_URL}/v1/public/companies/{COMPANY_ID}/logo"
    assert uploaded.json() == {
        "logo_url": expected_url,
        "content_type": "image/png",
        "byte_size": len(PNG_BYTES),
    }
    # The client never supplies logo_url; the server derives it from what was uploaded.
    assert template.json()["logo_url"] == expected_url

    # A recipient's mail client fetches the image with no credentials.
    assert served.status_code == 200
    assert served.content == PNG_BYTES
    assert served.headers["content-type"] == "image/png"
    assert served.headers["cache-control"] == "public, max-age=3600"

    assert removed.status_code == 204
    assert after_removal.json()["logo_url"] is None


@pytest.mark.asyncio
async def test_logo_upload_rejects_unsupported_types_and_oversized_images() -> None:
    app = _app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://testserver") as (
        client
    ):
        wrong_type = await client.put(
            "/v1/invitation-email-template/logo",
            headers={**AUTH, "Content-Type": "image/gif"},
            content=PNG_BYTES,
        )
        too_large = await client.put(
            "/v1/invitation-email-template/logo",
            headers={**AUTH, "Content-Type": "image/png"},
            content=b"\x00" * (MAX_LOGO_BYTES + 1),
        )
        empty = await client.put(
            "/v1/invitation-email-template/logo",
            headers={**AUTH, "Content-Type": "image/png"},
            content=b"",
        )

    assert wrong_type.status_code == 415
    assert too_large.status_code == 413
    assert empty.status_code == 400


@pytest.mark.asyncio
async def test_template_input_rejects_unknown_fields_and_client_supplied_logo() -> None:
    app = _app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://testserver") as (
        client
    ):
        # An attacker-chosen logo host would turn every invitation into a beacon, so the
        # field is not accepted at all rather than validated.
        injected_logo = await client.put(
            "/v1/invitation-email-template",
            headers=AUTH,
            json={**TEMPLATE_PAYLOAD, "logo_url": "https://attacker.example/pixel.png"},
        )
        bad_colour = await client.put(
            "/v1/invitation-email-template",
            headers=AUTH,
            json={**TEMPLATE_PAYLOAD, "brand_color": "teal"},
        )

    assert injected_logo.status_code == 422
    assert bad_colour.status_code == 422
