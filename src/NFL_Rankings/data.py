import os
import sys
import time
from pathlib import Path

import nflreadpy as nfl
import polars as pl


# ---------------------------------------------------------
# PROJECT SETTINGS
# ---------------------------------------------------------

SEASON = 2026

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"
CACHE_DIR = PROJECT_ROOT / "Data" / "cache"

CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------
# CACHE REFRESH POLICY
# ---------------------------------------------------------
# Cached files go stale after CACHE_MAX_AGE_HOURS and are re-downloaded.
# Force a refresh with `python main.py --refresh` or NFL_FORCE_REFRESH=1.

CACHE_MAX_AGE_HOURS = 6


def _force_refresh() -> bool:
    return (
        os.environ.get("NFL_FORCE_REFRESH") == "1"
        or "--refresh" in sys.argv
    )


def _cache_is_fresh(cache_file: Path) -> bool:
    if not cache_file.exists() or _force_refresh():
        return False
    age_hours = (time.time() - cache_file.stat().st_mtime) / 3600
    return age_hours < CACHE_MAX_AGE_HOURS


def _load_with_refresh(cache_file: Path, label: str, download):
    """Return cached data if fresh, else download. Falls back to the old cache on failure."""
    if _cache_is_fresh(cache_file):
        print(f"Loading {label} from cache: {cache_file}")
        return pl.read_parquet(cache_file)

    print(f"Downloading latest {label}...")
    try:
        data = download()
        data.write_parquet(cache_file)
        print(f"Saved {label} to cache: {cache_file}")
        return data
    except Exception as error:
        if cache_file.exists():
            print(
                f"WARNING: could not refresh {label} ({error}). "
                f"Using older cached copy: {cache_file}"
            )
            return pl.read_parquet(cache_file)
        raise

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from NFL_Rankings.database import get_connection


# ---------------------------------------------------------
# SCHEDULE DATA
# ---------------------------------------------------------


def load_schedule(season: int = SEASON) -> pl.DataFrame:
    cache_file = CACHE_DIR / f"schedule_{season}.parquet"

    return _load_with_refresh(
        cache_file,
        f"{season} NFL schedule",
        lambda: nfl.load_schedules([season]),
    )


def prepare_games_table() -> None:
    new_columns = {
        "game_type": "TEXT",
        "gameday": "TEXT",
        "gametime": "TEXT",
        "stadium": "TEXT",
        "location": "TEXT",
    }

    with get_connection() as connection:
        existing_columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(games)"
            ).fetchall()
        }

        for column, data_type in new_columns.items():
            if column not in existing_columns:
                connection.execute(
                    f"ALTER TABLE games ADD COLUMN {column} {data_type}"
                )


def import_schedule(schedules: pl.DataFrame) -> None:
    prepare_games_table()
    games = []

    for game in schedules.iter_rows(named=True):
        home_score = game["home_score"]
        away_score = game["away_score"]

        if home_score is not None and away_score is not None:
            game_status = "final"
        elif home_score is not None or away_score is not None:
            game_status = "in_progress"
        else:
            game_status = "scheduled"

        games.append((
            game["game_id"],
            game["season"],
            game["week"],
            game["home_team"],
            game["away_team"],
            home_score,
            away_score,
            game_status,
            game["game_type"],
            str(game["gameday"]) if game["gameday"] is not None else None,
            str(game["gametime"]) if game["gametime"] is not None else None,
            game["stadium"],
            game["location"],
        ))

    with get_connection() as connection:
        connection.executemany("""
            INSERT INTO games (
                game_id, season, week, home_team, away_team,
                home_score, away_score, game_status, game_type,
                gameday, gametime, stadium, location
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(game_id) DO UPDATE SET
                season = excluded.season,
                week = excluded.week,
                home_team = excluded.home_team,
                away_team = excluded.away_team,
                home_score = excluded.home_score,
                away_score = excluded.away_score,
                game_status = excluded.game_status,
                game_type = excluded.game_type,
                gameday = excluded.gameday,
                gametime = excluded.gametime,
                stadium = excluded.stadium,
                location = excluded.location
        """, games)

    print(f"Imported or updated {len(games)} games.")


def verify_games(season: int = SEASON) -> None:
    with get_connection() as connection:
        total = connection.execute(
            "SELECT COUNT(*) FROM games WHERE season = ?",
            (season,)
        ).fetchone()[0]

        completed = connection.execute("""
            SELECT COUNT(*) FROM games
            WHERE season = ? AND game_status = 'final'
        """, (season,)).fetchone()[0]

        upcoming = connection.execute("""
            SELECT COUNT(*) FROM games
            WHERE season = ? AND game_status = 'scheduled'
        """, (season,)).fetchone()[0]

        in_progress = connection.execute("""
            SELECT COUNT(*) FROM games
            WHERE season = ? AND game_status = 'in_progress'
        """, (season,)).fetchone()[0]

    print("\nDATABASE GAME SUMMARY")
    print("-------------------------")
    print(f"Total games:       {total}")
    print(f"Completed games:   {completed}")
    print(f"Upcoming games:    {upcoming}")
    print(f"In-progress games: {in_progress}")


# ---------------------------------------------------------
# TEAM STATISTICS
# ---------------------------------------------------------

def load_team_stats(season: int = SEASON) -> pl.DataFrame:
    cache_file = CACHE_DIR / f"team_stats_{season}.parquet"

    return _load_with_refresh(
        cache_file,
        f"{season} weekly team statistics",
        lambda: nfl.load_team_stats(
            seasons=[season],
            summary_level="week"
        ),
    )


# ---------------------------------------------------------
# PLAY-BY-PLAY DATA
# ---------------------------------------------------------

def load_play_by_play(season: int = SEASON) -> pl.DataFrame:
    cache_file = CACHE_DIR / f"play_by_play_{season}.parquet"

    pbp = _load_with_refresh(
        cache_file,
        f"{season} play-by-play data",
        lambda: nfl.load_pbp(seasons=[season]),
    )

    print(f"Play-by-play rows: {pbp.height:,}")
    print(f"Number of columns: {len(pbp.columns)}")

    if "week" in pbp.columns and pbp.height:
        print(f"Latest week in play-by-play data: {pbp['week'].max()}")

    return pbp


def get_scrimmage_plays(pbp: pl.DataFrame) -> pl.DataFrame:
    scrimmage = pbp.filter(
        pl.col("play_type").is_in(["pass", "run"])
        & pl.col("epa").is_not_null()
        & pl.col("success").is_not_null()
        & pl.col("posteam").is_not_null()
        & pl.col("defteam").is_not_null()
    )

    print(f"Eligible scrimmage plays: {scrimmage.height:,}")
    return scrimmage


# ---------------------------------------------------------
# DATA PIPELINE CHECK
# ---------------------------------------------------------

if __name__ == "__main__":
    pbp = load_play_by_play()
    scrimmage = get_scrimmage_plays(pbp)

    print("\nDATA LOADING CHECK")
    print("-------------------------")
    print(f"Season: {SEASON}")
    print(f"Play-by-play rows: {pbp.height:,}")
    print(f"Eligible scrimmage plays: {scrimmage.height:,}")
