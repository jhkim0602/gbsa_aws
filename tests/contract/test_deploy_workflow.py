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
    triggers = workflow["on"]
    assert isinstance(triggers, dict)
    # A merge to the deploy branch deploys dev, and a dispatch is what reaches prod. This
    # asserted `workflow_dispatch` was the only trigger, which made adding the merge trigger
    # -- the requested behaviour -- fail a test named after approval and OIDC.
    assert set(triggers) == {"push", "workflow_dispatch"}
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
    # Containment, not equality. Every one of these jobs also needs `settings`, because
    # GitHub resolves `needs.settings.outputs.environment` -- which decides the environment
    # a job runs in -- only for jobs that declare the dependency. An exact-list assertion
    # therefore fails on a dependency the workflow cannot drop, and says nothing more about
    # ordering than this does.
    assert {"terraform_plan", "approval"} <= set(apply["needs"])
    assert "download-artifact" in apply_text
    assert "terraform apply -input=false tfplan" in apply_text
    assert "terraform apply -auto-approve" not in apply_text


def test_the_saved_plan_artifact_path_is_not_hidden() -> None:
    """`upload-artifact` uploads nothing from a path with a leading dot.

    `include-hidden-files` defaults to false, and the action classes any dot-prefixed
    component as hidden -- so `path: .deploy-plan` matched zero files even though the step
    that wrote it had just succeeded. The failure names the path and not the reason
    (`No files were found with the provided path: .deploy-plan`), and the whole deploy
    stopped there with `approval` through `deploy_frontends` skipped.

    Pinned on the plan and apply jobs together: the download path and the `cp` source have to
    keep naming the same directory, or the apply fails after the approval gate instead.
    """
    workflow = load_workflow()
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)

    text = yaml.safe_dump({name: jobs[name] for name in ("terraform_plan", "terraform_apply")})
    assert ".deploy-plan" not in text
    assert "deploy-plan" in text
    # Not solved by opting out of the default, which exists to keep `.git` and `.env` out of
    # artifacts -- and a saved plan carries subnet and security group ids.
    assert "include-hidden-files" not in text


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

    # Containment for the same reason as above: each of these declares `settings` too.
    # What must hold is that the schema migration is upstream of anything serving traffic --
    # an ECS task started against an un-migrated database fails its first query, and a
    # published SPA calling an API that has not migrated fails in the browser instead.
    assert {"render_task_definitions"} <= set(migration["needs"])
    assert {"render_task_definitions", "migrate_database"} <= set(ecs["needs"])
    assert {"quality", "deploy_ecs"} <= set(frontend["needs"])
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
