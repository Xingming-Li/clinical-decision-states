"""Loading of synthetic timeline fixtures from JSON."""

from __future__ import annotations

from pathlib import Path

from .schema import PatientTimeline

#: Fixture directory, resolved relative to the repository checkout.
#: Present when working from a clone; not shipped inside the installed wheel.
SYNTHETIC_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "synthetic"


def load_timeline(path: str | Path) -> PatientTimeline:
    """Parse and validate one timeline JSON file."""
    return PatientTimeline.model_validate_json(Path(path).read_text(encoding="utf-8"))


def load_synthetic_timelines(
    directory: str | Path = SYNTHETIC_DATA_DIR,
) -> list[PatientTimeline]:
    """Load every ``*.json`` timeline in ``directory``, ordered by patient_id."""
    directory = Path(directory)
    if not directory.is_dir():
        raise FileNotFoundError(f"no such fixture directory: {directory}")
    timelines = [load_timeline(path) for path in sorted(directory.glob("*.json"))]
    return sorted(timelines, key=lambda t: t.patient_id)
