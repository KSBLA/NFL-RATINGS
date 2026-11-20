
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent / "src" / "NFL_Rankings"
sys.path.insert(0, str(SRC_DIR))

from data import load_play_by_play
from on_field import build_game_records, build_on_field_metrics


pbp = load_play_by_play()

print("\nBUILDING GAME RECORDS")

game_records = build_game_records(pbp)

print(f"Game records: {game_records.height}")
print("\nSAMPLE GAME RECORDS")
print(game_records.head(10))

print("\nBUILDING ON-FIELD METRICS")

on_field_metrics = build_on_field_metrics(pbp)

print(f"Teams: {on_field_metrics['team'].n_unique()}")
print(f"Metrics: {len(on_field_metrics.columns) - 1}")

print("\nON-FIELD METRICS")
print(on_field_metrics.head(10))

if game_records.height != 300:
    raise ValueError("Expected 300 team-game records.")

if on_field_metrics["team"].n_unique() != 32:
    raise ValueError("Expected all 32 NFL teams.")

if on_field_metrics["on_field_games_played"].sum() != 300:
    raise ValueError("Team game totals do not equal 300.")

print("\nON-FIELD METRICS TEST PASSED")
