import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def test_boundary_checker_rejects_another_lanes_private_package(tmp_path: Path) -> None:
    source_root = tmp_path / "interview_evidence"
    module = source_root / "company_management/application/service.py"
    module.parent.mkdir(parents=True)
    module.write_text(
        "from interview_evidence.submission_analysis.domain.model import Submission\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/check_module_boundaries.py"),
            "--source-root",
            str(source_root),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "company_management" in result.stdout
    assert "submission_analysis.domain" in result.stdout


def test_boundary_checker_maps_worker_directories_to_their_owning_lane(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "interview_evidence"
    module = source_root / "workers/analysis/handler.py"
    module.parent.mkdir(parents=True)
    module.write_text(
        "from interview_evidence.submission_analysis.domain.model import Submission\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/check_module_boundaries.py"),
            "--source-root",
            str(source_root),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Module boundary rules passed." in result.stdout
