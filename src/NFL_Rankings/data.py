import sys
from pathlib import Path

import nflreadpy as nfl
import polars as pl


# ---------------------------------------------------------
# PROJECT SETTINGS
# ---------------------------------------------------------

SEASON = 2026

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"
CACHE_DIR = PROJECT_ROOT / "data" / "cache"

CACHE_DIR.mkdir(parents=True, exist_ok=True)

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from NFL_Rankings.database import get_connection


# ---------------------------------------------------------
# SCHEDULE DATA
# ---------------------------------------------------------

def load_schedule(season: int = SEASON) -> pl.DataFrame:
    cache_file = CACHE_DIR / f"schedule_{season}.parquet"

    if cache_file.exists():
        print(f"Loading schedule from cache: {cache_file}")
        schedules = pl.read_parquet(cache_file)
    else:
        print(f"Downloading {season} NFL schedule...")
        schedules = nfl.load_schedules([season])
        schedules.write_parquet(cache_file)
        print(f"Saved schedule to cache: {cache_file}")

    return schedules


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

    if cache_file.exists():
        print(f"Loading team statistics from cache: {cache_file}")
        stats = pl.read_parquet(cache_file)
    else:
        print(f"Downloading {season} weekly team statistics...")
        stats = nfl.load_team_stats(
            seasons=[season],
            summary_level="week"
        )
        stats.write_parquet(cache_file)
        print(f"Saved team statistics to cache: {cache_file}")

    return stats


# ---------------------------------------------------------
# PLAY-BY-PLAY DATA
# ---------------------------------------------------------

def load_play_by_play(season: int = SEASON) -> pl.DataFrame:
    cache_file = CACHE_DIR / f"play_by_play_{season}.parquet"

    if cache_file.exists():
        print(f"Loading play-by-play data from cache: {cache_file}")
        pbp = pl.read_parquet(cache_file)
    else:
        print(f"Downloading {season} play-by-play data...")
        pbp = nfl.load_pbp(seasons=[season])
        pbp.write_parquet(cache_file)
        print(f"Saved play-by-play data to cache: {cache_file}")

    print(f"Play-by-play rows: {pbp.height:,}")
    print(f"Number of columns: {len(pbp.columns)}")

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
