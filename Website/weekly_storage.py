"""
This function gets data from around the NFL for the week such as results of games
up-coming schedule along with other information needed for the project.
"""
import json
from pathlib import Path


WEEKLY_DIR = Path(__file__).resolve().parent.parent / "Data" / "weekly"
RESULTS_PATH = WEEKLY_DIR / "game_results.json"
SCHEDULE_PATH = WEEKLY_DIR / "schedule.json"


def read_json_list(path):
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def write_json_list(path, data):
    WEEKLY_DIR.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(".tmp")
    with temp_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)
    temp_path.replace(path)


def get_results():
    return read_json_list(RESULTS_PATH)


def get_schedule():
    return read_json_list(SCHEDULE_PATH)
