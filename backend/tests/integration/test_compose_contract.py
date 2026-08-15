from pathlib import Path

import yaml

ROOT = Path(__file__).parents[3]


def _compose() -> dict[str, object]:
    return yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))


def test_compose_runs_the_complete_local_production_contract() -> None:
    compose = _compose()
    services = compose["services"]
    required = {
        "postgres",
        "dynamodb",
        "localstack",
        "mailpit",
        "opensearch",
        "api",
        "worker",
        "company-console",
        "applicant-interview",
    }

    assert required <= services.keys()
    for name in required:
        service = services[name]
        assert "profiles" not in service
        assert "healthcheck" in service

    api = services["api"]
    worker = services["worker"]
    for dependency in ("postgres", "dynamodb", "localstack", "opensearch"):
        assert api["depends_on"][dependency]["condition"] == "service_healthy"
        assert worker["depends_on"][dependency]["condition"] == "service_healthy"

    assert api["build"]["target"] == "api"
    assert worker["build"]["target"] == "worker"
    assert services["company-console"]["build"]["target"] == "company-console"
    assert services["applicant-interview"]["build"]["target"] == "applicant-interview"
    assert "http://127.0.0.1:8080/health" in services["company-console"]["healthcheck"]["test"]
    assert "http://127.0.0.1:8080/health" in services["applicant-interview"]["healthcheck"]["test"]
    assert services["opensearch"]["environment"]["DISABLE_SECURITY_PLUGIN"] == "true"
    assert services["opensearch"]["environment"]["DISABLE_INSTALL_DEMO_CONFIG"] == "true"


def test_compose_uses_the_production_runtime_after_local_infrastructure_initialization() -> None:
    compose = _compose()
    services = compose["services"]

    assert {"local-init", "migrate", "local-seed"} <= services.keys()
    assert services["localstack"]["environment"]["SERVICES"] == "s3,sqs"
    assert services["mailpit"]["ports"] == [
        "${MAILPIT_WEB_PORT:-8025}:8025",
        "${MAILPIT_SMTP_PORT:-1025}:1025",
    ]
    assert services["local-init"]["depends_on"]["localstack"]["condition"] == "service_healthy"
    assert services["local-init"]["depends_on"]["dynamodb"]["condition"] == "service_healthy"
    assert services["local-init"]["depends_on"]["opensearch"]["condition"] == "service_healthy"
    assert services["migrate"]["depends_on"]["postgres"]["condition"] == "service_healthy"
    assert (
        services["migrate"]["depends_on"]["local-init"]["condition"]
        == "service_completed_successfully"
    )
    assert (
        services["local-seed"]["depends_on"]["migrate"]["condition"]
        == "service_completed_successfully"
    )

    required_runtime_settings = {
        "APP_ENVIRONMENT",
        "DATABASE_URL",
        "SOURCE_BUCKET",
        "MEDIA_BUCKET",
        "DYNAMODB_TABLE_NAME",
        "OPENSEARCH_ENDPOINT",
        "OPENSEARCH_INDEX_NAME",
        "SQS_ANALYSIS_QUEUE_URL",
        "SQS_MEDIA_QUEUE_URL",
        "SQS_REPORTING_QUEUE_URL",
        "SQS_DELETION_QUEUE_URL",
        "LOCAL_COMPANY_TOKEN",
    }
    for service_name in ("api", "worker"):
        service = services[service_name]
        assert service["environment"]["APP_ENVIRONMENT"] == "local-production"
        assert required_runtime_settings <= service["environment"].keys()
        assert service["depends_on"]["local-seed"]["condition"] == (
            "service_completed_successfully"
        )


def test_frontend_images_serve_spa_routes_and_proxy_api_websockets() -> None:
    containerfile = (ROOT / "apps" / "Containerfile").read_text(encoding="utf-8")
    nginx = (ROOT / "apps" / "nginx.conf").read_text(encoding="utf-8")

    assert "AS company-console" in containerfile
    assert "AS applicant-interview" in containerfile
    assert "root /usr/share/nginx/html;" in nginx
    assert "try_files $uri $uri/ /index.html;" in nginx
    assert "proxy_pass http://api:8080;" in nginx
    assert "proxy_set_header Upgrade $http_upgrade;" in nginx
    assert "proxy_set_header Connection $connection_upgrade;" in nginx


def test_make_compose_up_builds_and_waits_for_health() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

    assert "DOCKER_CONTEXT ?= default" in makefile
    assert "docker compose up -d --build --wait" in makefile
    assert "test-local-production-parity:" in makefile
    assert "scripts/verify_local_production_parity.sh" in makefile

    parity_script = (ROOT / "scripts" / "verify_local_production_parity.sh").read_text(
        encoding="utf-8"
    )
    assert "interview_evidence.runtime.parity worker-roundtrip" in parity_script
