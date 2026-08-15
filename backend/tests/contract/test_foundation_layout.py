from pathlib import Path

from alembic.config import Config

ROOT = Path(__file__).resolve().parents[3]


def test_alembic_has_one_version_location_per_lane_and_merge() -> None:
    config = Config(ROOT / "backend/alembic.ini")
    version_locations = config.get_main_option("version_locations")

    assert "versions/company" in version_locations
    assert "versions/submission" in version_locations
    assert "versions/interview" in version_locations
    assert "versions/reporting" in version_locations
    assert "versions/merge" in version_locations
