from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "deploy.yml"
CONTAINERFILE = ROOT / "backend" / "Containerfile"
PYPROJECT = ROOT / "pyproject.toml"


def load_workflow() -> dict[str, object]:
    assert WORKFLOW.is_file(), "deployment workflow is missing"
    loaded = yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert isinstance(loaded, dict)
    return loaded


def test_deployment_requires_oidc_saved_plan_and_environment_approval() -> None:
    workflow = load_workflow()
    assert workflow["on"] == {"workflow_dispatch": workflow["on"]["workflow_dispatch"]}  # type: ignore[index]
    assert workflow["permissions"] == {"contents": "read", "id-token": "write"}

    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    plan = jobs["terraform_plan"]
    approval = jobs["approval"]
    apply = jobs["terraform_apply"]
    assert isinstance(plan, dict)
    assert isinstance(approval, dict)
    assert isinstance(apply, dict)

    plan_text = yaml.safe_dump(plan)
    apply_text = yaml.safe_dump(apply)
    assert "terraform plan" in plan_text
    assert "upload-artifact" in plan_text
    assert "approval" in str(approval["environment"])
    assert apply["needs"] == ["terraform_plan", "approval"]
    assert "download-artifact" in apply_text
    assert "terraform apply -input=false tfplan" in apply_text
    assert "terraform apply -auto-approve" not in apply_text


def test_migration_precedes_ecs_and_frontend_deployment() -> None:
    workflow = load_workflow()
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)

    render = jobs["render_task_definitions"]
    migration = jobs["migrate_database"]
    ecs = jobs["deploy_ecs"]
    frontend = jobs["deploy_frontends"]
    assert isinstance(render, dict)
    assert isinstance(migration, dict)
    assert isinstance(ecs, dict)
    assert isinstance(frontend, dict)

    assert migration["needs"] == ["render_task_definitions"]
    assert ecs["needs"] == ["render_task_definitions", "migrate_database"]
    assert frontend["needs"] == ["quality", "deploy_ecs"]
    assert "ecs run-task" in yaml.safe_dump(migration)
    assert "ecs wait tasks-stopped" in yaml.safe_dump(migration)
    assert "interview_evidence.migrate" in yaml.safe_dump(migration)
    assert "ecs wait services-stable" in yaml.safe_dump(ecs)
    assert "s3 sync" in yaml.safe_dump(frontend)
    assert "cloudfront create-invalidation" in yaml.safe_dump(frontend)


def test_runtime_image_contains_migrations_and_postgresql_driver() -> None:
    containerfile = CONTAINERFILE.read_text(encoding="utf-8")
    pyproject = PYPROJECT.read_text(encoding="utf-8")

    assert "COPY backend/alembic.ini ./backend/alembic.ini" in containerfile
    assert "COPY backend/alembic ./backend/alembic" in containerfile
    assert '"psycopg[binary]>=3.2,<4"' in pyproject
