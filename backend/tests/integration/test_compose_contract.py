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
