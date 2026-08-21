"""Lane ownership of every published route.

There used to be a second test here, ``test_generated_contracts_are_current``, which ran
``scripts/generate_contracts.py --check``. Commit ``7d977f7`` removed that generator along
with everything it needed -- its input (``specs/001-interview-evidence-platform/contracts/
openapi.yaml``), its Python dependency (``datamodel-code-generator``), its two Node
dependencies (``openapi-typescript``, ``json-schema-to-typescript``) and the ``generate`` /
``check`` scripts in ``packages/contracts/package.json`` -- but left the test behind. It
invoked a file that no longer exists, so it failed on every run and made the whole suite
red for a reason unrelated to any change under review.

The removal is deliberate, not an accident to be undone: ``packages/contracts/openapi/`` is
now the hand-maintained source of truth rather than a generated split of a larger spec.
Restoring the generator would mean re-adding three dependencies and recreating a 1992-line
legacy spec to feed it.

What still enforces the contract, now that no drift check does:

- **``generated/typescript/openapi.d.ts`` is imported by both SPAs** (``companyClient.ts``,
  and each app's ``routeAdapters.tsx``, via ``@iep/contracts``). A response field the
  frontend reads has to exist there or ``npm run typecheck`` fails. That is the real guard,
  and it only covers fields the frontend actually uses.
- **Nothing imports ``generated/python/``.** It drifts silently. Treat it as documentation.
- The test below still holds the invariant it always did: one owner lane per route.

So adding a field to a response means editing three files by hand, in this order:
``packages/contracts/openapi/`` (the contract), ``generated/typescript/openapi.d.ts`` (what
the SPAs compile against), then the route. Nothing will tell you if you skip the first.
"""

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
