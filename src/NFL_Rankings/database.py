
import sqlite3
from pathlib import Path


# ---------------------------------------------------------
# DATABASE CONFIGURATION
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"
DATABASE_PATH = DATA_DIR / "nfl_rankings.db"


# ---------------------------------------------------------
# ALL 32 NFL TEAMS
# ---------------------------------------------------------

NFL_TEAMS = [
    ("ARI", "Arizona Cardinals"),
    ("ATL", "Atlanta Falcons"),
    ("BAL", "Baltimore Ravens"),
    ("BUF", "Buffalo Bills"),
    ("CAR", "Carolina Panthers"),
    ("CHI", "Chicago Bears"),
    ("CIN", "Cincinnati Bengals"),
    ("CLE", "Cleveland Browns"),
    ("DAL", "Dallas Cowboys"),
    ("DEN", "Denver Broncos"),
    ("DET", "Detroit Lions"),
    ("GB", "Green Bay Packers"),
    ("HOU", "Houston Texans"),
    ("IND", "Indianapolis Colts"),
    ("JAX", "Jacksonville Jaguars"),
    ("KC", "Kansas City Chiefs"),
    ("LV", "Las Vegas Raiders"),
    ("LAC", "Los Angeles Chargers"),
    ("LAR", "Los Angeles Rams"),
    ("MIA", "Miami Dolphins"),
    ("MIN", "Minnesota Vikings"),
    ("NE", "New England Patriots"),
    ("NO", "New Orleans Saints"),
    ("NYG", "New York Giants"),
    ("NYJ", "New York Jets"),
    ("PHI", "Philadelphia Eagles"),
    ("PIT", "Pittsburgh Steelers"),
    ("SF", "San Francisco 49ers"),
    ("SEA", "Seattle Seahawks"),
    ("TB", "Tampa Bay Buccaneers"),
    ("TEN", "Tennessee Titans"),
    ("WAS", "Washington Commanders"),
]


# ---------------------------------------------------------
# DATABASE CONNECTION
# ---------------------------------------------------------

def get_connection():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row

    return connection


# ---------------------------------------------------------
# INITIALIZE DATABASE
# ---------------------------------------------------------

def initialize_database():

    with get_connection() as connection:

        connection.execute("""
            CREATE TABLE IF NOT EXISTS teams (
                team_id TEXT PRIMARY KEY,
                team_name TEXT NOT NULL,
                abbreviation TEXT NOT NULL UNIQUE
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS update_history (
                update_id INTEGER PRIMARY KEY AUTOINCREMENT,
                season INTEGER NOT NULL,
                week INTEGER NOT NULL,
                update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(season, week)
            )
        """)


        connection.execute("""
            CREATE TABLE IF NOT EXISTS games (
                game_id TEXT PRIMARY KEY,
                season INTEGER NOT NULL,
                week INTEGER NOT NULL,
                home_team TEXT NOT NULL,
                away_team TEXT NOT NULL,
                home_score INTEGER,
                away_score INTEGER,
                game_status TEXT,
                game_type TEXT,
                gameday TEXT,
                gametime TEXT,
                stadium TEXT,
                location TEXT
            )
        """)


        # Safely add missing game columns to existing databases.
        existing_columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(games)"
            ).fetchall()
        }

        missing_columns = {
            "game_type": "TEXT",
            "gameday": "TEXT",
            "gametime": "TEXT",
            "stadium": "TEXT",
            "location": "TEXT",
        }

        for column, data_type in missing_columns.items():
            if column not in existing_columns:
                connection.execute(
                    f"ALTER TABLE games ADD COLUMN {column} {data_type}"
                )

        connection.executemany("""
            INSERT OR IGNORE INTO teams
            (team_id, team_name, abbreviation)
            VALUES (?, ?, ?)
        """, [
            (abbreviation, name, abbreviation)
            for abbreviation, name in NFL_TEAMS
        ])
        connection.execute("""
            CREATE TABLE IF NOT EXISTS weekly_team_stats (
                stat_id INTEGER PRIMARY KEY AUTOINCREMENT,
                season INTEGER NOT NULL,
                week INTEGER NOT NULL,
                team TEXT NOT NULL,
                opponent TEXT,
                is_home INTEGER,
                points_scored REAL,
                points_allowed REAL,
                offensive_yards REAL,
                passing_yards REAL,
                rushing_yards REAL,
                turnovers REAL,
                sacks_allowed REAL,
                sacks_recorded REAL,
                UNIQUE(season, week, team)
            )
        """)

    print("NFL database initialized successfully.")
    print(f"Database location: {DATABASE_PATH}")

# ---------------------------------------------------------
# Getting all teams
# ---------------------------------------------------------

def get_all_teams():

    with get_connection() as connection:
        teams = connection.execute("""
            SELECT team_name, abbreviation
            FROM teams
            ORDER BY team_name
        """).fetchall()

    return teams

def get_games(season, status=None):

    with get_connection() as connection:

        if status:
            games = connection.execute("""
                SELECT *
                FROM games
                WHERE season = ? AND game_status = ?
                ORDER BY week, gameday
            """, (season, status)).fetchall()

        else:
            games = connection.execute("""
                SELECT *
                FROM games
                WHERE season = ?
                ORDER BY week, gameday
            """, (season,)).fetchall()

    return games

# ---------------------------------------------------------
# RUN DATABASE INITIALIZATION
# ---------------------------------------------------------

if __name__ == "__main__":

    initialize_database()

    completed = get_games(2026, "final")
    upcoming = get_games(2026, "scheduled")


    print("\nSAMPLE COMPLETED GAMES:")

    for game in completed[:5]:
        print(
            f"Week {game['week']}: "
            f"{game['away_team']} "
            f"{game['away_score']} @ "
            f"{game['home_team']} "
            f"{game['home_score']} "
            f"| {game['gameday']} "
            f"| {game['game_status']}"
        )


    print(f"\nCompleted games: {len(completed)}")
    print(f"Upcoming games: {len(upcoming)}")

    print("\nNEXT 5 UPCOMING GAMES:")

    for game in upcoming[:5]:
        print(
            f"Week {game['week']}: "
            f"{game['away_team']} @ {game['home_team']} "
            f"({game['gameday']})"
        )