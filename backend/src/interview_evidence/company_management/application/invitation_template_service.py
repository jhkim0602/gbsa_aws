"""Read, write, and resolve the company-editable invitation email template.

Resolution is a three-level fallback: a position override, then the company-wide
template, then the platform default. Only the level that was actually edited is stored,
so a company that never touched the copy keeps receiving improvements to the default.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from uuid import UUID

from interview_evidence.company_management.domain.company import (
    LOGO_CONTENT_TYPES,
    MAX_LOGO_BYTES,
    CompanyLogo,
    CompanyStatus,
)
from interview_evidence.company_management.repositories.postgres import (
    CompanyRepository,
    TenantScopedResourceNotFound,
)
from interview_evidence.shared.email_templates import (
    DEFAULT_INVITATION_EMAIL_TEMPLATE,
    InvitationEmailContent,
    InvitationEmailTemplate,
    RenderedEmail,
    render_invitation_email,
)
from interview_evidence.shared.ids import Clock
from interview_evidence.shared.tenant import TenantContext

PREVIEW_APPLICANT_NAME = "김지원"
PREVIEW_POSITION_TITLE = "백엔드 엔지니어"
PREVIEW_DEADLINE_TEXT = "2026년 9월 1일 23:59"
PREVIEW_INVITATION_URL = "https://example.com/interview/preview"


class LogoTooLargeError(ValueError):
    """Raised when an uploaded logo exceeds the inline storage cap."""


class UnsupportedLogoTypeError(ValueError):
    """Raised when an uploaded logo is not a mail-client-safe image format."""


@dataclass(frozen=True, slots=True)
class ResolvedTemplate:
    template: InvitationEmailTemplate
    #: True when the position carries its own override rather than inheriting.
    is_position_override: bool


class InvitationTemplateService:
    def __init__(
        self,
        repository: CompanyRepository,
        clock: Clock,
        *,
        logo_base_url: str,
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._logo_base_url = logo_base_url.rstrip("/")

    def logo_url(self, company_id: UUID) -> str:
        return f"{self._logo_base_url}/v1/public/companies/{company_id}/logo"

    def get_company_template(self, context: TenantContext) -> InvitationEmailTemplate:
        """Return the company's template, or the platform default if it has none.

        A missing company row means the tenant predates its own record rather than that
        the invitation cannot be described, so reading falls back to the default instead
        of failing. Writing still requires the row to exist.
        """
        try:
            company = self._repository.get_company(context)
        except TenantScopedResourceNotFound:
            return DEFAULT_INVITATION_EMAIL_TEMPLATE
        return company.invitation_email_template or self._default_for(context)

    def save_company_template(
        self,
        context: TenantContext,
        template: InvitationEmailTemplate,
    ) -> InvitationEmailTemplate:
        company = self._repository.get_company(context)
        stored = self._with_managed_logo(context, template)
        self._repository.save_company(
            context,
            company.model_copy(
                update={
                    "invitation_email_template": stored,
                    "updated_at": self._clock.now(),
                }
            ),
        )
        return stored

    def clear_company_template(self, context: TenantContext) -> InvitationEmailTemplate:
        """Forget the company's edits so it tracks the platform default again."""
        company = self._repository.get_company(context)
        self._repository.save_company(
            context,
            company.model_copy(
                update={
                    "invitation_email_template": None,
                    "updated_at": self._clock.now(),
                }
            ),
        )
        return self._default_for(context)

    def get_position_template(
        self,
        context: TenantContext,
        position_id: UUID,
    ) -> ResolvedTemplate:
        position = self._repository.get_position(context, position_id)
        override = position.invitation_email_template
        if override is not None:
            return ResolvedTemplate(template=override, is_position_override=True)
        return ResolvedTemplate(
            template=self.get_company_template(context),
            is_position_override=False,
        )

    def save_position_template(
        self,
        context: TenantContext,
        position_id: UUID,
        template: InvitationEmailTemplate | None,
    ) -> ResolvedTemplate:
        """Store a position override, or clear it with ``None`` to inherit again."""
        position = self._repository.get_position(context, position_id)
        stored = None if template is None else self._with_managed_logo(context, template)
        self._repository.save_position(
            context,
            position.model_copy(update={"invitation_email_template": stored}),
        )
        if stored is None:
            return ResolvedTemplate(
                template=self.get_company_template(context),
                is_position_override=False,
            )
        return ResolvedTemplate(template=stored, is_position_override=True)

    def resolve_for_sending(
        self,
        context: TenantContext,
        position_id: UUID,
    ) -> InvitationEmailTemplate:
        return self.get_position_template(context, position_id).template

    def preview(
        self,
        context: TenantContext,
        template: InvitationEmailTemplate,
        *,
        position_title: str = PREVIEW_POSITION_TITLE,
    ) -> RenderedEmail:
        """Render the template against sample data so nothing real is sent."""
        return render_invitation_email(
            self._with_managed_logo(context, template),
            InvitationEmailContent(
                company_name=self.company_name(context),
                position_title=position_title,
                deadline_text=PREVIEW_DEADLINE_TEXT,
                invitation_url=PREVIEW_INVITATION_URL,
                applicant_display_name=PREVIEW_APPLICANT_NAME,
            ),
        )

    def upload_logo(
        self,
        context: TenantContext,
        *,
        content: bytes,
        content_type: str,
    ) -> CompanyLogo:
        normalized_type = content_type.split(";")[0].strip().lower()
        if normalized_type not in LOGO_CONTENT_TYPES:
            raise UnsupportedLogoTypeError("unsupported logo content type")
        if not content:
            raise ValueError("logo content must not be empty")
        if len(content) > MAX_LOGO_BYTES:
            raise LogoTooLargeError("logo exceeds the maximum allowed size")
        company = self._repository.get_company(context)
        return self._repository.save_company_logo(
            context,
            CompanyLogo(
                company_id=company.company_id,
                content_type=normalized_type,
                byte_size=len(content),
                sha256=sha256(content).hexdigest(),
                content=content,
                updated_at=self._clock.now(),
            ),
        )

    def delete_logo(self, context: TenantContext) -> None:
        self._repository.delete_company_logo(context)

    def find_public_logo(self, company_id: UUID) -> CompanyLogo | None:
        return self._repository.find_public_company_logo(company_id)

    def company_name(self, context: TenantContext) -> str:
        try:
            return self._repository.get_company(context).name
        except TenantScopedResourceNotFound:
            return "회사"

    def _default_for(self, context: TenantContext) -> InvitationEmailTemplate:
        return DEFAULT_INVITATION_EMAIL_TEMPLATE.model_copy(
            update={"logo_url": self._stored_logo_url(context)}
        )

    def _with_managed_logo(
        self,
        context: TenantContext,
        template: InvitationEmailTemplate,
    ) -> InvitationEmailTemplate:
        """Point the template at the uploaded logo, or at nothing if none exists.

        The client cannot choose an arbitrary ``logo_url``: an attacker-supplied URL
        would turn every invitation into a request to a host they control, leaking
        recipient open events. The URL is always derived from what was uploaded here.
        """
        return template.model_copy(update={"logo_url": self._stored_logo_url(context)})

    def _stored_logo_url(self, context: TenantContext) -> str | None:
        try:
            company = self._repository.get_company(context)
        except TenantScopedResourceNotFound:
            return None
        if company.status is not CompanyStatus.ACTIVE:
            return None
        if self._repository.find_public_company_logo(company.company_id) is None:
            return None
        return self.logo_url(company.company_id)
