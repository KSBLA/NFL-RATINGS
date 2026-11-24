"""Migrate saved rating snapshots to rating scale version 3.

Run from the project root:
    python migrate_rating_history.py

The script backs up Data/history/snapshots.json before writing. It rebuilds
raw ratings from the five stored pillar ratings, so it can correctly migrate
both older snapshots that already contain ``overall_raw`` and the inconsistent
snapshot format that stored the raw value in ``overall_rating``.

Use --dry-run to preview the change without writing anything.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
RATINGS_SOURCE = PROJECT_ROOT / "src" / "NFL_Rankings"
if str(RATINGS_SOURCE) not in sys.path:
    sys.path.insert(0, str(RATINGS_SOURCE))

from grade_scale import SCALE_VERSION, raw_to_grade  # noqa: E402

PILLAR_WEIGHTS = {
    "offensive_rating": 0.30,
    "defensive_rating": 0.30,
    "special_teams_rating": 0.10,
    "discipline_rating": 0.05,
    "on_field_rating": 0.25,
}


def calculate_raw_rating(team: dict) -> float:
    missing = [column for column in PILLAR_WEIGHTS if column not in team]
    if missing:
        if "overall_raw" in team:
            return round(float(team["overall_raw"]), 2)
        raise ValueError(
            f"Snapshot team {team.get('team', '<unknown>')} is missing "
            f"pillar values required for migration: {missing}"
        )

    raw = sum(float(team[column]) * weight for column, weight in PILLAR_WEIGHTS.items())
    return round(raw, 2)


def migrate_snapshot_file(path: Path, dry_run: bool = False) -> tuple[int, float, float, float, float]:
    if not path.exists():
        raise FileNotFoundError(f"History file not found: {path}")

    snapshots = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(snapshots, list):
        raise ValueError("Expected snapshots.json to contain a JSON list.")

    old_values: list[float] = []
    new_values: list[float] = []
    migrated_teams = 0

    for snapshot in snapshots:
        teams = snapshot.get("teams", [])
        for team in teams:
            raw = calculate_raw_rating(team)
            old_values.append(float(team.get("overall_rating", raw)))
            new_grade = round(raw_to_grade(raw), 2)
            new_values.append(new_grade)
            team["overall_raw"] = raw
            team["overall_rating"] = new_grade
            migrated_teams += 1
        snapshot["scale_version"] = SCALE_VERSION

    if migrated_teams == 0:
        raise ValueError("No team ratings were found in the history file.")

    if not dry_run:
        backup_path = path.with_suffix(path.suffix + ".pre_scale_v3.bak")
        if not backup_path.exists():
            shutil.copy2(path, backup_path)
        temporary_path = path.with_suffix(path.suffix + ".tmp")
        temporary_path.write_text(json.dumps(snapshots, indent=2), encoding="utf-8")
        temporary_path.replace(path)

    return (
        migrated_teams,
        min(old_values),
        max(old_values),
        min(new_values),
        max(new_values),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing the history file.")
    args = parser.parse_args()

    history_path = PROJECT_ROOT / "Data" / "history" / "snapshots.json"
    count, old_min, old_max, new_min, new_max = migrate_snapshot_file(
        history_path,
        dry_run=args.dry_run,
    )

    mode = "DRY RUN — no files changed" if args.dry_run else "Migration complete"
    print(mode)
    print(f"Rating scale version: {SCALE_VERSION}")
    print(f"Team snapshots migrated: {count}")
    print(f"Old displayed rating range: {old_min:.2f}–{old_max:.2f}")
    print(f"New displayed rating range: {new_min:.2f}–{new_max:.2f}")
    if not args.dry_run:
        print(f"Updated: {history_path}")
        print(f"Backup:  {history_path}.pre_scale_v3.bak")


if __name__ == "__main__":
    main()
