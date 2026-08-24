# Created: 2026-08-21 09:45
"""Point the guard scripts at *this* repository.

`test_module_boundaries.py` and `test_revision_ids.py` check that the scripts work, on
synthetic trees under `tmp_path`. Neither ever ran one against `backend/src`, so a real
violation only showed up for whoever happened to run the script by hand -- which is how
`runtime/worker.py` reached `reporting.domain.deletion` and stayed there through a merge.

These belong in the unit suite rather than as extra CI steps because `testpaths` points
here and CI already runs `npm test`: one place to add a guard, and it fires locally too.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def test_no_module_imports_another_lanes_private_package() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check_module_boundaries.py")],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_every_migration_obeys_the_lane_head_and_revision_id_rules() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check_migrations.py")],
        check=False,
        capture_output=True,
        text=True,
        # The script's ORM drift check shells out to `alembic check`, which needs a live
        # database. The unit suite has none, so leave that half to `make migrate` and the
        # integration suite and keep this to the rules it can read off the files.
        env={**os.environ, "CHECK_ORM_DRIFT": "0"},
    )

    assert result.returncode == 0, result.stdout + result.stderr
