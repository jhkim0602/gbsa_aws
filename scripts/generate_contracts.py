from __future__ import annotations

import argparse
import copy
import json
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
SOURCE_OPENAPI = ROOT / "specs/001-interview-evidence-platform/contracts/openapi.yaml"
CONTRACT_ROOT = ROOT / "packages/contracts"
OPENAPI_ROOT = CONTRACT_ROOT / "openapi"
GENERATED_ROOT = CONTRACT_ROOT / "generated"
LANE_DIRECTORIES = {
    "A": "company",
    "B": "submission",
    "C": "interview",
    "D": "reporting",
}
HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head", "trace"}


def pointer(value: str) -> str:
    return "/" + value.replace("~", "~0").replace("/", "~1")


def rewrite_fragment_refs(value: Any) -> Any:
    if isinstance(value, Mapping):
        rewritten: dict[str, Any] = {}
        for key, item in value.items():
            if key == "$ref" and isinstance(item, str) and item.startswith("#/components/"):
                rewritten[key] = f"../../root.yaml{item}"
            else:
                rewritten[key] = rewrite_fragment_refs(item)
        return rewritten
    if isinstance(value, list):
        return [rewrite_fragment_refs(item) for item in value]
    return value


def build_openapi_files() -> dict[Path, str]:
    source = yaml.safe_load(SOURCE_OPENAPI.read_text(encoding="utf-8"))
    fragments: dict[str, dict[str, Any]] = {
        directory: {} for directory in LANE_DIRECTORIES.values()
    }
    root_document = copy.deepcopy(source)
    root_document["paths"] = {}

    for route, path_item in source["paths"].items():
        owners = {
            operation["x-owner-lane"]
            for method, operation in path_item.items()
            if method.lower() in HTTP_METHODS
        }
        if len(owners) != 1:
            raise ValueError(f"{route} must have exactly one owner lane, found {sorted(owners)}")
        owner = owners.pop()
        try:
            directory = LANE_DIRECTORIES[owner]
        except KeyError as error:
            raise ValueError(f"{route} has unsupported owner lane {owner}") from error

        fragments[directory][route] = rewrite_fragment_refs(path_item)
        root_document["paths"][route] = {"$ref": f"./paths/{directory}/paths.yaml#{pointer(route)}"}

    output = {
        OPENAPI_ROOT / "root.yaml": yaml.safe_dump(
            root_document,
            allow_unicode=True,
            sort_keys=False,
        )
    }
    for directory, document in fragments.items():
        output[OPENAPI_ROOT / "paths" / directory / "paths.yaml"] = yaml.safe_dump(
            document,
            allow_unicode=True,
            sort_keys=False,
        )
    return output


def write_files(files: Mapping[Path, str]) -> None:
    for path, content in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def run(command: list[str]) -> None:
    result = subprocess.run(command, cwd=ROOT, check=False, text=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"contract generator failed: {' '.join(command)}\n{result.stdout}{result.stderr}"
        )


def generate_types(destination: Path) -> None:
    python_dir = destination / "python"
    typescript_dir = destination / "typescript"
    python_dir.mkdir(parents=True, exist_ok=True)
    typescript_dir.mkdir(parents=True, exist_ok=True)

    datamodel = ROOT / ".venv/bin/datamodel-codegen"
    openapi_typescript = ROOT / "node_modules/.bin/openapi-typescript"
    json2ts = ROOT / "node_modules/.bin/json2ts"
    common_python_args = [
        str(datamodel),
        "--output-model-type",
        "pydantic_v2.BaseModel",
        "--target-python-version",
        "3.12",
        "--disable-timestamp",
        "--use-standard-collections",
        "--use-union-operator",
        "--formatters",
        "ruff-check",
        "ruff-format",
        "--no-allow-remote-refs",
    ]

    run(
        [
            str(openapi_typescript),
            str(OPENAPI_ROOT / "root.yaml"),
            "--output",
            str(typescript_dir / "openapi.d.ts"),
            "--immutable",
            "--alphabetize",
        ]
    )
    run(
        [
            *common_python_args,
            "--input",
            str(OPENAPI_ROOT / "root.yaml"),
            "--input-file-type",
            "openapi",
            "--output",
            str(python_dir / "openapi.py"),
        ]
    )

    schema_inputs = {
        "websocket": CONTRACT_ROOT / "events/websocket/v1/protocol.json",
        "events": CONTRACT_ROOT / "events/common/v1/envelope.json",
    }
    for name, schema in schema_inputs.items():
        run(
            [
                str(json2ts),
                "--input",
                str(schema),
                "--output",
                str(typescript_dir / f"{name}.d.ts"),
                "--cwd",
                str(schema.parent),
                "--unknownAny",
            ]
        )
        run(
            [
                *common_python_args,
                "--input",
                str(schema),
                "--input-file-type",
                "jsonschema",
                "--output",
                str(python_dir / f"{name}.py"),
            ]
        )

    (python_dir / "__init__.py").write_text(
        '"""Generated contract models. Do not edit by hand."""\n',
        encoding="utf-8",
    )


def compare_file(path: Path, expected: str) -> bool:
    return path.exists() and path.read_text(encoding="utf-8") == expected


def collect_tree(root: Path) -> dict[Path, bytes]:
    if not root.exists():
        return {}
    return {
        path.relative_to(root): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file() and path.name != "README.md"
    }


def check_current(openapi_files: Mapping[Path, str]) -> int:
    drift = [
        str(path.relative_to(ROOT))
        for path, content in openapi_files.items()
        if not compare_file(path, content)
    ]
    if drift:
        print("OpenAPI contract drift detected:")
        print("\n".join(f"- {path}" for path in drift))
        return 1

    with tempfile.TemporaryDirectory(prefix="iep-contracts-") as temporary:
        expected_root = Path(temporary) / "generated"
        generate_types(expected_root)
        expected = collect_tree(expected_root)
        current = collect_tree(GENERATED_ROOT)

    if expected != current:
        changed = sorted(set(expected) | set(current))
        print("Generated contract drift detected:")
        print("\n".join(f"- {path}" for path in changed if expected.get(path) != current.get(path)))
        return 1
    print("Canonical and generated contracts are current.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate lane contracts and typed clients.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail when committed output has drift.",
    )
    arguments = parser.parse_args()

    openapi_files = build_openapi_files()
    if arguments.check:
        return check_current(openapi_files)

    write_files(openapi_files)
    with tempfile.TemporaryDirectory(prefix="iep-contracts-") as temporary:
        generated = Path(temporary) / "generated"
        generate_types(generated)
        for directory in ("python", "typescript"):
            target = GENERATED_ROOT / directory
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(generated / directory, target)
    print("Generated OpenAPI fragments and Python/TypeScript contract types.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, ValueError, json.JSONDecodeError, yaml.YAMLError) as error:
        print(error, file=sys.stderr)
        raise SystemExit(1) from error
