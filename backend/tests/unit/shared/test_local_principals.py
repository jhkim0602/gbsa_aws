from uuid import UUID

import pytest
from interview_evidence.shared.security.local import (
    LocalCompanyPrincipalProvider,
    resolve_company_principal_provider,
)
from interview_evidence.shared.security.principals import PrincipalNotFoundError

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
COMPANY_USER_ID = UUID("00000000-0000-7000-8000-000000000002")


def _environment(*, token: str = "local-company-token") -> dict[str, str]:
    return {
        "APP_ENVIRONMENT": "local",
        "LOCAL_COMPANY_ACCESS_TOKEN": token,
        "LOCAL_COMPANY_ID": str(COMPANY_ID),
        "LOCAL_COMPANY_USER_ID": str(COMPANY_USER_ID),
        "LOCAL_COMPANY_IDENTITY_SUBJECT": "local-production-company-user",
        "LOCAL_COMPANY_EMAIL": "local-company@example.test",
    }


def test_local_company_principal_provider_accepts_only_configured_token() -> None:
    provider = LocalCompanyPrincipalProvider.from_environment(_environment())

    principal = provider.get_company_principal("local-company-token")

    assert principal.company_id == COMPANY_ID
    assert principal.company_user_id == COMPANY_USER_ID
    assert principal.identity_subject == "local-production-company-user"
    assert principal.email == "local-company@example.test"
    with pytest.raises(PrincipalNotFoundError):
        provider.get_company_principal("wrong-token")
    with pytest.raises(PrincipalNotFoundError):
        provider.get_applicant_principal("applicant-token")


def test_local_provider_is_selected_only_for_local_environment() -> None:
    default = LocalCompanyPrincipalProvider.from_environment(_environment(token="default-token"))

    selected = resolve_company_principal_provider(_environment(), default=default)
    production = resolve_company_principal_provider(
        {"APP_ENVIRONMENT": "production"},
        default=default,
    )

    assert selected is not default
    assert selected.get_company_principal("local-company-token").company_id == COMPANY_ID
    assert production is default


def test_local_provider_requires_explicit_identity_configuration() -> None:
    environment = _environment()
    del environment["LOCAL_COMPANY_USER_ID"]

    with pytest.raises(RuntimeError, match="LOCAL_COMPANY_USER_ID is required"):
        LocalCompanyPrincipalProvider.from_environment(environment)
