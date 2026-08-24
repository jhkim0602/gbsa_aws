from interview_evidence.runtime.production import _automated_interviews_enabled


def test_automated_interviews_remain_enabled_for_local_development() -> None:
    assert _automated_interviews_enabled({"APP_ENVIRONMENT": "local"})


def test_deployed_automated_interviews_require_an_explicit_flag() -> None:
    assert not _automated_interviews_enabled({"APP_ENVIRONMENT": "prod"})
    assert _automated_interviews_enabled(
        {
            "APP_ENVIRONMENT": "dev",
            "AUTOMATED_INTERVIEW_ENABLED": "true",
        }
    )
