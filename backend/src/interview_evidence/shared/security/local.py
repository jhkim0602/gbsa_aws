from __future__ import annotations

from collections.abc import Mapping
from hmac import compare_digest
from uuid import UUID

from interview_evidence.shared.security.principals import (
    ApplicantPrincipal,
    CompanyPrincipal,
    PrincipalNotFoundError,
    PrincipalProvider,
)


class LocalCompanyPrincipalProvider:
    def __init__(
        self,
        *,
        access_token: str,
        company_id: UUID,
        company_user_id: UUID,
        identity_subject: str,
        email: str | None = None,
    ) -> None:
        token = access_token.strip()
        if not token:
            raise RuntimeError("LOCAL_COMPANY_ACCESS_TOKEN is required")
        self._access_token = token
        self._principal = CompanyPrincipal(
            company_id=company_id,
            company_user_id=company_user_id,
            identity_subject=identity_subject,
            email=email,
        )

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str],
    ) -> LocalCompanyPrincipalProvider:
        return cls(
            access_token=_required(environment, "LOCAL_COMPANY_ACCESS_TOKEN"),
            company_id=_required_uuid(environment, "LOCAL_COMPANY_ID"),
            company_user_id=_required_uuid(environment, "LOCAL_COMPANY_USER_ID"),
            identity_subject=_required(environment, "LOCAL_COMPANY_IDENTITY_SUBJECT"),
            email=environment.get("LOCAL_COMPANY_EMAIL", "").strip() or None,
        )

    def get_company_principal(self, credential: str) -> CompanyPrincipal:
        if not compare_digest(credential, self._access_token):
            raise PrincipalNotFoundError("company principal not found")
        return self._principal

    def get_applicant_principal(self, credential: str) -> ApplicantPrincipal:
        del credential
        raise PrincipalNotFoundError("applicant principal not found")


class FallbackCompanyPrincipalProvider:
    def __init__(
        self,
        *,
        primary: PrincipalProvider,
        fallback: PrincipalProvider,
    ) -> None:
        self._primary = primary
        self._fallback = fallback

    def get_company_principal(self, credential: str) -> CompanyPrincipal:
        try:
            return self._primary.get_company_principal(credential)
        except PrincipalNotFoundError:
            return self._fallback.get_company_principal(credential)

    def get_applicant_principal(self, credential: str) -> ApplicantPrincipal:
        return self._fallback.get_applicant_principal(credential)


def resolve_company_principal_provider(
    environment: Mapping[str, str],
    *,
    default: PrincipalProvider,
) -> PrincipalProvider:
    if environment.get("APP_ENVIRONMENT", "").strip().casefold() == "local":
        return LocalCompanyPrincipalProvider.from_environment(environment)
    if environment.get("DEMO_COMPANY_ACCESS_ENABLED", "").strip().casefold() != "true":
        return default
    return FallbackCompanyPrincipalProvider(
        primary=LocalCompanyPrincipalProvider(
            access_token=_required(environment, "DEMO_COMPANY_ACCESS_TOKEN"),
            company_id=_required_uuid(environment, "DEMO_COMPANY_ID"),
            company_user_id=_required_uuid(environment, "DEMO_COMPANY_USER_ID"),
            identity_subject=_required(environment, "DEMO_COMPANY_IDENTITY_SUBJECT"),
            email=environment.get("DEMO_COMPANY_EMAIL", "").strip() or None,
        ),
        fallback=default,
    )


def _required(environment: Mapping[str, str], name: str) -> str:
    value = environment.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required for local company authentication")
    return value


def _required_uuid(environment: Mapping[str, str], name: str) -> UUID:
    value = _required(environment, name)
    try:
        return UUID(value)
    except ValueError as error:
        raise RuntimeError(f"{name} must be a UUID") from error
