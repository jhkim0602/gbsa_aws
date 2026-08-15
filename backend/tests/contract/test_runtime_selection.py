from interview_evidence.main import LazyEnvironmentApplication


def test_deployment_application_selects_runtime_from_environment() -> None:
    application = LazyEnvironmentApplication(environment={"APP_ENVIRONMENT": "stage"})
    assert application.runtime_mode == "production"


def test_explicit_local_environment_keeps_deterministic_runtime() -> None:
    application = LazyEnvironmentApplication(environment={"APP_ENVIRONMENT": "local"})
    assert application.runtime_mode == "local"
