from uuid import UUID

from interview_evidence.shared.errors import DomainError, ErrorCode, ErrorEnvelope


def test_domain_error_uses_problem_details_envelope() -> None:
    request_id = UUID("00000000-0000-7000-8000-000000000004")
    error = DomainError(
        status=409,
        code="STALE_VERSION",
        title="State changed",
        request_id=request_id,
        retryable=True,
        current_version=4,
    )

    envelope = ErrorEnvelope.model_validate(error.as_dict())

    assert envelope.status == 409
    assert envelope.request_id == request_id
    assert envelope.current_version == 4
    assert "password" not in str(envelope.model_dump()).lower()


def test_error_catalog_contains_safe_cross_lane_codes() -> None:
    assert ErrorCode.CONSENT_REQUIRED == "CONSENT_REQUIRED"
    assert ErrorCode.TENANT_SCOPE_DENIED == "TENANT_SCOPE_DENIED"
    assert ErrorCode.DEPENDENCY_UNAVAILABLE == "DEPENDENCY_UNAVAILABLE"
