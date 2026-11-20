
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent / "src" / "NFL_Rankings"
sys.path.insert(0, str(SRC_DIR))

from data import load_play_by_play, get_scrimmage_plays
from offense import build_offensive_metrics
from defense import build_defensive_metrics
from penalties import build_penalty_metrics
from special_teams import build_special_teams_metrics
from on_field import build_on_field_metrics


pbp = load_play_by_play()
scrimmage = get_scrimmage_plays(pbp)

foundations = {
    "OFFENSE": build_offensive_metrics(pbp, scrimmage),
    "DEFENSE": build_defensive_metrics(pbp, scrimmage),
    "DISCIPLINE": build_penalty_metrics(pbp),
    "SPECIAL TEAMS": build_special_teams_metrics(pbp),
    "ON-FIELD PERFORMANCE": build_on_field_metrics(pbp)
}

print("\n" + "=" * 70)
print("FOUNDATION METRIC INVENTORY")
print("=" * 70)

for foundation, metrics in foundations.items():

    columns = [
        column for column in metrics.columns
        if column != "team"
    ]

    print(f"\n{foundation}")
    print("-" * 70)
    print(f"Total metrics: {len(columns)}")

    for column in columns:
        print(f"  {column}")

print("\n" + "=" * 70)
print("METRIC INVENTORY COMPLETED")
print("=" * 70)
