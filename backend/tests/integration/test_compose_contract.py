from pathlib import Path

import yaml

ROOT = Path(__file__).parents[3]


def _compose() -> dict[str, object]:
    return yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))


def test_compose_runs_the_complete_local_production_contract() -> None:
    compose = _compose()
    services = compose["services"]
    required = {"postgres", "localstack", "mailpit"}

    assert required == services.keys()
    for name in required:
        service = services[name]
        assert "profiles" not in service
        assert "healthcheck" in service

    assert "dynamodb" not in services
    assert "opensearch" not in services


def test_compose_keeps_application_processes_on_the_host() -> None:
    compose = _compose()
    services = compose["services"]

    assert "SERVICES" not in services["localstack"]["environment"]
    assert services["mailpit"]["ports"] == [
        "${MAILPIT_WEB_PORT:-8025}:8025",
        "${MAILPIT_SMTP_PORT:-1025}:1025",
    ]
    assert not {"api", "worker", "company-console", "applicant-interview"} & services.keys()


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


def test_frontend_cache_policy_never_serves_spa_html_for_stale_assets() -> None:
    nginx = (ROOT / "apps" / "nginx.conf").read_text(encoding="utf-8")

    assert "location ^~ /assets/" in nginx
    assert "try_files $uri =404;" in nginx
    assert 'Cache-Control "public, max-age=31536000, immutable"' in nginx
    assert "location = /index.html" in nginx
    assert 'Cache-Control "no-store, no-cache, must-revalidate"' in nginx


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
