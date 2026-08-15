from uuid import UUID

import pytest
from interview_evidence.shared.security.principals import (
    ApplicantPrincipal,
    CompanyPrincipal,
    FakePrincipalProvider,
    PrincipalNotFoundError,
)


def test_fake_principal_provider_is_deterministic_and_scoped() -> None:
    company_id = UUID("00000000-0000-7000-8000-000000000001")
    company_principal = CompanyPrincipal(
        company_id=company_id,
        company_user_id=UUID("00000000-0000-7000-8000-000000000002"),
        identity_subject="company-subject",
    )
    applicant_principal = ApplicantPrincipal(
        company_id=company_id,
        invitation_id=UUID("00000000-0000-7000-8000-000000000003"),
        applicant_id=UUID("00000000-0000-7000-8000-000000000004"),
        session_id=UUID("00000000-0000-7000-8000-000000000005"),
    )
    provider = FakePrincipalProvider(
        company_principals={"company-token": company_principal},
        applicant_principals={"applicant-token": applicant_principal},
    )

    assert provider.get_company_principal("company-token") == company_principal
    assert provider.get_applicant_principal("applicant-token") == applicant_principal
    with pytest.raises(PrincipalNotFoundError):
        provider.get_company_principal("unknown-token")
