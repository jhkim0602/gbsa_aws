from pathlib import Path
from typing import Any

import yaml
from interview_evidence.main import create_local_runtime

ROOT = Path(__file__).resolve().parents[3]
OPENAPI_ROOT = ROOT / "packages/contracts/openapi/root.yaml"
HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def canonical_operations() -> dict[tuple[str, str], str]:
    document = yaml.safe_load(OPENAPI_ROOT.read_text(encoding="utf-8"))
    base = document["servers"][0]["url"].rstrip("/")
    operations: dict[tuple[str, str], str] = {}
    for path, path_item in document["paths"].items():
        file_name, pointer = path_item["$ref"].split("#", maxsplit=1)
        fragment = yaml.safe_load((OPENAPI_ROOT.parent / file_name).read_text(encoding="utf-8"))
        resolved = fragment[pointer.removeprefix("/").replace("~1", "/").replace("~0", "~")]
        for method, operation in resolved.items():
            if method.lower() in HTTP_METHODS:
                operations[(f"{base}{path}", method.lower())] = operation["operationId"]
    return operations


def runtime_operations() -> dict[tuple[str, str], str]:
    schema: dict[str, Any] = create_local_runtime().app.openapi()
    return {
        (path, method): operation["operationId"]
        for path, path_item in schema["paths"].items()
        for method, operation in path_item.items()
        if method.lower() in HTTP_METHODS and "operationId" in operation
    }


def test_runtime_exposes_exactly_the_canonical_operations() -> None:
    runtime = runtime_operations()
    canonical = canonical_operations()

    undocumented = sorted(f"{method.upper()} {path}" for path, method in runtime.keys() - canonical)
    unimplemented = sorted(
        f"{method.upper()} {path}" for path, method in canonical.keys() - runtime
    )

    assert not undocumented, (
        "Routes exist in the application but not in packages/contracts/openapi. "
        f"Update specs/001-interview-evidence-platform/contracts/openapi.yaml: {undocumented}"
    )
    assert not unimplemented, (
        "Operations are documented but no route serves them. "
        f"Implement or remove them from the contract: {unimplemented}"
    )


def test_runtime_operation_ids_match_the_contract() -> None:
    runtime = runtime_operations()
    canonical = canonical_operations()

    mismatched = {
        f"{method.upper()} {path}": (canonical[(path, method)], runtime[(path, method)])
        for path, method in runtime.keys() & canonical.keys()
        if canonical[(path, method)] != runtime[(path, method)]
    }

    assert not mismatched, f"operationId drift (contract, runtime): {mismatched}"
