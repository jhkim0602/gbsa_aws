import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
OPENAPI_ROOT = ROOT / "packages/contracts/openapi/root.yaml"


def test_openapi_paths_have_exactly_one_owner_lane() -> None:
    document = yaml.safe_load(OPENAPI_ROOT.read_text(encoding="utf-8"))

    for path, path_item in document["paths"].items():
        reference = path_item["$ref"]
        file_name, pointer = reference.split("#", maxsplit=1)
        fragment = yaml.safe_load((OPENAPI_ROOT.parent / file_name).read_text(encoding="utf-8"))
        resolved = fragment[pointer.removeprefix("/").replace("~1", "/").replace("~0", "~")]
        owners = {
            operation["x-owner-lane"]
            for method, operation in resolved.items()
            if method.lower() in {"get", "post", "put", "patch", "delete"}
        }
        assert len(owners) == 1, f"{path} has owners {owners}"


def test_generated_contracts_are_current() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/generate_contracts.py", "--check"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
