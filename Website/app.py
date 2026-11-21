from pathlib import Path
from datetime import datetime

import hashlib
import html
import json
import urllib.request
import sys
import math
import textwrap



import pandas as pd
import streamlit as st


# ============================================================
# NFL RATINGS — COMPLETE BLACK & ANTIQUE GOLD BROADCAST APP
# The ratings engine, CSV structure, and formulas are untouched.
# ============================================================

st.set_page_config(
    page_title="NFL RATINGS | League Headquarters",
    page_icon="🏈",
    layout="wide",
    initial_sidebar_state="collapsed",
)


BASE_DIR = Path(__file__).resolve().parent.parent
CSV_PATH = BASE_DIR / "Data" / "output" / "nfl_rankings_2026.csv"
METRICS_PATH = BASE_DIR / "Data" / "output" / "team_metrics_2026.csv"
HISTORY_DIR = BASE_DIR / "Data" / "history"
HISTORY_PATH = HISTORY_DIR / "snapshots.json"

# ============================================================
# NFL PROJECT DATABASE CONNECTION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


# ============================================================
# WEEKLY RESULTS + UPCOMING SCHEDULE STORAGE
# ============================================================

WEEKLY_DIR = BASE_DIR / "Data" / "weekly"
RESULTS_PATH = WEEKLY_DIR / "game_results.json"
SCHEDULE_PATH = WEEKLY_DIR / "schedule.json"

@st.cache_data
def load_team_metrics():
    if not METRICS_PATH.exists():
        return pd.DataFrame()

    try:
        return pd.read_csv(METRICS_PATH)
    except (OSError, pd.errors.ParserError):
        return pd.DataFrame()

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


def get_records():
    records = {
        code: {"W": 0, "L": 0, "T": 0, "PF": 0, "PA": 0}
        for code in TEAMS
    }

    for game in get_results():
        home = game.get("home")
        away = game.get("away")

        if home not in records or away not in records:
            continue

        try:
            home_score = int(game["home_score"])
            away_score = int(game["away_score"])
        except (KeyError, TypeError, ValueError):
            continue

        records[home]["PF"] += home_score
        records[home]["PA"] += away_score
        records[away]["PF"] += away_score
        records[away]["PA"] += home_score

        if home_score > away_score:
            records[home]["W"] += 1
            records[away]["L"] += 1
        elif away_score > home_score:
            records[away]["W"] += 1
            records[home]["L"] += 1
        else:
            records[home]["T"] += 1
            records[away]["T"] += 1

    for record in records.values():
        games = record["W"] + record["L"] + record["T"]
        record["PCT"] = (
            (record["W"] + record["T"] * 0.5) / games
            if games else 0.0
        )
        record["DIFF"] = record["PF"] - record["PA"]

    return records


def format_record(code):
    record = get_records()[code]
    return f'{record["W"]}-{record["L"]}-{record["T"]}'



def get_standings(conference=None, division=None):

    records = get_records()

    rows = []

    for code, record in records.items():

        team_info = TEAMS[code]

        team_conference = team_info.get("conf", "")
        team_division = team_info.get("div", "")

        if conference and team_conference != conference:
            continue

        if division and team_division != division:
            continue

        rows.append({
            "Team": team_info["name"],
            "Code": code,
            "Conference": team_conference,
            "Division": team_division,
            "W": record["W"],
            "L": record["L"],
            "T": record["T"],
            "PCT": record["PCT"],
            "PF": record["PF"],
            "PA": record["PA"],
            "DIFF": record["DIFF"],
        })

    standings = pd.DataFrame(rows)

    if standings.empty:
        return standings

    standings = standings.sort_values(
        by=["W", "PCT", "DIFF", "PF"],
        ascending=[False, False, False, False],
    ).reset_index(drop=True)

    return standings

def get_playoff_picture():

    standings = get_standings()

    playoff_picture = {}

    for conference in ["AFC", "NFC"]:

        conference_standings = standings[
            standings["Conference"] == conference
        ].copy()

        # Find division winners
        division_winners = (
            conference_standings
            .sort_values(
                by=["W", "PCT", "DIFF", "PF"],
                ascending=[False, False, False, False],
            )
            .groupby("Division", sort=False)
            .head(1)
        )

        # Rank division winners
        division_winners = division_winners.sort_values(
            by=["W", "PCT", "DIFF", "PF"],
            ascending=[False, False, False, False],
        )

        division_winners = division_winners.copy()
        division_winners["Seed"] = range(1, 5)
        division_winners["Type"] = "DIVISION WINNER"

        # Find remaining teams
        remaining_teams = conference_standings[
            ~conference_standings["Code"].isin(
                division_winners["Code"]
            )
        ]

        # Rank wild card teams
        wild_cards = remaining_teams.sort_values(
            by=["W", "PCT", "DIFF", "PF"],
            ascending=[False, False, False, False],
        ).head(3).copy()

        wild_cards["Seed"] = range(5, 8)
        wild_cards["Type"] = "WILD CARD"

        # Combine playoff teams
        playoff_teams = pd.concat(
            [division_winners, wild_cards]
        ).sort_values("Seed").reset_index(drop=True)

        # Remaining teams
        in_the_hunt = remaining_teams[
            ~remaining_teams["Code"].isin(wild_cards["Code"])
        ].copy()

        seventh_seed = playoff_teams[
            playoff_teams["Seed"] == 7
        ]

        if not seventh_seed.empty:

            seventh_team = seventh_seed.iloc[0]

            in_the_hunt["Games Back"] = (
                (seventh_team["W"] - in_the_hunt["W"])
                + (in_the_hunt["L"] - seventh_team["L"])
                ) / 2

            in_the_hunt = in_the_hunt[
                in_the_hunt["Games Back"] <= 2
            ]

        playoff_picture[conference] = {
            "playoff_teams": playoff_teams,
            "in_the_hunt": in_the_hunt.reset_index(drop=True),
        }

    return playoff_picture

def build_playoff_bracket(playoff_teams, conference):

    teams = {
        int(row["Seed"]): row["Code"]
        for _, row in playoff_teams.iterrows()
    }

    return {
        "conference": conference,
        "teams": teams,
        "wild_card": [
            (2, 7),
            (3, 6),
            (4, 5),
        ],
        "divisional": [
            (1, None),
            (None, None),
            (None, None),
        ],
        "championship": (None, None),
    }

def advance_playoff_bracket(bracket, round_name, matchup_index, winner):

    bracket = dict(bracket)
    winners = dict(bracket.get("winners", {}))

    matchups = bracket[round_name]

    if round_name == "championship":
        matchup = matchups
    else:
        matchup = matchups[matchup_index]

    if round_name == "wild_card":
        valid_teams = [
            bracket["teams"].get(seed)
            for seed in matchup
        ]
    else:
        valid_teams = list(matchup)

    if winner not in valid_teams:
        return bracket


    # Save the selected winner
    winners[f"{round_name}_{matchup_index}"] = winner

    # Clear later-round selections when an earlier result changes

    if round_name == "wild_card":
        winners = {
            key: value
            for key, value in winners.items()
            if key.startswith("wild_card_")
        }
        bracket.pop("conference_champion", None)

    elif round_name == "divisional":
        winners = {
            key: value
            for key, value in winners.items()
            if not key.startswith("championship_")
        }
        bracket.pop("conference_champion", None)

    # Rebuild the bracket
    bracket["winners"] = winners

    if round_name == "wild_card":

        wild_card_winners = [
            winners.get(f"wild_card_{i}")
            for i in range(3)
        ]

        if all(wild_card_winners):

            remaining = [
                bracket["teams"][1],
                *wild_card_winners,
            ]

            remaining.sort(
                key=lambda code: next(
                    seed
                    for seed, team in bracket["teams"].items()
                    if team == code
                )
            )

            bracket["divisional"] = [
                (remaining[0], remaining[3]),
                (remaining[1], remaining[2]),
            ]

    if round_name in ("wild_card", "divisional"):

        divisional_winners = [
            winners.get(f"divisional_{i}")
            for i in range(2)
        ]

        if all(divisional_winners):
            bracket["championship"] = tuple(divisional_winners)

    if round_name == "championship":
        bracket["conference_champion"] = winner

    return bracket

def get_upcoming_games():

    games = get_schedule()

    aliases = {
        "LA": "LAR",
        "JAC": "JAX",
        "WSH": "WAS",
        "WFT": "WAS",
        "OAK": "LV",
        "SD": "LAC",
        "STL": "LAR",
    }

    upcoming = []

    for game in games:
        home_team = game.get("home")
        away_team = game.get("away")

        if not home_team or not away_team:
            continue

        home = aliases.get(home_team, home_team)
        away = aliases.get(away_team, away_team)

        upcoming.append({
            "id": game.get("id", ""),
            "home": home,
            "away": away,
            "week": game.get("week", ""),
            "date": game.get("date", ""),
            "kickoff": game.get("kickoff", ""),
        })

    return sorted(
        upcoming,
        key=lambda game: (
            game.get("date", ""),
            game.get("kickoff", ""),
        ),
    )


CATEGORIES = [
    ("OFFENSE", "offensive_rating", "OFF"),
    ("DEFENSE", "defensive_rating", "DEF"),
    ("SPECIAL TEAMS", "special_teams_rating", "ST"),
    ("DISCIPLINE", "discipline_rating", "DISC"),
    ("ON-FIELD", "on_field_rating", "FIELD"),
]

TEAMS = {
    "ARI": {"name": "Arizona Cardinals", "color": "#97233F", "secondary": "#FFB612", "effect": "fire", "conf": "NFC", "div": "West"},
    "ATL": {"name": "Atlanta Falcons", "color": "#A71930", "secondary": "#000000", "effect": "fire", "conf": "NFC", "div": "South"},
    "BAL": {"name": "Baltimore Ravens", "color": "#241773", "secondary": "#9E7C0C", "effect": "lightning", "conf": "AFC", "div": "North"},
    "BUF": {"name": "Buffalo Bills", "color": "#00338D", "secondary": "#C60C30", "effect": "storm", "conf": "AFC", "div": "East"},
    "CAR": {"name": "Carolina Panthers", "color": "#0085CA", "secondary": "#101820", "effect": "lightning", "conf": "NFC", "div": "South"},
    "CHI": {"name": "Chicago Bears", "color": "#0B162A", "secondary": "#C83803", "effect": "storm", "conf": "NFC", "div": "North"},
    "CIN": {"name": "Cincinnati Bengals", "color": "#FB4F14", "secondary": "#000000", "effect": "claws", "conf": "AFC", "div": "North"},
    "CLE": {"name": "Cleveland Browns", "color": "#311D00", "secondary": "#FF3C00", "effect": "fire", "conf": "AFC", "div": "North"},
    "DAL": {"name": "Dallas Cowboys", "color": "#003594", "secondary": "#869397", "effect": "spotlight", "conf": "NFC", "div": "East"},
    "DEN": {"name": "Denver Broncos", "color": "#FB4F14", "secondary": "#002244", "effect": "storm", "conf": "AFC", "div": "West"},
    "DET": {"name": "Detroit Lions", "color": "#0076B6", "secondary": "#B0B7BC", "effect": "lightning", "conf": "NFC", "div": "North"},
    "GB": {"name": "Green Bay Packers", "color": "#203731", "secondary": "#FFB612", "effect": "spotlight", "conf": "NFC", "div": "North"},
    "HOU": {"name": "Houston Texans", "color": "#03202F", "secondary": "#A71930", "effect": "fire", "conf": "AFC", "div": "South"},
    "IND": {"name": "Indianapolis Colts", "color": "#002C5F", "secondary": "#A2AAAD", "effect": "lightning", "conf": "AFC", "div": "South"},
    "JAX": {"name": "Jacksonville Jaguars", "color": "#006778", "secondary": "#D7A22A", "effect": "wave", "conf": "AFC", "div": "South"},
    "KC": {"name": "Kansas City Chiefs", "color": "#E31837", "secondary": "#FFB81C", "effect": "fire", "conf": "AFC", "div": "West"},
    "LV": {"name": "Las Vegas Raiders", "color": "#000000", "secondary": "#A5ACAF", "effect": "spotlight", "conf": "AFC", "div": "West"},
    "LAC": {"name": "Los Angeles Chargers", "color": "#0080C6", "secondary": "#FFC20E", "effect": "lightning", "conf": "AFC", "div": "West"},
    "LAR": {"name": "Los Angeles Rams", "color": "#003594", "secondary": "#FFA300", "effect": "speed", "conf": "NFC", "div": "West"},
    "MIA": {"name": "Miami Dolphins", "color": "#008E97", "secondary": "#FC4C02", "effect": "wave", "conf": "AFC", "div": "East"},
    "MIN": {"name": "Minnesota Vikings", "color": "#4F2683", "secondary": "#FFC62F", "effect": "storm", "conf": "NFC", "div": "North"},
    "NE": {"name": "New England Patriots", "color": "#002244", "secondary": "#C60C30", "effect": "spotlight", "conf": "AFC", "div": "East"},
    "NO": {"name": "New Orleans Saints", "color": "#D3BC8D", "secondary": "#101820", "effect": "spotlight", "conf": "NFC", "div": "South"},
    "NYG": {"name": "New York Giants", "color": "#0B2265", "secondary": "#A71930", "effect": "lightning", "conf": "NFC", "div": "East"},
    "NYJ": {"name": "New York Jets", "color": "#125740", "secondary": "#FFFFFF", "effect": "speed", "conf": "AFC", "div": "East"},
    "PHI": {"name": "Philadelphia Eagles", "color": "#004C54", "secondary": "#A5ACAF", "effect": "storm", "conf": "NFC", "div": "East"},
    "PIT": {"name": "Pittsburgh Steelers", "color": "#FFB612", "secondary": "#101820", "effect": "fire", "conf": "AFC", "div": "North"},
    "SF": {"name": "San Francisco 49ers", "color": "#AA0000", "secondary": "#B3995D", "effect": "fire", "conf": "NFC", "div": "West"},
    "SEA": {"name": "Seattle Seahawks", "color": "#002244", "secondary": "#69BE28", "effect": "wave", "conf": "NFC", "div": "West"},
    "TB": {"name": "Tampa Bay Buccaneers", "color": "#D50A0A", "secondary": "#34302B", "effect": "fire", "conf": "NFC", "div": "South"},
    "TEN": {"name": "Tennessee Titans", "color": "#0C2340", "secondary": "#4B92DB", "effect": "lightning", "conf": "AFC", "div": "South"},
    "WAS": {"name": "Washington Commanders", "color": "#5A1414", "secondary": "#FFB612", "effect": "speed", "conf": "NFC", "div": "East"},
}

# ESPN's logo slugs differ for a few teams; explicit mapping prevents broken logos.
LOGO_SLUGS = {
    "ARI": "ari", "ATL": "atl", "BAL": "bal", "BUF": "buf",
    "CAR": "car", "CHI": "chi", "CIN": "cin", "CLE": "cle",
    "DAL": "dal", "DEN": "den", "DET": "det", "GB": "gb",
    "HOU": "hou", "IND": "ind", "JAX": "jax", "KC": "kc",
    "LV": "lv", "LAC": "lac", "LAR": "lar", "MIA": "mia",
    "MIN": "min", "NE": "ne", "NO": "no", "NYG": "nyg",
    "NYJ": "nyj", "PHI": "phi", "PIT": "pit", "SF": "sf",
    "SEA": "sea", "TB": "tb", "TEN": "ten", "WAS": "wsh",
}
for team_code, team_info in TEAMS.items():
    team_info["logo"] = (
        f"https://a.espncdn.com/i/teamlogos/nfl/500/"
        f"{LOGO_SLUGS[team_code]}.png"
    )

# ============================================================
# AUTOMATIC NFL DATA IMPORT — ESPN SCOREBOARD
# Imports the 2026 regular-season schedule and completed scores.
# Does not modify the ratings engine or ratings CSV.
# ============================================================

NFL_SEASON = 2026

ESPN_SCOREBOARD_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/football/nfl/"
    f"scoreboard?limit=1000&dates={NFL_SEASON}0101-{NFL_SEASON}1231"
)

NFL_DATA_STATUS = {
    "success": False,
    "message": "NFL data has not been loaded yet.",
    "games": 0,
    "results": 0,
}



@st.cache_data(ttl=900, show_spinner=False)
def load_espn_games():
    """Download the NFL regular-season schedule and results."""
    base_url = ESPN_SCOREBOARD_URL.split("?")[0]
    events_by_id = {}

    # ESPN rejects date ranges, so retrieve each regular-season
    # week separately.
    for week_number in range(1, 19):
        url = (
            f"{base_url}?dates={NFL_SEASON}"
            f"&seasontype=2&week={week_number}&limit=1000"
        )

        request = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 NFL-Ratings-App"},
        )

        with urllib.request.urlopen(request, timeout=25) as response:
            payload = json.loads(response.read().decode("utf-8"))

        for event in payload.get("events", []):
            game_id = str(event.get("id", "")).strip()
            if game_id:
                events_by_id[game_id] = event

    events = list(events_by_id.values())
    games = []

    aliases = {
        "WSH": "WAS",
        "JAC": "JAX",
        "OAK": "LV",
        "SD": "LAC",
        "STL": "LAR",
    }

    for event in events:
        season_type = event.get("season", {}).get("type")

        # Regular season only. Exclude preseason and playoffs.
        if season_type is not None and int(season_type) != 2:
            continue

        competitions = event.get("competitions", [])
        if not competitions:
            continue

        competition = competitions[0]
        venue = competition.get("venue", {})
        stadium = venue.get("fullName", "Stadium TBD")
        competitors = competition.get("competitors", [])


        home = None
        away = None
        home_score = None
        away_score = None
        home_record = "N/A"
        away_record = "N/A"

        for competitor in competitors:
            team = competitor.get("team", {})
            code = team.get("abbreviation", "").upper()
            code = aliases.get(code, code)

            if code not in TEAMS:
                continue

            score = competitor.get("score")
            records = competitor.get("records", [])
            team_record = (
                records[0].get("summary", "N/A")
                if records else "N/A"
            )

            if competitor.get("homeAway") == "home":
                home = code
                home_score = score
            elif competitor.get("homeAway") == "away":
                away = code
                away_score = score

            if competitor.get("homeAway") == "home":
                home_record = team_record
            elif competitor.get("homeAway") == "away":
                away_record = team_record

        if not home or not away or home == away:
            continue

        week = event.get("week", {}).get("number")
        if week is None:
            continue

        event_date = event.get("date", "")

        try:
            local_date = datetime.fromisoformat(
                event_date.replace("Z", "+00:00")
            ).astimezone()

            game_date = local_date.strftime("%Y-%m-%d")
            kickoff = local_date.strftime("%I:%M %p %Z").strip()

        except (ValueError, TypeError):
            game_date = event_date[:10]
            kickoff = "TBD"

        game_id = str(event.get("id", "")).strip()
        if not game_id:
            continue

        status = competition.get("status", {}).get("type", {})
        completed = bool(status.get("completed", False))

        games.append({
            "id": f"espn:{game_id}",
            "week": int(week),
            "date": game_date,
            "kickoff": kickoff,
            "home": home,
            "away": away,
            "completed": completed,
            "home_score": home_score,
            "away_score": away_score,
            "home_record": home_record,
            "away_record": away_record,
            "stadium": stadium,
        })

    if not games:
        raise ValueError(
            "ESPN returned no 2026 regular-season games."
        )

    return games


def sync_nfl_data():
    """
    Merge official ESPN data with existing manual entries.

    Official completed scores take priority.
    Manual entries are preserved when the feed does not contain
    that game or has not yet marked it completed.
    """
    global NFL_DATA_STATUS

    try:
        official_games = load_espn_games()

        old_results = get_results()
        old_schedule = get_schedule()

        manual_results = [
            game for game in old_results
            if game.get("source") != "espn"
        ]

        manual_schedule = [
            game for game in old_schedule
            if game.get("source") != "espn"
        ]

        manual_result_lookup = {
            (
                int(game.get("week", -1)),
                game.get("home"),
                game.get("away"),
            ): game
            for game in manual_results
        }

        official_schedule = []
        official_results = []
        official_keys = set()

        for game in official_games:
            key = (
                int(game["week"]),
                game["home"],
                game["away"],
            )

            official_keys.add(key)

            schedule_entry = {
                "id": game["id"],
                "week": game["week"],
                "date": game["date"],
                "kickoff": game["kickoff"],
                "home": game["home"],
                "away": game["away"],
                "home_record": game.get("home_record", "N/A"),
                "away_record": game.get("away_record", "N/A"),
                "stadium": game.get("stadium", "Stadium TBD"),
                "source": "espn",
            }

            official_schedule.append(schedule_entry)

            if game["completed"]:
                try:
                    home_score = int(float(game["home_score"]))
                    away_score = int(float(game["away_score"]))
                except (TypeError, ValueError):
                    continue

                official_results.append({
                    "id": game["id"],
                    "schedule_id": game["id"],
                    "week": game["week"],
                    "date": game["date"],
                    "home": game["home"],
                    "away": game["away"],
                    "home_score": home_score,
                    "away_score": away_score,
                    "source": "espn",
                })

            else:
                # Preserve a manual result if the official feed
                # has not yet marked this matchup as completed.
                manual = manual_result_lookup.get(key)

                if manual:
                    preserved = dict(manual)
                    preserved["schedule_id"] = game["id"]
                    official_results.append(preserved)

        # Keep manual games that are not in the official feed.
        for game in manual_results:
            key = (
                int(game.get("week", -1)),
                game.get("home"),
                game.get("away"),
            )

            if key not in official_keys:
                official_results.append(game)

        for game in manual_schedule:
            key = (
                int(game.get("week", -1)),
                game.get("home"),
                game.get("away"),
            )

            if key not in official_keys:
                official_schedule.append(game)

        # Write only when the data has actually changed.
        if official_results != old_results:
            write_json_list(RESULTS_PATH, official_results)

        if official_schedule != old_schedule:
            write_json_list(SCHEDULE_PATH, official_schedule)

        NFL_DATA_STATUS = {
            "success": True,
            "message": "Connected to ESPN. NFL data synchronized.",
            "games": len(official_games),
            "results": sum(
                1 for game in official_games
                if game["completed"]
            ),
        }

    except Exception as error:
        NFL_DATA_STATUS = {
            "success": False,
            "message": (
                "Automatic data feed unavailable. "
                "Using previously saved game data. "
                f"Details: {error}"
            ),
            "games": 0,
            "results": 0,
        }


# Initial synchronization. Cached data prevents repeated downloads.
sync_nfl_data()

# ============================================================
# DATA + SNAPSHOT HISTORY
# ============================================================

@st.cache_data
def load_rankings(path_string, modified_time):
    path = Path(path_string)
    if not path.exists():
        return None
    frame = pd.read_csv(path)
    required = [
        "rank", "team", "overall_rating", "offensive_rating",
        "defensive_rating", "special_teams_rating",
        "discipline_rating", "on_field_rating",
    ]
    if not all(col in frame.columns for col in required):
        return None
    frame["team"] = frame["team"].astype(str).str.upper().str.strip()
    for col in required:
        if col != "team":
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
    frame = frame.dropna(subset=required).copy()
    frame["rank"] = frame["rank"].astype(int)
    return frame.sort_values("rank").reset_index(drop=True)


def read_history():
    if not HISTORY_PATH.exists():
        return []
    try:
        with HISTORY_PATH.open("r", encoding="utf-8") as file:
            data = json.load(file)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []



def save_snapshot(frame):
    """Save only when ratings content changes; never fabricate past data."""
    if frame is None or frame.empty:
        return
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    csv_bytes = frame.sort_values("team").to_csv(index=False).encode("utf-8")
    fingerprint = hashlib.sha256(csv_bytes).hexdigest()
    history = read_history()
    if history and history[-1].get("fingerprint") == fingerprint:
        return
    now = datetime.now()
    history.append({
        "captured_at": now.isoformat(timespec="seconds"),
        "date": now.strftime("%Y-%m-%d"),
        "fingerprint": fingerprint,
        "teams": frame.to_dict(orient="records"),
    })
    with HISTORY_PATH.open("w", encoding="utf-8") as file:
        json.dump(history, file, indent=2)


rankings = (
    load_rankings(str(CSV_PATH), CSV_PATH.stat().st_mtime)
    if CSV_PATH.exists() else None
)
team_metrics = load_team_metrics()

def get_team_row(code, data=None):
    source = rankings if data is None else data

    if source is None:
        return None

    code = str(code).upper()
    csv_code = {"LAR": "LA"}.get(code, code)

    found = source[source["team"].astype(str).str.upper() == csv_code]

    return None if found.empty else found.iloc[0]

def logo(code, width=62):
    info = TEAMS[code]
    return (
        f'<img src="{info["logo"]}" alt="{html.escape(info["name"])}" '
        f'style="width:{width}px;height:{width}px;object-fit:contain;'
        f'filter:drop-shadow(0 5px 9px #0009)">'
    )


# ============================================================
# SESSION STATE + NAVIGATION
# ============================================================

DEFAULTS = {
    "page": "HOME",
    "selected_team": "SF",
    "play_entrance": False,
    "war_one": "SF",
    "war_two": "KC",
    "scroll_to_top": False,
    "playoff_simulator": {},
    "super_bowl_winner": None,
    "super_bowl_matchup": None,
    "selected_game_preview": None,
}
for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value


def go(page, team=None, entrance=False):
    st.session_state.page = page
    if team:
        st.session_state.selected_team = team
    st.session_state.play_entrance = entrance
    st.session_state.scroll_to_top = True
    st.rerun()


def reset_page_scroll():
    """Reset all Streamlit page scroll containers after navigation."""
    if st.session_state.get("scroll_to_top", False):
        st.html(
            """
            <script>
            (() => {
                const scrollTop = () => {
                    const selectors = [
                        '[data-testid="stMain"]',
                        '[data-testid="stAppViewContainer"]',
                        '[data-testid="stMainBlockContainer"]',
                        'section.main',
                        'main'
                    ];

                    selectors.forEach(selector => {
                        document.querySelectorAll(selector).forEach(element => {
                            element.scrollTop = 0;
                        });
                    });

                    document.querySelectorAll("*").forEach(element => {
                        const style = window.getComputedStyle(element);
                        if (
                            (style.overflowY === "auto" ||
                             style.overflowY === "scroll") &&
                            element.scrollHeight > element.clientHeight
                        ) {
                            element.scrollTop = 0;
                        }
                    });

                    window.scrollTo(0, 0);
                };

                scrollTop();
                requestAnimationFrame(scrollTop);
                setTimeout(scrollTop, 100);
                setTimeout(scrollTop, 300);
                setTimeout(scrollTop, 600);
            })();
            </script>
            """,
            unsafe_allow_javascript=True,
        )
        st.session_state.scroll_to_top = False


# ============================================================
# VISUAL SYSTEM — MATTE BLACK + SOFT ANTIQUE GOLD
# ============================================================

st.markdown(r"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@400;500;600;700;800;900&family=Exo+2:wght@400;500;600;700;800;900&family=Rajdhani:wght@400;500;600;700&display=swap');

:root {
    --gold: #B99A5A;
    --gold-light: #D0B779;
    --gold-dark: #806B43;
    --muted: #A99A78;
    --panel: #171614;
    --line: rgba(185,154,90,.20);
    --white: #F1EFE9;
}

.stApp {
    background:
        radial-gradient(ellipse at 12% 0%, rgba(150,119,58,.12), transparent 38%),
        radial-gradient(ellipse at 95% 30%, rgba(185,154,90,.06), transparent 35%),
        linear-gradient(135deg, #080808, #111110 52%, #050505);
    color: var(--white);
}
header[data-testid="stHeader"] { background: transparent; }
.block-container { max-width: 1540px; padding-top: 1rem; padding-bottom: 4rem; }
h1,h2,h3,p,label { color: var(--white); }
[data-testid="stMarkdownContainer"] p { color: #C7C1B4; }


.stButton > button {
    border: 1px solid rgba(185,154,90,.35);
    border-radius: 3px;
    background: linear-gradient(135deg,#201E19,#111110);
    color: #E8E1D2;
    font-family: 'Exo 2';
    font-weight: 800;
    letter-spacing: 1px;
    transition: .2s;
}
.stButton > button:hover {
    border-color: var(--gold-light);
    background: linear-gradient(135deg,#383020,#1B1915);
    color: #FFFFFF;
    transform: translateY(-2px);
}
.stSelectbox label,.stTextInput label,.stMultiSelect label {
    font-family: 'Rajdhani';
    font-weight: 700;
    letter-spacing: 2px;
    color: #B9A77E;
}
div[data-baseweb="select"] > div, div[data-baseweb="input"] {
    background: #171614;
    border-color: #655637;
    color: #F1EFE9;
}
.brand {
    font-family: 'Barlow Condensed';
    font-weight: 900;
    font-size: 38px;
    letter-spacing: 3px;
    line-height: 1;
}
.brand span { color: var(--gold); }
.nav-kicker {
    font-family: 'Rajdhani';
    font-size: 13px;
    letter-spacing: 4px;
    color: #A99A78;
    font-weight: 700;
}
.hero {
    position: relative;
    overflow: hidden;
    padding: 62px 38px 50px;
    margin: 22px 0 34px;
    border-left: 8px solid var(--gold);
    background:
        linear-gradient(105deg,#111110f5,#201D17c9),
        repeating-linear-gradient(135deg,transparent 0 22px,#ffffff06 22px 24px);
}
.hero:after {
    content: "NFL";
    position: absolute;
    right: 2%;
    top: -95px;
    font-family: 'Barlow Condensed';
    font-size: 330px;
    font-weight: 900;
    color: #ffffff08;
    transform: skew(-12deg);
    pointer-events: none;
}
.kicker {
    font-family: 'Rajdhani';
    font-size: 17px;
    letter-spacing: 7px;
    color: var(--gold-light);
    font-weight: 700;
}
.hero-title {
    position: relative;
    z-index: 1;
    font-family: 'Barlow Condensed';
    font-size: clamp(76px,12vw,158px);
    font-weight: 900;
    line-height: .76;
    letter-spacing: -2px;
    margin: 20px 0;
    text-transform: uppercase;
}
.hero-title span { color: var(--gold-light); }
.hero-sub {
    font-family: 'Rajdhani';
    font-size: 21px;
    letter-spacing: 3px;
    color: #C9C1B1;
    font-weight: 700;
}
.section-title {
    font-family: 'Barlow Condensed';
    font-size: 47px;
    font-weight: 900;
    letter-spacing: 2px;
    margin: 30px 0 12px;
    border-bottom: 2px solid rgba(185,154,90,.55);
    padding-bottom: 5px;
    text-transform: uppercase;
}
.micro {
    font-family: 'Rajdhani';
    font-size: 14px;
    font-weight: 700;
    letter-spacing: 3px;
    color: var(--gold);
}
.panel {
    background: linear-gradient(145deg,#201F1B,#111110);
    border: 1px solid var(--line);
    padding: 18px;
    margin: 8px 0;
}
.rank-row {
    display: flex;
    align-items: center;
    gap: 15px;
    background: linear-gradient(90deg,#211F1A,#111110);
    border-left: 4px solid var(--gold);
    padding: 10px 16px;
    margin: 8px 0;
    min-height: 82px;
}
.rank-num {
    flex: 0 0 62px;
    width: 62px;
    text-align: center;
    white-space: nowrap;
    font-family: 'Barlow Condensed';
    font-size: 43px;
    font-weight: 900;
    color: #C5A66A;
    line-height: 1;
}
.rank-name {
    flex: 1;
    min-width: 0;
    font-family: 'Exo 2';
    font-weight: 900;
    font-size: 16px;
}
.rank-score {
    flex: 0 0 72px;
    text-align: right;
    font-family: 'Barlow Condensed';
    font-size: 40px;
    font-weight: 900;
    color: #E5D4AD;
}
.tile {
    background: linear-gradient(145deg,#201F1B,#111110);
    border: 1px solid rgba(185,154,90,.20);
    padding: 14px 8px;
    text-align: center;
    min-height: 132px;
}
.tile img {
    width: 78px;
    height: 78px;
    object-fit: contain;
    filter: drop-shadow(0 5px 10px #000b);
}
.profile-hero {
    padding: 30px;
    margin: 22px 0;
    border-left: 9px solid var(--team);
    background: linear-gradient(110deg,color-mix(in srgb,var(--team) 34%,#171614),#090909 76%);
    position: relative;
    overflow: hidden;
}
.profile-name {
    font-family: 'Barlow Condensed';
    font-size: clamp(55px,9vw,112px);
    font-weight: 900;
    line-height: .85;
    text-transform: uppercase;
}
.big-rating {
    font-family: 'Barlow Condensed';
    font-size: 116px;
    font-weight: 900;
    line-height: .9;
    color: #E5D4AD;
}
.logo-large { width: min(245px,100%); filter: drop-shadow(0 12px 20px #000b); }
.statbox {
    background: linear-gradient(145deg,#242118,#111110);
    border-top: 3px solid var(--gold);
    padding: 15px 8px;
    text-align: center;
    margin-bottom: 10px;
}
.stat-label {
    font-family: 'Rajdhani';
    font-size: 14px;
    font-weight: 700;
    letter-spacing: 2px;
    color: #B9AC91;
}
.stat-value {
    font-family: 'Barlow Condensed';
    font-size: 48px;
    font-weight: 900;
    line-height: 1.05;
    color: #E4D3AA;
}
.bar-track {
    height: 13px;
    background: #302D26;
    border-radius: 2px;
    overflow: hidden;
    margin: 7px 0 15px;
}
.bar-fill {
    height: 100%;
    background: linear-gradient(90deg,#806735,#C5A66A);
    box-shadow: 0 0 12px rgba(185,154,90,.25);
}
.metric-card {
    padding: 18px;
    background: linear-gradient(145deg,#201F1B,#111110);
    border: 1px solid var(--line);
    min-height: 112px;
}
.metric-label {
    font-family: 'Rajdhani';
    letter-spacing: 3px;
    color: #B9AC91;
    font-weight: 700;
    font-size: 13px;
}
.metric-number {
    font-family: 'Barlow Condensed';
    font-size: 54px;
    font-weight: 900;
    line-height: 1;
    color: #E4D3AA;
}
.tier {
    display: inline-block;
    padding: 4px 9px;
    font-family: 'Rajdhani';
    font-size: 12px;
    letter-spacing: 2px;
    font-weight: 800;
    border: 1px solid #927947;
    color: #D7C18F;
    margin-left: 8px;
}
.cinematic {
    --team: #123;
    --team2: #456;
    position: relative;
    overflow: hidden;
    min-height: 490px;
    display: flex;
    justify-content: center;
    align-items: center;
    text-align: center;
    margin: 10px 0 30px;
    background:
        radial-gradient(circle at center,color-mix(in srgb,var(--team) 70%,transparent),transparent 66%),
        linear-gradient(135deg,#020202,#171614 55%,#020202);
    border: 1px solid color-mix(in srgb,var(--team) 75%,transparent);
    isolation: isolate;
}
.cinematic:before {
    content: "";
    position: absolute;
    inset: 0;
    z-index: -1;
    background: repeating-linear-gradient(0deg,transparent 0 5px,#ffffff09 5px 6px);
    animation: scan 5s linear infinite;
}
.intro-content { position: relative; z-index: 5; animation: reveal 1s ease both; }
.intro-kicker {
    font-family: 'Rajdhani';
    font-weight: 700;
    letter-spacing: 7px;
    color: #C9C1B1;
    font-size: 16px;
}
.intro-logo {
    display: block;
    width: 190px;
    height: 190px;
    object-fit: contain;
    margin: 20px auto;
    filter: drop-shadow(0 0 28px var(--team));
    animation: impact .9s cubic-bezier(.2,.8,.2,1) both;
}
.intro-team {
    font-family: 'Barlow Condensed';
    font-size: clamp(55px,9vw,105px);
    font-weight: 900;
    line-height: .9;
    text-transform: uppercase;
    text-shadow: 0 5px 25px #000;
}
.intro-tag {
    margin-top: 18px;
    font-family: 'Exo 2';
    font-weight: 900;
    font-size: 18px;
    letter-spacing: 6px;
    color: var(--team2);
}
.claw {
    position: absolute;
    z-index: 2;
    top: -20%;
    height: 145%;
    width: 13px;
    background: linear-gradient(180deg,transparent,#fff 20%,var(--team) 50%,#fff 80%,transparent);
    box-shadow: 0 0 28px var(--team),0 0 60px var(--team);
    transform: rotate(24deg) scaleY(0);
    animation: claw .8s ease-out forwards;
}
.c1 { left: 25%; animation-delay: .04s; }
.c2 { left: 48%; animation-delay: .17s; }
.c3 { left: 71%; animation-delay: .3s; }
.fx:after { content:""; position:absolute; inset:-50%; pointer-events:none; }
.fx-fire:after {
    background: radial-gradient(ellipse at bottom,var(--team),transparent 55%);
    animation: pulse 1.5s ease-in-out infinite alternate;
}
.fx-lightning:after {
    background: linear-gradient(115deg,transparent 40%,var(--team) 50%,transparent 54%);
    transform: translateX(-100%);
    animation: flash .8s ease-out;
}
.fx-storm:after {
    background: repeating-linear-gradient(120deg,transparent 0 50px,var(--team) 51px,transparent 54px);
    animation: storm 2s linear infinite;
    opacity: .4;
}
.fx-wave:after {
    background: radial-gradient(ellipse,transparent 35%,var(--team) 70%,transparent 72%);
    animation: wave 2s ease-out infinite;
}
.fx-speed:after {
    background: repeating-linear-gradient(100deg,transparent 0 70px,var(--team) 72px,transparent 75px);
    animation: speed .6s linear infinite;
    opacity: .35;
}
.fx-spotlight:after {
    background: conic-gradient(from 0deg at 50% 50%,transparent,var(--team),transparent 30%);
    animation: spin 5s linear infinite;
    opacity: .4;
}
@keyframes reveal {
    from { opacity:0; transform:translateY(35px) scale(.94); }
    to { opacity:1; transform:none; }
}
@keyframes impact {
    0% { opacity:0; transform:scale(2.5) rotate(-12deg); }
    70% { opacity:1; transform:scale(.9) rotate(3deg); }
    100% { transform:none; }
}
@keyframes claw {
    0% { transform:rotate(24deg) scaleY(0); }
    45% { transform:rotate(24deg) scaleY(1); }
    100% { transform:rotate(24deg) scaleY(1); opacity:0; }
}
@keyframes scan { to { background-position-y:30px; } }
@keyframes pulse { to { transform:translateY(-8%); opacity:.55; } }
@keyframes flash {
    0% { transform:translateX(-100%); opacity:0; }
    30% { opacity:1; }
    100% { transform:translateX(100%); opacity:0; }
}
@keyframes storm { to { transform:translate(8%,8%); } }
@keyframes wave {
    from { transform:scale(.3); opacity:.7; }
    to { transform:scale(1.4); opacity:0; }
}
@keyframes speed { to { transform:translateX(20%); } }
@keyframes spin { to { transform:rotate(360deg); } }

[data-testid="stDataFrame"] { border:1px solid var(--line); }
hr { border-color:rgba(185,154,90,.25); }
@media(max-width:700px) {
    .hero { padding:40px 20px; }
    .rank-row { gap:8px; padding:9px 7px; }
    .rank-num { flex-basis:48px; width:48px; font-size:35px; }
    .rank-name { font-size:12px; }
    .rank-score { flex-basis:50px; font-size:30px; }
    .cinematic { min-height:410px; }
}

    
</style>
""", unsafe_allow_html=True)


# ============================================================
# SHARED COMPONENTS
# ============================================================

def hero(kicker, title, accent, subtitle):
    st.markdown(
        f'<div class="hero"><div class="kicker">{kicker}</div>'
        f'<div class="hero-title">{title}<br><span>{accent}</span></div>'
        f'<div class="hero-sub">{subtitle}</div></div>',
        unsafe_allow_html=True,
    )


def section(text):
    st.markdown(f'<div class="section-title">{html.escape(text)}</div>', unsafe_allow_html=True)


def metric(label, value, suffix="", team_color=None):
    style = ""

    if team_color:
        color = html.escape(str(team_color), quote=True)
        style = (
            f' style="background: linear-gradient(145deg, {color}35, #111110);'
            f' border: 1px solid {color}88;"'
        )

    st.markdown(
        f'<div class="metric-card"{style}>'
        f'<div class="metric-label">{html.escape(str(label))}</div>'
        f'<div class="metric-number">{html.escape(str(value))}{suffix}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

def get_leader_strengths(team_code):
    if team_metrics.empty:
        return []

    team_code = {"LAR": "LA"}.get(team_code, team_code)

    leader_rows = team_metrics[
        team_metrics["team"].astype(str) == team_code
    ]

    if leader_rows.empty:
        return []

    candidates = [
        {
            "label": "OFFENSIVE EPA / PLAY",
            "column": "off_epa_per_play",
            "category": "OFFENSE",
            "higher": True,
            "format": "number",
        },
        {
            "label": "RED-ZONE TD RATE",
            "column": "red_zone_td_rate",
            "category": "OFFENSE",
            "higher": True,
            "format": "percent",
        },
        {
            "label": "THIRD-DOWN CONVERSION",
            "column": "third_down_conversion_rate",
            "category": "OFFENSE",
            "higher": True,
            "format": "percent",
        },
        {
            "label": "EXPLOSIVE-PLAY RATE",
            "column": "overall_explosive_rate",
            "category": "OFFENSE",
            "higher": True,
            "format": "percent",
        },
        {
            "label": "DEFENSIVE EPA / PLAY",
            "column": "def_epa_allowed_per_play",
            "category": "DEFENSE",
            "higher": False,
            "format": "number",
        },
        {
            "label": "YARDS ALLOWED / PLAY",
            "column": "def_yards_allowed_per_play",
            "category": "DEFENSE",
            "higher": False,
            "format": "number",
        },
        {
            "label": "EXPLOSIVE-PLAY RATE ALLOWED",
            "column": "overall_explosive_rate_allowed",
            "category": "DEFENSE",
            "higher": False,
            "format": "percent",
        },
        {
            "label": "PUNT INSIDE-20 RATE",
            "column": "punt_inside_twenty_rate",
            "category": "SPECIAL TEAMS",
            "higher": True,
            "format": "percent",
        },
        {
            "label": "POINT DIFFERENTIAL / GAME",
            "column": "on_field_avg_point_differential",
            "category": "ON-FIELD",
            "higher": True,
            "format": "number",
        },
    ]

    strengths = []

    for candidate in candidates:
        column = candidate["column"]

        if column not in team_metrics.columns:
            continue

        values = pd.to_numeric(team_metrics[column], errors="coerce")
        if values.notna().sum() < 16:
            continue

        rank = values.rank(
            ascending=not candidate["higher"],
            method="min"
        )

        team_index = leader_rows.index[0]
        team_rank = rank.loc[team_index]

        if pd.isna(team_rank):
            continue

        candidate["rank"] = int(team_rank)
        candidate["value"] = float(leader_rows.iloc[0][column])
        strengths.append(candidate)

    strengths.sort(key=lambda item: item["rank"])

    selected = []
    categories = set()

    for strength in strengths:
        if strength["category"] in categories:
            continue

        selected.append(strength)
        categories.add(strength["category"])

        if len(selected) == 3:
            break

    for strength in strengths:
        if len(selected) == 3:
            break
        if strength not in selected:
            selected.append(strength)

    return selected

def rank_row(row, button_key=None):
    code = str(row["team"]).upper()
    info = TEAMS.get(code)
    if not info:
        return
    st.markdown(
        f'<div class="rank-row"><div class="rank-num">#{int(row["rank"]):02d}</div>'
        f'{logo(code, 58)}<div class="rank-name">{html.escape(info["name"].upper())}'
        f'<div class="micro">{info["conf"]} / {info["div"]}</div></div>'
        f'<div class="rank-score">{float(row["overall_rating"]):.1f}</div></div>',
        unsafe_allow_html=True,
    )
    if button_key and st.button(f"OPEN {code} PROFILE →", key=button_key):
        go("PROFILE", code, True)


def rating_bar(label, value, color=None):
    pct = max(0, min(100, float(value)))
    color_style = f"background:linear-gradient(90deg,{color},#ffffff)" if color else ""
    st.markdown(
        f'<div style="display:flex;justify-content:space-between;gap:12px">'
        f'<span class="micro">{html.escape(label)}</span><b>{float(value):.1f}</b></div>'
        f'<div class="bar-track"><div class="bar-fill" style="width:{pct}%;{color_style}"></div></div>',
        unsafe_allow_html=True,
    )


def header():
    left, right = st.columns([1.5, 5])
    with left:
        st.markdown('<div class="brand">NFL <span>RATINGS.</span></div>', unsafe_allow_html=True)
    with right:
        nav = st.columns(8)
        items = [
            ("HOME", "HOME"),
            ("TEAMS", "TEAMS"),
            ("RANKINGS", "RANKINGS"),
            ("WAR ROOM", "WAR"),
            ("WEEKLY", "WEEKLY"),
            ("HISTORY", "HISTORY"),
            ("REPORT", "REPORT"),
            ("METHOD", "METHOD"),
        ]
        for col, (label, page) in zip(nav, items):
            with col:
                if st.button(label, key=f"nav_{page}", use_container_width=True, type="secondary"):
                    go(page)
    st.markdown(
        '<div class="nav-kicker">THE NFL RATINGS ENGINE / 2026 SEASON / LEAGUE HEADQUARTERS</div>',
        unsafe_allow_html=True,
    )
    st.markdown("---")


def footer():
    st.markdown("---")
    st.markdown(
        '<div style="text-align:center;padding:20px;color:#A99A78;font-family:Rajdhani;'
        'letter-spacing:4px;font-weight:700">'
        'NFL RATINGS ENGINE / BUILT FOR THE GAME / DATA-DRIVEN. TRANSPARENT. INDEPENDENT.</div>',
        unsafe_allow_html=True,
    )


# ============================================================
# HOME / BROADCAST HQ
# ============================================================


def render_home():
    hero("THE LEAGUE. REIMAGINED.", "WHO RUNS", "THE NFL?", "32 TEAMS. ONE RATINGS ENGINE. NO OPINIONS REQUIRED.")

    if rankings is None:
        st.error(f"Rankings CSV could not be loaded. Expected: {CSV_PATH}")
        return

    ordered = rankings.sort_values("rank")
    leader = ordered.iloc[0]
    leader_code = str(leader["team"])
    leader_info = TEAMS.get(leader_code, {})
    top = ordered.head(5)
    bottom = ordered.tail(5).sort_values("rank", ascending=False)
    schedule = get_schedule()
    results = get_results()

    completed_ids = {
        str(game.get("schedule_id") or game.get("id"))
        for game in results
        if game.get("schedule_id") or game.get("id")
    }

    remaining_weeks = [
        int(game["week"])
        for game in schedule
        if game.get("week") is not None
           and str(game.get("id", "")) not in completed_ids
    ]

    current_week = min(remaining_weeks) if remaining_weeks else "OFFSEASON"

    st.markdown('<div class="micro">CURRENT LEAGUE LEADER</div>', unsafe_allow_html=True)

    a, b = st.columns([2, 1])

    with a:
        st.markdown(
            f'<div class="profile-hero" style="--team:{leader_info.get("color","#B99A5A")}">'
            f'<div class="micro">#1 IN THE NFL / CURRENT RATINGS LEADER</div>'
            f'<div style="display:flex;align-items:center;gap:25px;flex-wrap:wrap">'
            f'{logo(leader_code, 130)}<div><div class="profile-name">{html.escape(leader_info.get("name",""))}</div>'
            f'<div class="big-rating">{float(leader["overall_rating"]):.1f}</div>'
            f'<div class="micro">OVERALL RATING</div></div></div></div>',
            unsafe_allow_html=True,
        )

        if st.button(f"ENTER THE {leader_code} PROFILE →", key="home_leader"):
            go("PROFILE", leader_code, True)

    with b:
        team_color = leader_info.get("color", "#B99A5A")

        metric("CURRENT WEEK", current_week, team_color=team_color)

        leader_strengths = get_leader_strengths(leader_code)

        for strength in leader_strengths:
            if strength["format"] == "percent":
                display_value = f'{strength["value"]:.1%}'
            else:
                display_value = f'{strength["value"]:.3f}'

            metric(
                strength["label"],
                display_value,
                team_color=team_color,
            )

        metric(
            "TOP-TO-BOTTOM GAP",
            f'{ordered.iloc[0]["overall_rating"] - ordered.iloc[-1]["overall_rating"]:.1f}',
            team_color=team_color,
        )

    section("THE TOP FIVE")

    for _, row in top.iterrows():
        rank_row(row, f"home_top_{row['team']}")

    section("THE BOTTOM FIVE")

    for _, row in bottom.iterrows():
        rank_row(row, f"home_bottom_{row['team']}")

    section("AROUND THE LEAGUE")

    award_specs = [
        ("OFFENSE", "offensive_rating"),
        ("DEFENSE", "defensive_rating"),
        ("SPECIAL TEAMS", "special_teams_rating"),
        ("DISCIPLINE", "discipline_rating"),
        ("ON-FIELD", "on_field_rating"),
    ]

    category_rows = [
        (award_specs[:2], False),
        (award_specs[2:4], False),
        (award_specs[4:], True),
    ]

    for row_specs, centered in category_rows:
        if centered:
            _, category_col, _ = st.columns([1, 2, 1])
            category_columns = [category_col]
        else:
            category_columns = st.columns(2)

        for col, (label, rating_col) in zip(category_columns, row_specs):
            with col:

                # Clickable category heading
                st.markdown(
                    f'<div class="section-title" style="cursor:pointer;" '
                    f'title="View all 32 teams">'
                    f'TOP FIVE — {html.escape(label)} <span style="font-size:0.75em;opacity:0.65;">↗</span></div>',
                    unsafe_allow_html=True,
                )

                # Top five teams in this category
                category_top = rankings.sort_values(
                    rating_col,
                    ascending=False
                ).head(5)

                for position, (_, row) in enumerate(category_top.iterrows(), start=1):
                    code = {"LA": "LAR"}.get(
                        str(row["team"]),
                        str(row["team"])
                    )

                    team_name = TEAMS.get(code, {}).get("name", code)
                    rating = float(row[rating_col])

                    left, right = st.columns([1, 5])

                    with left:

                        st.markdown(
                            logo(code, width= 60),
                            unsafe_allow_html=True,
                        )
                    with right:
                        if st.button(
                                f"#{position}  {team_name.upper()} — {rating:.1f} →",
                                key=f"home_{rating_col}_{code}",
                                use_container_width=True,
                        ):
                            go("PROFILE", code, True)

    st.caption(
        "Category leaderboards are calculated from the current ratings file. "
        "Select any team to view its profile."
    )


# ============================================================
# TEAM SELECT
# ============================================================

def render_teams():
    hero("32 TEAMS. ONE LEAGUE.", "CHOOSE", "YOUR SIDE.", "SELECT A LOGO TO ENTER THE TEAM EXPERIENCE.")
    conferences = {
        "AFC": {
            "East": ["BUF", "MIA", "NE", "NYJ"],
            "North": ["BAL", "CIN", "CLE", "PIT"],
            "South": ["HOU", "IND", "JAX", "TEN"],
            "West": ["DEN", "KC", "LV", "LAC"],
        },
        "NFC": {
            "East": ["DAL", "NYG", "PHI", "WAS"],
            "North": ["CHI", "DET", "GB", "MIN"],
            "South": ["ATL", "CAR", "NO", "TB"],
            "West": ["ARI", "LAR", "SF", "SEA"],
        },
    }
    for conference, divisions in conferences.items():
        section(f"{conference} CONFERENCE")
        for division, codes in divisions.items():
            st.markdown(f'<div class="micro">{division.upper()} DIVISION</div>', unsafe_allow_html=True)
            cols = st.columns(4)
            for col, code in zip(cols, codes):
                info = TEAMS[code]
                row = get_team_row(code)
                with col:
                    st.markdown(
                        f'<div class="tile" style="border-top:3px solid {info["color"]}">'
                        f'<img src="{info["logo"]}" alt="{html.escape(info["name"])}">'
                        f'<div style="font-family:Exo 2;font-size:12px;font-weight:900;margin-top:5px">'
                        f'{html.escape(info["name"].upper())}</div></div>',
                        unsafe_allow_html=True,
                    )
                    if row is not None:
                        record = get_records()[code]
                        st.caption(
                            f'RANK #{int(row["rank"])} / '
                            f'{float(row["overall_rating"]):.1f} RATING / '
                            f'{record["W"]}-{record["L"]}-{record["T"]}'
                        )
                    if st.button(f"ENTER {code} →", key=f"team_{code}", use_container_width=True):
                        go("PROFILE", code, True)


def render_dna_heatmap(title, zones, row, frame, defensive=False):
    st.markdown(f"#### {title}")

    cells = []

    for label, column, plays_column in zones:
        if column not in frame.columns or plays_column not in frame.columns:
            continue

        team_value = pd.to_numeric(
            pd.Series([row.get(column)]), errors="coerce"
        ).iloc[0]

        league_values = pd.to_numeric(frame[column], errors="coerce")
        play_counts = pd.to_numeric(frame[plays_column], errors="coerce")

        valid = (
            league_values.notna()
            & play_counts.notna()
            & (play_counts > 0)
        )

        if pd.isna(team_value) or not valid.any():
            continue

        league_average = (
            (league_values[valid] * play_counts[valid]).sum()
            / play_counts[valid].sum()
        )

        difference = team_value - league_average

        # For defense, lower EPA allowed is better.
        if defensive:
            difference *= -1

        if difference > 0.025:
            background = "#176b45"
        elif difference < -0.025:
            background = "#9e3030"
        else:
            background = "#9b862f"

        cells.append({
            "label": label,
            "team": team_value,
            "league": league_average,
            "plays": row.get(plays_column, 0),
            "background": background,
        })

    if not cells:
        st.info("Field-zone data is unavailable.")
        return

    # Deep passing on top, short passing underneath.
    if any(
        cell["label"].startswith(("Short", "Deep"))
        for cell in cells
    ):
        cells.sort(
            key=lambda item: (
                0 if item["label"].startswith("Deep") else 1,
                item["label"]
            )
        )

    html_cells = ""

    for cell in cells:
        html_cells += f"""
        <div style="
            background:{cell['background']};
            border:1px solid rgba(255,255,255,0.18);
            border-radius:5px;
            padding:16px 8px;
            text-align:center;
            color:white;
            min-height:105px;
        ">
            <div style="font-size:13px;font-weight:700;">
                {html.escape(cell['label'].upper())}
            </div>
            <div style="font-size:25px;font-weight:800;margin:8px 0;">
                {cell['team']:+.3f}
            </div>
            <div style="font-size:11px;opacity:0.9;">
                League: {cell['league']:+.3f}
            </div>
            <div style="font-size:10px;opacity:0.75;margin-top:5px;">
                {int(cell['plays'])} plays
            </div>
        </div>
        """

    st.markdown(
        f"""
        <div style="
            display:grid;
            grid-template-columns:repeat(3,minmax(0,1fr));
            gap:7px;
            padding:8px;
            background:#17251f;
            border:2px solid #b08d45;
            border-radius:8px;
        ">
            {html_cells}
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.caption(
        "Green = better than league average · "
        "Gold = near league average · "
        "Red = worse than league average"
    )

# ============================================================
# TEAM DNA ANALYSIS
# ============================================================

DNA_METRICS = {
    "Offensive Efficiency": {
        "off_epa_per_play": ("EPA per Play", True),
        "off_success_rate": ("Success Rate", True),
        "off_yards_per_play": ("Yards per Play", True),
        "pass_epa_per_play": ("Passing EPA per Play", True),
        "rush_epa_per_play": ("Rushing EPA per Play", True),
        "overall_explosive_rate": ("Explosive Play Rate", True),
        "off_early_down_success_rate": ("Early Down Success", True),
        "off_first_down_success_rate": ("First Down Success", True),
        "off_second_down_success_rate": ("Second Down Success", True),
    },
    "Defensive Performance": {
        "def_epa_allowed_per_play": ("EPA Allowed per Play", False),
        "def_success_rate_allowed": ("Success Rate Allowed", False),
        "def_yards_allowed_per_play": ("Yards Allowed per Play", False),
        "pass_epa_allowed_per_play": ("Passing EPA Allowed", False),
        "rush_epa_allowed_per_play": ("Rushing EPA Allowed", False),
        "overall_explosive_rate_allowed": ("Explosive Play Rate Allowed", False),
        "def_early_down_success_allowed": ("Early Down Success Allowed", False),
        "def_first_down_success_allowed": ("First Down Success Allowed", False),
        "def_second_down_success_allowed": ("Second Down Success Allowed", False),
    },
    "Situational Offense": {
        "dna_third_down_conversion_rate": ("Third Down Conversion", True),
        "dna_fourth_down_conversion_rate": ("Fourth Down Conversion", True),
        "dna_red_zone_td_rate": ("Red Zone TD Rate", True),
        "dna_red_zone_scoring_rate": ("Red Zone Scoring Rate", True),
    },
    "Situational Defense": {
        "dna_third_down_conversion_rate_allowed": ("Third Down Conversion Allowed", False),
        "dna_fourth_down_conversion_rate_allowed": ("Fourth Down Conversion Allowed", False),
        "dna_red_zone_td_rate_allowed": ("Red Zone TD Rate Allowed", False),
        "dna_red_zone_scoring_rate_allowed": ("Red Zone Scoring Rate Allowed", False),
    },
}

DNA_TENDENCIES = {
    "Offensive Identity": {
        "dna_pass_rate": "Pass Rate",
        "dna_rush_rate": "Rush Rate",
        "dna_shotgun_rate": "Shotgun Usage",
        "dna_no_huddle_rate": "No-Huddle Usage",
        "dna_short_pass_rate": "Short Pass Rate",
        "dna_deep_pass_rate": "Deep Pass Rate",
        "dna_run_left_rate": "Runs Left",
        "dna_run_middle_rate": "Runs Middle",
        "dna_run_right_rate": "Runs Right",
    },
    "Defensive Identity": {
        "dna_pass_rate_faced": "Opponent Pass Rate",
        "dna_rush_rate_faced": "Opponent Rush Rate",
        "dna_shotgun_rate_faced": "Opponent Shotgun Usage",
        "dna_no_huddle_rate_faced": "Opponent No-Huddle Usage",
        "dna_short_pass_rate_faced": "Opponent Short Pass Rate",
        "dna_deep_pass_rate_faced": "Opponent Deep Pass Rate",
        "dna_runs_left_rate_faced": "Opponent Runs Left",
        "dna_runs_middle_rate_faced": "Opponent Runs Middle",
        "dna_runs_right_rate_faced": "Opponent Runs Right",
    },
}


def get_dna_percentile(frame, column, value, higher_is_better=True):
    values = pd.to_numeric(frame[column], errors="coerce").dropna()
    if values.empty or pd.isna(value):
        return None

    percentile = (values <= value).mean() * 100

    if not higher_is_better:
        percentile = 100 - percentile

    return percentile


def get_dna_strengths_weaknesses(row, frame, limit=3):
    results = []

    for group, metrics in DNA_METRICS.items():
        for column, (label, higher_is_better) in metrics.items():
            if column not in frame.columns:
                continue

            value = pd.to_numeric(
                pd.Series([row.get(column)]),
                errors="coerce"
            ).iloc[0]

            percentile = get_dna_percentile(
                frame, column, value, higher_is_better
            )

            if percentile is None:
                continue

            results.append({
                "group": group,
                "label": label,
                "value": value,
                "percentile": percentile,
            })

    results.sort(key=lambda item: item["percentile"], reverse=True)

    strengths = results[:limit]
    weaknesses = sorted(
        results,
        key=lambda item: item["percentile"]
    )[:limit]

    return strengths, weaknesses


def get_most_similar_teams(code, frame, limit=3):
    similarity_columns = [
        # Offensive identity
        "dna_pass_rate",
        "dna_rush_rate",
        "dna_shotgun_rate",
        "dna_no_huddle_rate",
        "dna_short_pass_rate",
        "dna_deep_pass_rate",
        "dna_run_left_rate",
        "dna_run_middle_rate",
        "dna_run_right_rate",

        # Defensive identity
        "dna_pass_rate_faced",
        "dna_rush_rate_faced",
        "dna_shotgun_rate_faced",
        "dna_no_huddle_rate_faced",
        "dna_short_pass_rate_faced",
        "dna_deep_pass_rate_faced",
        "dna_runs_left_rate_faced",
        "dna_runs_middle_rate_faced",
        "dna_runs_right_rate_faced",

        # Efficiency
        "off_epa_per_play",
        "off_success_rate",
        "off_yards_per_play",
        "def_epa_allowed_per_play",
        "def_success_rate_allowed",
        "def_yards_allowed_per_play",

        # Situational performance
        "dna_third_down_conversion_rate",
        "dna_fourth_down_conversion_rate",
        "dna_red_zone_td_rate",
        "dna_third_down_conversion_rate_allowed",
        "dna_fourth_down_conversion_rate_allowed",
        "dna_red_zone_td_rate_allowed",
    ]

    columns = [
        column for column in similarity_columns
        if column in frame.columns
    ]

    data = frame[["team"] + columns].copy()

    for column in columns:
        data[column] = pd.to_numeric(data[column], errors="coerce")

    data[columns] = data[columns].fillna(data[columns].mean())
    standardized = (
        data[columns] - data[columns].mean()
    ) / data[columns].std().replace(0, 1)

    target_index = data.index[
        data["team"].astype(str).str.upper() == code.upper()
    ]

    if len(target_index) == 0:
        return pd.DataFrame()

    target = standardized.loc[target_index[0]]
    data["similarity_distance"] = (
        (standardized - target) ** 2
    ).mean(axis=1) ** 0.5

    data = data[data["team"].astype(str).str.upper() != code.upper()]

    return data.nsmallest(
        limit, "similarity_distance"
    )[["team", "similarity_distance"]].reset_index(drop=True)



# ============================================================
# TEAM PROFILE
# ============================================================

def get_next_game(code):
    today = datetime.now().date()
    upcoming_games = []

    for game in get_schedule():
        if code not in (game.get("home"), game.get("away")):
            continue

        try:
            game_date = datetime.strptime(
                game.get("date", ""), "%Y-%m-%d"
            ).date()
        except (ValueError, TypeError):
            continue

        if game_date > today:
            upcoming_games.append(game)

    if not upcoming_games:
        return None

    return min(
        upcoming_games,
        key=lambda game: (game.get("date", ""), game.get("kickoff", ""))
    )

def calculate_win_probability(team_rating, opponent_rating, is_home):
    home_field_advantage = 2.0 if is_home else 0.0

    rating_difference = (
        team_rating - opponent_rating + home_field_advantage
    )

    probability = 1 / (
        1 + math.exp(-rating_difference / 25)
    )

    return max(0.05, min(0.95, probability))

def build_key_statistical_battles(team_stats, opponent_stats):
    battles = [
        {
            "category": "Turnover Battle",
            "team_metric": "net_turnovers",
            "opponent_metric": "net_turnovers",
            "team_label": "Net Turnovers / game",
            "opponent_label": "Net Turnovers / game",
            "team_games": True,
            "opponent_games": True,
            "lower_is_better": False,
            "description": "Create turnovers while protecting the football.",
        },
        {
            "category": "Pass Protection",
            "team_metric": "sack_rate_allowed",
            "opponent_metric": "sack_rate_allowed",
            "team_label": "Sack Rate Allowed",
            "opponent_label": "Sack Rate Allowed",
            "lower_is_better": True,
            "description": "Keep the quarterback protected and limit sacks.",
        },
        {
            "category": "Fourth Down",
            "team_metric": "dna_fourth_down_conversion_rate",
            "opponent_metric": "dna_fourth_down_conversion_rate",
            "team_label": "Conversion Rate",
            "opponent_label": "Conversion Rate",
            "team_sample": "dna_fourth_down_attempts",
            "opponent_sample": "dna_fourth_down_attempts",
            "lower_is_better": False,
            "minimum": 5,
            "description": "Convert critical fourth downs and keep drives alive.",
        },
        {
            "category": "Penalty Discipline",
            "team_metric": "penalty_yards",
            "opponent_metric": "penalty_yards",
            "team_label": "Penalty Yards / game",
            "opponent_label": "Penalty Yards / game",
            "team_games": True,
            "opponent_games": True,
            "lower_is_better": True,
            "description": "Avoid costly penalties and giving away field position.",
        },
    ]

    def number(row, column):
        value = pd.to_numeric(
            pd.Series([row.get(column)]),
            errors="coerce",
        ).iloc[0]

        return None if pd.isna(value) else float(value)

    results = []

    for battle in battles:
        if battle["category"] == "Turnover Battle":
            team_takeaways = number(team_stats, "total_takeaways")
            team_giveaways = number(team_stats, "total_giveaways")
            opponent_takeaways = number(opponent_stats, "total_takeaways")
            opponent_giveaways = number(opponent_stats, "total_giveaways")

            if None in (
                team_takeaways,
                team_giveaways,
                opponent_takeaways,
                opponent_giveaways,
            ):
                continue

            team_value = team_takeaways - team_giveaways
            opponent_value = opponent_takeaways - opponent_giveaways
        else:
            team_value = number(team_stats, battle["team_metric"])
            opponent_value = number(
                opponent_stats, battle["opponent_metric"]
            )


        if team_value is None or opponent_value is None:
            continue

        if battle.get("team_games"):
            games = number(team_stats, "on_field_games_played")
            if games is None or games <= 0:
                continue
            team_value /= games

        if battle.get("opponent_games"):
            games = number(opponent_stats, "on_field_games_played")
            if games is None or games <= 0:
                continue
            opponent_value /= games

        team_sample = battle.get("team_sample")
        opponent_sample = battle.get("opponent_sample")

        if team_sample:
            sample = number(team_stats, team_sample)
            if sample is None or sample < battle["minimum"]:
                continue

        if opponent_sample:
            sample = number(opponent_stats, opponent_sample)
            if sample is None or sample < battle["minimum"]:
                continue

        if battle["lower_is_better"]:
            edge = opponent_value - team_value
        else:
            edge = team_value - opponent_value

        results.append({
            "category": battle["category"],
            "team_value": team_value,
            "opponent_value": opponent_value,
            "team_label": battle["team_label"],
            "opponent_label": battle["opponent_label"],
            "edge": edge,
            "description": battle["description"],
        })

    results.sort(
        key=lambda item: abs(item["edge"]),
        reverse=True,
    )

    return results[:3]

def build_matchup_analysis(team_stats, opponent_stats):
    comparisons = [
        {
            "category": "Overall Efficiency",
            "offense": "off_epa_per_play",
            "defense": "def_epa_allowed_per_play",
            "offense_sample": "offensive_plays",
            "defense_sample": "defensive_plays",
            "threshold": 0.025,
            "unit": "EPA/play",
        },
        {
            "category": "Passing",
            "offense": "pass_epa_per_play",
            "defense": "pass_epa_allowed_per_play",
            "offense_sample": "pass_plays",
            "defense_sample": "def_pass_plays_faced",
            "threshold": 0.035,
            "unit": "EPA/play",
        },
        {
            "category": "Rushing",
            "offense": "rush_epa_per_play",
            "defense": "rush_epa_allowed_per_play",
            "offense_sample": "rush_plays",
            "defense_sample": "def_rush_plays_faced",
            "threshold": 0.025,
            "unit": "EPA/play",
        },
        {
            "category": "Explosive Plays",
            "offense": "overall_explosive_rate",
            "defense": "overall_explosive_rate_allowed",
            "offense_sample": "offensive_plays",
            "defense_sample": "defensive_plays",
            "threshold": 0.015,
            "unit": "rate",
        },
        {
            "category": "Third Down",
            "offense": "dna_third_down_conversion_rate",
            "defense": "dna_third_down_conversion_rate_allowed",
            "offense_sample": "dna_third_down_attempts",
            "defense_sample": "dna_third_down_attempts_allowed",
            "threshold": 0.04,
            "unit": "rate",
        },
        {
            "category": "Red Zone",
            "offense": "dna_red_zone_td_rate",
            "defense": "dna_red_zone_td_rate_allowed",
            "offense_sample": "dna_red_zone_trips",
            "defense_sample": "dna_red_zone_trips_allowed",
            "threshold": 0.06,
            "unit": "rate",
        },
    ]

    advantages = []
    concerns = []

    def number(row, column):
        value = pd.to_numeric(
            pd.Series([row.get(column)]),
            errors="coerce",
        ).iloc[0]

        return None if pd.isna(value) else float(value)


    def add_comparison(category, side, edge, threshold,
                       team_value, opponent_value, unit):
        normalized_edge = edge / threshold

        if edge > threshold:
            advantages.append({
                "category": category,
                "side": side,
                "team_value": team_value,
                "opponent_value": opponent_value,
                "edge": edge,
                "strength": normalized_edge,
                "unit": unit,
            })
        elif edge < -threshold:
            concerns.append({
                "category": category,
                "side": side,
                "team_value": team_value,
                "opponent_value": opponent_value,
                "edge": edge,
                "strength": abs(normalized_edge),
                "unit": unit,
            })
    for item in comparisons:
        category = item["category"]
        threshold = item["threshold"]

        # Selected team's offense vs. opponent's defense.
        offense_value = number(team_stats, item["offense"])
        opponent_defense = number(opponent_stats, item["defense"])

        offense_plays = number(
            team_stats, item["offense_sample"]
        )
        opponent_defense_plays = number(
            opponent_stats, item["defense_sample"]
        )

        if (
            offense_value is not None
            and opponent_defense is not None
            and offense_plays is not None
            and opponent_defense_plays is not None
            and offense_plays >= 50
            and opponent_defense_plays >= 50
        ):
            edge = offense_value - opponent_defense

            add_comparison(
                category,
                "OFFENSE",
                edge,
                threshold,
                offense_value,
                opponent_defense,
                item["unit"],
            )

        # Selected team's defense vs. opponent's offense.
        opponent_offense = number(
            opponent_stats, item["offense"]
        )
        defense_value = number(
            team_stats, item["defense"]
        )

        opponent_offense_plays = number(
            opponent_stats, item["offense_sample"]
        )
        defense_plays = number(
            team_stats, item["defense_sample"]
        )

        if (
            opponent_offense is not None
            and defense_value is not None
            and opponent_offense_plays is not None
            and defense_plays is not None
            and opponent_offense_plays >= 50
            and defense_plays >= 50
        ):
            edge = opponent_offense - defense_value

            add_comparison(
                category,
                "DEFENSE",
                edge,
                threshold,
                defense_value,
                opponent_offense,
                item["unit"],
            )

    advantages.sort(
        key=lambda item: item["strength"],
        reverse=True,
    )

    concerns.sort(
        key=lambda item: item["strength"],
        reverse=True,
    )

    return advantages, concerns

def build_keys_to_victory(advantages, concerns):
    keys = []

    advantages = sorted(
        advantages,
        key=lambda item: item["strength"],
        reverse=True,
    )

    concerns = sorted(
        concerns,
        key=lambda item: item["strength"],
        reverse=True,
    )

    # Turn offensive advantages into game-plan recommendations.
    for item in advantages:
        if item["side"] != "OFFENSE":
            continue

        category = item["category"]

        recommendations = {
            "Overall Efficiency": (
                "Stay ahead of the chains and sustain efficient drives. "
                "Make the opponent defend the entire field."
            ),
            "Passing": (
                "Attack through the air. Use the passing game to create "
                "favorable matchups and move the chains."
            ),
            "Rushing": (
                "Establish the ground game and use it to control the "
                "tempo and create manageable situations."
            ),
            "Explosive Plays": (
                "Look for opportunities to generate explosive gains. "
                "Take calculated shots downfield."
            ),
            "Third Down": (
                "Capitalize on third-down opportunities and keep drives "
                "alive instead of settling for short possessions."
            ),
            "Red Zone": (
                "Finish drives with touchdowns. Take advantage of "
                "opportunities inside the opponent's 20-yard line."
            ),
        }

        recommendation = recommendations.get(category)

        if recommendation:
            keys.append(recommendation)

    # Turn defensive advantages into game-plan recommendations.
    for item in advantages:
        if item["side"] != "DEFENSE":
            continue

        category = item["category"]

        recommendations = {
            "Overall Efficiency": (
                "Make the opponent earn every yard. Limit efficient "
                "drives and force difficult situations."
            ),
            "Passing": (
                "Disrupt the opposing passing game. Pressure the "
                "quarterback and make completions difficult."
            ),
            "Rushing": (
                "Control the line of scrimmage and make the opponent "
                "one-dimensional."
            ),
            "Explosive Plays": (
                "Keep everything in front of the defense. Prevent "
                "big plays and force the opponent to sustain long drives."
            ),
            "Third Down": (
                "Get off the field on third down and prevent the "
                "opponent from extending possessions."
            ),
            "Red Zone": (
                "Tighten up in the red zone and force field goals "
                "instead of allowing touchdowns."
            ),
        }

        recommendation = recommendations.get(category)

        if recommendation:
            keys.append(recommendation)

    # Address the selected team's statistical weaknesses.
    for item in concerns:
        category = item["category"]
        side = item["side"]

        if side == "OFFENSE":
            recommendations = {
                "Overall Efficiency": (
                    "Avoid negative plays and stay on schedule. "
                    "Sustaining drives will be especially important."
                ),
                "Passing": (
                    "Protect the quarterback and avoid forcing throws "
                    "against a difficult pass defense."
                ),
                "Rushing": (
                    "Be selective with rushing attempts. Avoid predictable "
                    "runs and use other ways to create offensive balance."
                ),
                "Explosive Plays": (
                    "Find ways to create chunk plays without forcing "
                    "low-percentage opportunities."
                ),
                "Third Down": (
                    "Improve third-down execution by creating more "
                    "manageable situations on early downs."
                ),
                "Red Zone": (
                    "Prioritize execution near the goal line and find "
                    "ways to turn red-zone trips into touchdowns."
                ),
            }
        else:
            recommendations = {
                "Overall Efficiency": (
                    "Limit the opponent's offensive rhythm and force "
                    "longer, more difficult drives."
                ),
                "Passing": (
                    "Give the secondary help and find ways to disrupt "
                    "the opposing passing attack."
                ),
                "Rushing": (
                    "Improve gap discipline and win more battles at "
                    "the line of scrimmage."
                ),
                "Explosive Plays": (
                    "Emphasize tackling and assignment discipline to "
                    "prevent the opponent from breaking big plays."
                ),
                "Third Down": (
                    "Find ways to create more third-and-long situations "
                    "and get off the field."
                ),
                "Red Zone": (
                    "Improve execution near the goal line and make the "
                    "opponent settle for field goals."
                ),
            }

        recommendation = recommendations.get(category)

        if recommendation:
            keys.append(recommendation)

    # Remove duplicate recommendations while preserving their order.
    return list(dict.fromkeys(keys))[:5]

def build_game_preview_key(advantages, concerns):
    strategy_library = {
        "Overall Efficiency": {
            "OFFENSE": {
                "advantage": [
                    ("Stay ahead of the chains",
                     "Use efficient early-down offense to stay out of "
                     "obvious passing situations and sustain drives."),
                    ("Keep the offense balanced",
                     "Mix the run and pass to keep the defense guessing "
                     "and consistently move the chains."),
                    ("Make every possession count",
                     "Lean into the offense's efficiency and force the "
                     "opponent to defend sustained drives."),
                ],
                "concern": [
                    ("Simplify the offensive approach",
                     "Prioritize manageable plays, avoid negative "
                     "yardage, and prevent the defense from dictating "
                     "the situation."),
                    ("Win on early downs",
                     "Create more manageable second and third downs "
                     "instead of putting the offense behind schedule."),
                    ("Protect every possession",
                     "Limit risky plays and focus on efficient, "
                     "high-percentage decisions."),
                ],
            },
            "DEFENSE": {
                "advantage": [
                    ("Make every yard difficult",
                     "Use the defensive efficiency advantage to force "
                     "longer drives and make the offense earn everything."),
                    ("Disrupt their offensive rhythm",
                     "Keep the opponent from settling into a rhythm and "
                     "force them into difficult situations."),
                    ("Win the down-to-down battle",
                     "Stay disciplined and make it difficult for the "
                     "opponent to string together successful plays."),
                ],
                "concern": [
                    ("Make them earn every drive",
                     "Focus on limiting easy completions and runs. "
                     "Force the opponent to execute consistently."),
                    ("Improve defensive consistency",
                     "Eliminate assignment mistakes and prevent "
                     "individual plays from turning into sustained drives."),
                    ("Create tougher situations",
                     "Focus on winning early downs and forcing the "
                     "opponent into longer-yardage situations."),
                ],
            },
        },
        "Passing": {
            "OFFENSE": {
                "advantage": [
                    ("Attack the secondary",
                     "Take advantage of the passing matchup by "
                     "challenging coverage and creating opportunities "
                     "through the air."),
                    ("Spread the defense out",
                     "Use the passing game to stretch the defense "
                     "horizontally and create favorable matchups."),
                    ("Build the game plan around the pass",
                     "Lean into the passing advantage to move the "
                     "chains and open opportunities elsewhere."),
                ],
                "concern": [
                    ("Use a quicker passing approach",
                     "Get the ball out quickly, use high-percentage "
                     "throws, and limit opportunities for the defense "
                     "to disrupt the quarterback."),
                    ("Protect the quarterback",
                     "Emphasize protection and avoid predictable "
                     "passing situations against a difficult defense."),
                    ("Create easier passing opportunities",
                     "Use shorter throws and varied formations to "
                     "help the passing game find its rhythm."),
                ],
            },
            "DEFENSE": {
                "advantage": [
                    ("Make the quarterback uncomfortable",
                     "Use the passing defensive advantage to disrupt "
                     "timing and make completions more difficult."),
                    ("Challenge their passing attack",
                     "Make the opponent prove it can consistently "
                     "complete passes against this secondary."),
                    ("Take away easy throws",
                     "Disrupt the passing rhythm and force the "
                     "quarterback to hold the ball longer."),
                ],
                "concern": [
                    ("Disrupt the passing rhythm",
                     "Mix coverages and pressure looks to make "
                     "the quarterback work for every completion."),
                    ("Limit opportunities downfield",
                     "Prioritize coverage discipline and prevent "
                     "the passing game from producing easy gains."),
                    ("Make protection work",
                     "Find ways to create pressure without leaving "
                     "the secondary exposed."),
                ],
            },
        },
        "Rushing": {
            "OFFENSE": {
                "advantage": [
                    ("Attack the defensive front",
                     "Make the ground game a central part of the plan "
                     "and consistently challenge the opponent's "
                     "run defense."),
                    ("Set the physical tone",
                     "Establish the run early and make the defense "
                     "prove it can handle a physical rushing attack."),
                    ("Use the run to control the game",
                     "Lean on the rushing advantage to sustain drives, "
                     "control possession, and dictate the tempo."),
                ],
                "concern": [
                    ("Be selective with rushing attempts",
                     "Vary the run concepts and avoid repeatedly "
                     "challenging the defense in predictable situations."),
                    ("Create better running opportunities",
                     "Use formations and offensive balance to prevent "
                     "the defense from loading the box."),
                    ("Make the run game more efficient",
                     "Focus on execution and favorable rushing "
                     "situations instead of forcing carries."),
                ],
            },
            "DEFENSE": {
                "advantage": [
                    ("Win the line of scrimmage",
                     "Use the defensive front to limit rushing lanes "
                     "and make the opponent earn yards through the air."),
                    ("Make them one-dimensional",
                     "Take away the ground game and force the "
                     "opponent to rely more heavily on passing."),
                    ("Control the rushing lanes",
                     "Maintain gap discipline and prevent the "
                     "opponent from establishing a consistent run game."),
                ],
                "concern": [
                    ("Fix the run defense",
                     "Prioritize gap integrity and tackling to prevent "
                     "the opponent from controlling the ground game."),
                    ("Stop the run early",
                     "Focus on winning first down and avoiding the "
                     "long rushing gains that keep drives alive."),
                    ("Make rushing yards difficult",
                     "Improve defensive discipline and close running "
                     "lanes before the opponent reaches the second level."),
                ],
            },
        },
        "Explosive Plays": {
            "OFFENSE": {
                "advantage": [
                    ("Create explosive opportunities",
                     "Look for favorable opportunities to generate "
                     "chunk plays and put immediate pressure on the defense."),
                    ("Attack space downfield",
                     "Use the offense's ability to create big plays "
                     "to stretch the defense and change field position."),
                    ("Take calculated shots",
                     "Mix explosive opportunities into the game plan "
                     "without sacrificing offensive efficiency."),
                ],
                "concern": [
                    ("Create chunk plays more efficiently",
                     "Use varied formations and play designs to create "
                     "space without forcing low-percentage attempts."),
                    ("Find opportunities after the catch",
                     "Use shorter completions and create opportunities "
                     "for receivers to gain additional yardage."),
                    ("Avoid forcing explosive plays",
                     "Stay patient, take available yards, and let "
                     "bigger opportunities develop naturally."),
                ],
            },
            "DEFENSE": {
                "advantage": [
                    ("Keep everything in front",
                     "Use the defensive advantage to prevent big plays "
                     "and force the opponent to sustain long drives."),
                    ("Eliminate explosive opportunities",
                     "Stay disciplined in coverage and prevent "
                     "individual plays from changing the game."),
                    ("Force them to be patient",
                     "Take away the big play and make the opponent "
                     "execute repeatedly to move the ball."),
                ],
                "concern": [
                    ("Eliminate defensive breakdowns",
                     "Prioritize assignment discipline and communication "
                     "to prevent explosive gains."),
                    ("Protect against the big play",
                     "Keep appropriate coverage help over the top "
                     "and avoid unnecessary risks."),
                    ("Improve tackling in space",
                     "Limit yards after contact and prevent ordinary "
                     "plays from becoming major gains."),
                ],
            },
        },
        "Third Down": {
            "OFFENSE": {
                "advantage": [
                    ("Own third down",
                     "Capitalize on the favorable matchup by keeping "
                     "drives alive and extending possessions."),
                    ("Stay on the field",
                     "Use the third-down advantage to sustain drives "
                     "and keep the opponent's offense on the sideline."),
                    ("Finish offensive possessions",
                     "Make third-down execution a priority and "
                     "consistently turn opportunities into first downs."),
                ],
                "concern": [
                    ("Create manageable third downs",
                     "Improve early-down execution so the offense "
                     "is not consistently facing long-yardage situations."),
                    ("Simplify third-down decisions",
                     "Use favorable formations and high-percentage "
                     "plays to improve conversion opportunities."),
                    ("Avoid obvious passing situations",
                     "Establish more productive early downs and "
                     "keep the offense's playbook open."),
                ],
            },
            "DEFENSE": {
                "advantage": [
                    ("Get off the field",
                     "Use the third-down advantage to end possessions "
                     "and give the offense more opportunities."),
                    ("Force difficult conversions",
                     "Create longer third-down situations and make "
                     "the opponent earn every first down."),
                    ("Win the critical downs",
                     "Stay aggressive and disciplined when the "
                     "opponent needs to extend a drive."),
                ],
                "concern": [
                    ("Improve third-down execution",
                     "Focus on coverage discipline and pressure "
                     "to create more opportunities to get off the field."),
                    ("Win first and second down",
                     "Create longer third-down situations instead "
                     "of allowing the opponent to convert comfortably."),
                    ("Finish defensive possessions",
                     "Improve situational execution and prevent "
                     "the opponent from extending drives."),
                ],
            },
        },
        "Red Zone": {
            "OFFENSE": {
                "advantage": [
                    ("Finish drives with touchdowns",
                     "Capitalize on the red-zone matchup and turn "
                     "scoring opportunities into touchdowns."),
                    ("Be aggressive near the goal line",
                     "Use the team's red-zone strength to put "
                     "pressure on the defense inside the 20."),
                    ("Turn possessions into points",
                     "Make red-zone execution a priority and "
                     "maximize every scoring opportunity."),
                ],
                "concern": [
                    ("Improve red-zone execution",
                     "Emphasize situational play-calling and "
                     "execution when the field becomes compressed."),
                    ("Finish more scoring drives",
                     "Find ways to create favorable matchups "
                     "near the goal line instead of settling for field goals."),
                    ("Simplify near the goal line",
                     "Prioritize reliable plays and avoid mistakes "
                     "that waste scoring opportunities."),
                ],
            },
            "DEFENSE": {
                "advantage": [
                    ("Force field goals",
                     "Use the red-zone defensive advantage to "
                     "prevent touchdowns and limit scoring damage."),
                    ("Tighten up near the goal line",
                     "Make the opponent work for every yard "
                     "and protect the most important part of the field."),
                    ("Win the red-zone battle",
                     "Stay disciplined inside the 20 and turn "
                     "opponent scoring opportunities into field goals."),
                ],
                "concern": [
                    ("Strengthen goal-line defense",
                     "Improve assignment discipline and tackling "
                     "when the opponent gets inside scoring range."),
                    ("Make red-zone stops",
                     "Focus on limiting easy scoring opportunities "
                     "and forcing the opponent into difficult plays."),
                    ("Prevent touchdowns",
                     "Emphasize situational defense and make "
                     "the opponent settle for field goals."),
                ],
            },
        },
    }

    candidates = (
        [(item, "advantage") for item in advantages]
        + [(item, "concern") for item in concerns]
    )

    candidates = [
        (item, result_type)
        for item, result_type in candidates
        if item.get("category") in strategy_library
        and item.get("side") in ("OFFENSE", "DEFENSE")
    ]

    if not candidates:
        return {
            "title": "Win the fundamentals",
            "category": "Game Management",
            "side": "BOTH",
            "explanation": (
                "Protect the football, execute in key situations, "
                "and avoid giving the opponent easy opportunities."
            ),
            "stat_line": None,
        }

    item, result_type = max(
        candidates,
        key=lambda candidate: candidate[0].get("strength", 0),
    )

    category = item["category"]
    side = item["side"]

    variations = strategy_library[category][side][result_type]

    # Use the matchup values to select between strategic variations.
    team_value = item.get("team_value", 0) or 0
    opponent_value = item.get("opponent_value", 0) or 0

    variant_index = (
        int(abs(team_value * 1000) + abs(opponent_value * 1000))
        % len(variations)
    )

    title, explanation = variations[variant_index]

    if item.get("unit") == "EPA/play":
        team_display = f"{team_value:+.3f}"
        opponent_display = f"{opponent_value:+.3f}"
        unit_label = "EPA/play"
    else:
        team_display = f"{team_value:.1%}"
        opponent_display = f"{opponent_value:.1%}"
        unit_label = ""

    if side == "OFFENSE":
        stat_line = (
            f"Your offense: {team_display} {unit_label} "
            f"| Opponent defense allows: "
            f"{opponent_display} {unit_label}"
        )
    else:
        stat_line = (
            f"Your defense allows: {team_display} {unit_label} "
            f"| Opponent offense: "
            f"{opponent_display} {unit_label}"
        )

    return {
        "title": title,
        "category": category,
        "side": side,
        "explanation": explanation,
        "stat_line": stat_line,
    }

def render_up_next(code, info):
    game = get_next_game(code)

    section("UP NEXT")

    if game is None:
        st.info("No upcoming game is currently scheduled.")
        return

    opponent = (
        game["away"] if game["home"] == code else game["home"]
    )

    opponent_info = TEAMS[opponent]

    team_row = get_team_row(code)
    opponent_row = get_team_row(opponent)

    team_stats = get_team_row(code, team_metrics)
    opponent_stats = get_team_row(opponent, team_metrics)

    if any(x is None for x in [
        team_row, opponent_row, team_stats, opponent_stats
    ]):
        st.warning("Unable to load matchup ratings.")
        return

    team_rating = float(team_row["overall_rating"])
    opponent_rating = float(opponent_row["overall_rating"])

    is_home = game["home"] == code

    win_probability = calculate_win_probability(
        team_rating,
        opponent_rating,
        is_home,
    )

    if win_probability >= 0.50:
        headline = "CONFIDENCE METER"
        outlook = "FAVORITE"
    else:
        headline = "UPSET ALERT"
        outlook = "UNDERDOG"

    game_date = datetime.strptime(
        game["date"], "%Y-%m-%d"
    ).strftime("%A, %B %d, %Y")

    location = "HOME" if is_home else "AWAY"

    st.markdown(
        f'<div style="background:linear-gradient(135deg,'
        f'{info["color"]}33,#111827);'
        f'border:1px solid {info["color"]};'
        f'border-radius:16px;padding:24px;margin-bottom:18px;'
        f'text-align:center">'

        f'<div style="font-size:12px;letter-spacing:3px;'
        f'font-weight:800;opacity:.8;margin-bottom:20px">'
        f'{html.escape(headline)}</div>'

        f'<div style="display:flex;align-items:center;'
        f'justify-content:center;gap:30px;flex-wrap:wrap">'

        f'<div style="display:flex;flex-direction:column;'
        f'align-items:center;gap:8px">'
        f'{logo(code, 100)}'
        f'<div style="font-size:17px;font-weight:800">'
        f'{html.escape(info["name"])}</div>'
        f'</div>'

        f'<div style="font-size:20px;font-weight:900;'
        f'opacity:.65">VS</div>'

        f'<div style="display:flex;flex-direction:column;'
        f'align-items:center;gap:8px">'
        f'{logo(opponent, 100)}'
        f'<div style="font-size:17px;font-weight:800">'
        f'{html.escape(opponent_info["name"])}</div>'
        f'</div>'

        f'</div>'

        f'<div style="font-size:13px;opacity:.8;margin-top:20px">'
        f'{game_date} &nbsp; | &nbsp; {game["kickoff"]} '
        f'&nbsp; | &nbsp; {location}</div>'

        f'<div style="margin-top:20px;font-weight:800;'
        f'color:{info["secondary"]}">{outlook}</div>'

        f'<div style="font-size:42px;font-weight:900;'
        f'margin-top:5px">{win_probability:.0%}</div>'

        f'<div style="font-size:11px;letter-spacing:2px;'
        f'opacity:.7">ESTIMATED WIN PROBABILITY</div>'

        f'</div>',
        unsafe_allow_html=True,
    )

    st.caption(
        f"Your team's overall rating: {team_rating:.1f} "
        f"| Opponent rating: {opponent_rating:.1f}"
    )
    advantages, concerns = build_matchup_analysis(
        team_stats,
        opponent_stats,
    )

    keys_to_victory = build_keys_to_victory(
        advantages,
        concerns,
    )

    advantage_col, concern_col = st.columns(2)


    def render_comparison_card(item, positive):
        side = item["side"]

        if side == "OFFENSE":
            team_side = "OFFENSE"
            opponent_side = "DEFENSE"
        else:
            team_side = "DEFENSE"
            opponent_side = "OFFENSE"

        team_value = item["team_value"]
        opponent_value = item["opponent_value"]

        if item["unit"] == "EPA/play":
            team_display = f"{team_value:+.3f}"
            opponent_display = f"{opponent_value:+.3f}"
        else:
            team_display = f"{team_value:.1%}"
            opponent_display = f"{opponent_value:.1%}"

        bar_width = min(100, item["strength"] * 50)
        bar_color = "#27AE60" if positive else "#E05252"
        edge_label = "ADVANTAGE" if positive else "DISADVANTAGE"

        card_html = f"""
        <div style="
            background:#151F2D;
            border:1px solid #344155;
            border-radius:12px;
            padding:13px;
            margin-bottom:10px;
        ">
            <div style="
                font-size:14px;
                font-weight:800;
                margin-bottom:10px;
            ">
                {html.escape(item["category"])}
            </div>

            <div style="
                display:flex;
                justify-content:space-between;
                gap:8px;
                font-size:11px;
                opacity:.75;
                margin-bottom:5px;
            ">
                <span>
                    {html.escape(info["name"])} {team_side}
                </span>
                <span>
                    {html.escape(opponent_info["name"])} {opponent_side}
                </span>
            </div>

            <div style="
                display:flex;
                justify-content:space-between;
                font-size:17px;
                font-weight:800;
                margin-bottom:12px;
            ">
                <span>{team_display}</span>
                <span>{opponent_display}</span>
            </div>

            <div style="
                font-size:10px;
                font-weight:800;
                letter-spacing:1px;
                color:{bar_color};
                margin-bottom:5px;
            ">
                {edge_label}
            </div>

            <div style="
                height:7px;
                background:#303B4B;
                border-radius:10px;
                overflow:hidden;
            ">
                <div style="
                    height:100%;
                    width:{bar_width:.1f}%;
                    background:{bar_color};
                    border-radius:10px;
                "></div>
            </div>
        </div>
        """

        st.html(textwrap.dedent(card_html)
        )

    with advantage_col:
        st.markdown("### ADVANTAGES")

        if advantages:
            for item in advantages[:4]:
                render_comparison_card(item, True)
        else:
            st.caption(
                "No significant statistical advantages identified."
            )

    with concern_col:
        st.markdown("### AREAS OF CONCERN")

        if concerns:
            for item in concerns[:4]:
                render_comparison_card(item, False)
        else:
            st.caption(
                "No significant statistical concerns identified."
            )
    st.markdown("### KEYS TO VICTORY")

    if keys_to_victory:
        for index, key in enumerate(keys_to_victory, start=1):
            st.markdown(
                f"""
                <div style="
                    display:flex;
                    align-items:flex-start;
                    gap:12px;
                    background:#151F2D;
                    border:1px solid #344155;
                    border-radius:12px;
                    padding:14px;
                    margin-bottom:10px;
                ">
                    <div style="
                        color:{info['secondary']};
                        font-size:20px;
                        font-weight:900;
                    ">
                        {index:02d}
                    </div>
                    <div style="font-size:14px;line-height:1.5">
                        {html.escape(key)}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.caption(
            "No specific keys to victory identified for this matchup."
        )

def render_profile():
    code = st.session_state.selected_team

    if code not in TEAMS:
        st.warning("Choose a team first.")
        go("TEAMS")
        return

    row = get_team_row(code)
    dna_row = get_team_row(code, team_metrics)

    if row is None:
        st.error(f"No ratings found for {code} in the CSV.")
        return

    if dna_row is None:
        st.error(f"No Team DNA metrics found for {code}.")
        return

    info = TEAMS[code]

    if st.session_state.play_entrance:
        effects = {
            "claws": ("THE HUNT IS ON.", "claws"),
            "fire": ("BRING THE HEAT.", "fx fx-fire"),
            "lightning": ("STRIKE FIRST.", "fx fx-lightning"),
            "storm": ("WEATHER THE STORM.", "fx fx-storm"),
            "wave": ("MAKE YOUR OWN WAVE.", "fx fx-wave"),
            "speed": ("TOO FAST TO CATCH.", "fx fx-speed"),
            "spotlight": ("THIS IS OUR STAGE.", "fx fx-spotlight"),
        }

        tagline, effect_class = effects[info["effect"]]

        claws = (
            '<div class="claw c1"></div><div class="claw c2"></div><div class="claw c3"></div>'
            if info["effect"] == "claws" else ""
        )

        st.markdown(
            f'<div class="cinematic {effect_class}" style="--team:{info["color"]};--team2:{info["secondary"]}">'
            f'{claws}<div class="intro-content"><div class="intro-kicker">NFL RATINGS / TEAM INTRODUCTION</div>'
            f'<img class="intro-logo" src="{info["logo"]}" alt="{html.escape(info["name"])}">'
            f'<div class="intro-team">{html.escape(info["name"])}</div>'
            f'<div class="intro-tag">{tagline}</div></div></div>',
            unsafe_allow_html=True,
        )

        st.session_state.play_entrance = False

    # --------------------------------------------------------
    # TEAM HEADER
    # --------------------------------------------------------

    rank = int(row["rank"])
    overall = float(row["overall_rating"])

    st.markdown(
        f'<div class="profile-hero" style="--team:{info["color"]}">'
        f'<div class="micro">NFL RATINGS / TEAM PROFILE / {code} / {info["conf"]} {info["div"]}</div>'
        f'<div style="display:flex;align-items:center;justify-content:space-between;gap:25px;flex-wrap:wrap">'
        f'<div style="flex:1;min-width:240px"><div class="profile-name">{html.escape(info["name"])}</div>'
        f'<div class="micro" style="margin-top:18px">LEAGUE RANK #{rank:02d}</div>'
        f'<div class="big-rating">{overall:.1f}</div><div class="micro">OVERALL RATING</div></div>'
        f'<div style="text-align:center">{logo(code,220)}</div></div></div>',
        unsafe_allow_html=True,
    )

    record = get_records()[code]

    st.markdown(
        f'<div class="micro" style="margin:15px 0">'
        f'CURRENT SEASON RECORD: '
        f'<span style="color:#E5D4AD;font-size:22px">'
        f'{record["W"]}-{record["L"]}-{record["T"]}'
        f'</span> &nbsp; / &nbsp; '
        f'WIN PERCENTAGE: {record["PCT"]:.3f} '
        f'&nbsp; / &nbsp; POINT DIFFERENTIAL: {record["DIFF"]:+d}'
        f'</div>',
        unsafe_allow_html=True,
    )

    values = [(label, float(row[col])) for label, col, _ in CATEGORIES]
    strongest = max(values, key=lambda item: item[1])
    weakest = min(values, key=lambda item: item[1])

    cols = st.columns(3)

    with cols[0]:
        metric("STRONGEST CATEGORY", strongest[0])

    with cols[1]:
        metric("WEAKEST CATEGORY", weakest[0])

    with cols[2]:
        metric("OVERALL RATING", f"{overall:.1f}")


    # --------------------------------------------------------
    # ATTRIBUTE BREAKDOWN
    # --------------------------------------------------------

    section("ATTRIBUTE BREAKDOWN")

    left, right = st.columns([3, 2])

    with left:
        for label, col, short in CATEGORIES:
            rating_bar(label, float(row[col]), info["color"])

    with right:
        st.markdown(
            '<div class="panel"><div class="micro">TEAM IDENTITY</div>'
            f'<b>{info["conf"]} {info["div"]}</b><br>'
            f'<b>League position:</b> #{rank} of {len(rankings)}<br>'
            f'<b>Overall rating:</b> {overall:.2f}<br>'
            f'<b>Above/below league average:</b> '
            f'{overall - rankings["overall_rating"].mean():+.2f}</div>',
            unsafe_allow_html=True,
        )

    # ========================================================
    # TEAM DNA
    # ========================================================

    section("TEAM DNA")

    # --------------------------------------------------------
    # OFFENSIVE IDENTITY
    # --------------------------------------------------------

    st.markdown("### OFFENSIVE IDENTITY")

    render_dna_heatmap(
        "PASSING PERFORMANCE — EPA PER PLAY",
        [
            ("Short Left", "dna_off_pass_epa_short_left",
             "dna_off_pass_plays_short_left"),
            ("Short Middle", "dna_off_pass_epa_short_middle",
             "dna_off_pass_plays_short_middle"),
            ("Short Right", "dna_off_pass_epa_short_right",
             "dna_off_pass_plays_short_right"),
            ("Deep Left", "dna_off_pass_epa_deep_left",
             "dna_off_pass_plays_deep_left"),
            ("Deep Middle", "dna_off_pass_epa_deep_middle",
             "dna_off_pass_plays_deep_middle"),
            ("Deep Right", "dna_off_pass_epa_deep_right",
             "dna_off_pass_plays_deep_right"),
        ],
        dna_row,
        team_metrics,
    )

    render_dna_heatmap(
        "RUSHING PERFORMANCE — EPA PER PLAY",
        [
            ("Left", "dna_off_rush_epa_left",
             "dna_off_rush_plays_left"),
            ("Middle", "dna_off_rush_epa_middle",
             "dna_off_rush_plays_middle"),
            ("Right", "dna_off_rush_epa_right",
             "dna_off_rush_plays_right"),
        ],
        dna_row,
        team_metrics,
    )

    # --------------------------------------------------------
    # DEFENSIVE IDENTITY
    # --------------------------------------------------------

    st.markdown("### DEFENSIVE IDENTITY")

    render_dna_heatmap(
        "PASSING DEFENSE — EPA ALLOWED PER PLAY",
        [
            ("Short Left", "dna_def_pass_epa_allowed_short_left",
             "dna_def_pass_plays_short_left"),
            ("Short Middle", "dna_def_pass_epa_allowed_short_middle",
             "dna_def_pass_plays_short_middle"),
            ("Short Right", "dna_def_pass_epa_allowed_short_right",
             "dna_def_pass_plays_short_right"),
            ("Deep Left", "dna_def_pass_epa_allowed_deep_left",
             "dna_def_pass_plays_deep_left"),
            ("Deep Middle", "dna_def_pass_epa_allowed_deep_middle",
             "dna_def_pass_plays_deep_middle"),
            ("Deep Right", "dna_def_pass_epa_allowed_deep_right",
             "dna_def_pass_plays_deep_right"),
        ],
        dna_row,
        team_metrics,
        defensive=True,
    )

    render_dna_heatmap(
        "RUSHING DEFENSE — EPA ALLOWED PER PLAY",
        [
            ("Left", "dna_def_rush_epa_allowed_left",
             "dna_def_rush_plays_left"),
            ("Middle", "dna_def_rush_epa_allowed_middle",
             "dna_def_rush_plays_middle"),
            ("Right", "dna_def_rush_epa_allowed_right",
             "dna_def_rush_plays_right"),
        ],
        dna_row,
        team_metrics,
        defensive=True,
    )

    # --------------------------------------------------------
    # SITUATIONAL PERFORMANCE
    # --------------------------------------------------------

    section("SITUATIONAL PERFORMANCE")

    situation_groups = [
        {
            "title": "SITUATIONAL OFFENSE",
            "stats": [
                ("Third Down", "dna_third_down_conversion_rate",
                 "dna_third_down_attempts"),
                ("Fourth Down", "dna_fourth_down_conversion_rate",
                 "dna_fourth_down_attempts"),
                ("Red Zone TD Rate", "dna_red_zone_td_rate",
                 "dna_red_zone_trips"),
                ("Red Zone Scoring", "dna_red_zone_scoring_rate",
                 "dna_red_zone_trips"),
            ],
        },
        {
            "title": "SITUATIONAL DEFENSE",
            "stats": [
                ("Third Down Allowed", "dna_third_down_conversion_rate_allowed",
                 "dna_third_down_attempts_allowed"),
                ("Fourth Down Allowed", "dna_fourth_down_conversion_rate_allowed",
                 "dna_fourth_down_attempts_allowed"),
                ("Red Zone TD Rate Allowed", "dna_red_zone_td_rate_allowed",
                 "dna_red_zone_trips_allowed"),
                ("Red Zone Scoring Allowed", "dna_red_zone_scoring_rate_allowed",
                 "dna_red_zone_trips_allowed"),
            ],
        },
    ]

    for group in situation_groups:
        st.markdown(f"### {group['title']}")

        cols = st.columns(4)

        for index, (label, rate_col, attempts_col) in enumerate(group["stats"]):
            rate = pd.to_numeric(
                pd.Series([dna_row[rate_col]]), errors="coerce"
            ).iloc[0]

            attempts = pd.to_numeric(
                pd.Series([dna_row[attempts_col]]), errors="coerce"
            ).iloc[0]

            with cols[index]:
                st.metric(
                    label,
                    f"{rate:.1%}" if pd.notna(rate) else "N/A",
                )

                st.caption(
                    f"{int(attempts)} attempts/trips"
                    if pd.notna(attempts) else "Sample unavailable"
                )

    # --------------------------------------------------------
    # STATISTICAL STRENGTHS AND WEAKNESSES
    # --------------------------------------------------------

    section("STATISTICAL STRENGTHS & WEAKNESSES")

    strengths, weaknesses = get_dna_strengths_weaknesses(
        dna_row, team_metrics
    )

    def format_dna_value(item):
        if "rate" in item["label"].lower() or "success" in item["label"].lower():
            return f"{item['value']:.1%}"

        return f"{item['value']:.2f}"

    left, right = st.columns(2)

    with left:
        st.markdown("### TOP STRENGTHS")

        for item in strengths:
            st.markdown(
                f"**{item['label']}**  \n"
                f"{format_dna_value(item)} · "
                f"{item['percentile']:.0f}th percentile"
            )

    with right:
        st.markdown("### AREAS TO IMPROVE")

        for item in weaknesses:
            st.markdown(
                f"**{item['label']}**  \n"
                f"{format_dna_value(item)} · "
                f"{item['percentile']:.0f}th percentile"
            )

    render_up_next(code, info)

    # --------------------------------------------------------
    # MOST SIMILAR TEAMS
    # --------------------------------------------------------



    section("MOST SIMILAR")

    similar_teams = get_most_similar_teams(
        code, team_metrics, limit=3
    )

    if similar_teams.empty:
        st.info("Similar team profiles are not available.")

    else:
        st.caption(
            "These teams have the closest statistical profiles "
            "across offensive tendencies, defensive tendencies, "
            "efficiency, and situational performance."
        )

        for _, similar in similar_teams.iterrows():
            near = get_team_row(similar["team"])

            if near is not None:
                rank_row(
                    near,
                    f"similar_{code}_{similar['team']}"
                )

    if st.button("← BACK TO ALL TEAMS", key="profile_back"):
        go("TEAMS")


# ============================================================
# POWER RANKINGS
# ============================================================


def render_rankings():
    hero("THE LEAGUE TABLE", "POWER", "RANKINGS.", "32 TEAMS. ONE ORDER. BUILT BY THE RATINGS ENGINE.")

    if rankings is None:
        st.error("Rankings CSV could not be loaded.")
        return

    sort_options = {
        "Overall Rating": "overall_rating",
        "Offense": "offensive_rating",
        "Defense": "defensive_rating",
        "Special Teams": "special_teams_rating",
        "Discipline": "discipline_rating",
        "On-Field": "on_field_rating",
    }

    f1, f2, f3, f4 = st.columns([2, 1, 1, 1.5])

    with f1:
        search = st.text_input(
            "SEARCH TEAM",
            placeholder="Type a team name or abbreviation..."
        )

    with f2:
        conference = st.selectbox(
            "CONFERENCE", ["ALL", "AFC", "NFC"]
        )

    with f3:
        division = st.selectbox(
            "DIVISION", ["ALL", "East", "North", "South", "West"]
        )

    with f4:
        sort_by = st.selectbox(
            "SORT RANKINGS BY",
            list(sort_options.keys())
        )

    data = rankings.copy()

    data["conference"] = data["team"].map(
        lambda code: TEAMS.get(code, {}).get("conf", "")
    )
    data["division"] = data["team"].map(
        lambda code: TEAMS.get(code, {}).get("div", "")
    )
    data["team_name"] = data["team"].map(
        lambda code: TEAMS.get(code, {}).get("name", code)
    )

    # Sort the full league before applying filters so ranks
    # always represent each team's position across all 32 teams.
    sort_column = sort_options[sort_by]

    data = data.sort_values(
        sort_column,
        ascending=False,
        na_position="last"
    ).reset_index(drop=True)

    data["display_rank"] = range(1, len(data) + 1)

    if conference != "ALL":
        data = data[data["conference"] == conference]

    if division != "ALL":
        data = data[data["division"] == division]

    if search.strip():
        needle = search.strip().lower()
        data = data[
            data.apply(
                lambda row: needle in str(row["team"]).lower()
                or needle in str(row["team_name"]).lower(),
                axis=1,
            )
        ]

    section(f"RANKED TEAMS / {len(data)} RESULTS")

    if data.empty:
        st.info("No teams match those filters.")
        return

    for _, row in data.iterrows():
        rating = float(row[sort_column])

        tier = (
            "ELITE" if rating >= 65 else
            "CONTENDER" if rating >= 55 else
            "MIDDLE PACK" if rating >= 45 else "REBUILD"
        )

        code = str(row["team"])
        info = TEAMS.get(code)

        if not info:
            continue

        st.markdown(
            f'<div class="rank-row" style="border-left-color:{info["color"]}">'
            f'<div class="rank-num">#{int(row["display_rank"]):02d}</div>{logo(code,56)}'
            f'<div class="rank-name">{html.escape(info["name"].upper())}'
            f'<div class="micro">{info["conf"]} {info["div"]} / '
            f'<span class="tier">{tier}</span></div></div>'
            f'<div class="rank-score">{rating:.1f}</div></div>',
            unsafe_allow_html=True,
        )

        if st.button(f"OPEN {code} PROFILE →", key=f"ranking_open_{code}"):
            go("PROFILE", code, True)


# ============================================================
# WAR ROOM
# ============================================================

def render_war_room():
    hero("THE MATCHUP CENTER", "THE", "WAR ROOM.", "TWO TEAMS. FIVE CATEGORIES. ONE HEAD-TO-HEAD.")
    if rankings is None:
        st.error("Rankings CSV could not be loaded.")
        return

    codes = list(TEAMS.keys())
    safe_one = st.session_state.war_one if st.session_state.war_one in codes else "SF"
    safe_two = st.session_state.war_two if st.session_state.war_two in codes else "KC"
    a, b = st.columns(2)
    with a:
        one = st.selectbox(
            "TEAM ONE", codes, index=codes.index(safe_one),
            format_func=lambda code: TEAMS[code]["name"], key="war_pick_one"
        )
    with b:
        two = st.selectbox(
            "TEAM TWO", codes, index=codes.index(safe_two),
            format_func=lambda code: TEAMS[code]["name"], key="war_pick_two"
        )
    st.session_state.war_one, st.session_state.war_two = one, two

    if one == two:
        st.warning("Choose two different teams.")
        return

    r1, r2 = get_team_row(one), get_team_row(two)
    if r1 is None or r2 is None:
        st.error("One of the selected teams is missing from the ratings file.")
        return
    i1, i2 = TEAMS[one], TEAMS[two]

    c1, cv, c2 = st.columns([2, 1, 2])
    with c1:
        st.markdown(
            f'<div class="panel" style="text-align:center;border-top:5px solid {i1["color"]}">'
            f'{logo(one,130)}<div class="profile-name" style="font-size:44px">{i1["name"]}</div>'
            f'<div class="big-rating">{float(r1["overall_rating"]):.1f}</div>'
            f'<div class="micro">RANK #{int(r1["rank"])}</div></div>',
            unsafe_allow_html=True,
        )
    with cv:
        st.markdown(
            '<div style="font-family:Barlow Condensed;font-size:70px;font-weight:900;'
            'text-align:center;padding-top:70px;color:#B99A5A">VS</div>',
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f'<div class="panel" style="text-align:center;border-top:5px solid {i2["color"]}">'
            f'{logo(two,130)}<div class="profile-name" style="font-size:44px">{i2["name"]}</div>'
            f'<div class="big-rating">{float(r2["overall_rating"]):.1f}</div>'
            f'<div class="micro">RANK #{int(r2["rank"])}</div></div>',
            unsafe_allow_html=True,
        )

    section("CATEGORY SHOWDOWN")
    wins1 = wins2 = ties = 0
    chart_rows = []
    for label, col, _ in CATEGORIES:
        v1, v2 = float(r1[col]), float(r2[col])
        if v1 > v2:
            wins1 += 1
            edge = i1["name"]
        elif v2 > v1:
            wins2 += 1
            edge = i2["name"]
        else:
            ties += 1
            edge = "TIE"
        chart_rows.append({"Category": label, i1["name"]: v1, i2["name"]: v2})
        st.markdown(f"**{label}**")
        x, y, z = st.columns([2, 1, 2])
        with x:
            st.metric(i1["name"], f"{v1:.1f}", delta=f"{v1-v2:+.1f}")
        with y:
            st.markdown(
                '<div style="text-align:center;padding-top:24px;'
                'font-family:Barlow Condensed;font-size:30px;color:#B99A5A">VS</div>',
                unsafe_allow_html=True,
            )
        with z:
            st.metric(i2["name"], f"{v2:.1f}", delta=f"{v2-v1:+.1f}")
        st.caption(f"Category edge: {edge}")

    section("COMPARISON CHART")
    st.bar_chart(pd.DataFrame(chart_rows).set_index("Category"), height=330)

    section("THE FINAL VERDICT")
    v1, v2 = float(r1["overall_rating"]), float(r2["overall_rating"])
    winner = i1["name"] if v1 > v2 else i2["name"] if v2 > v1 else "Neither team"
    left, mid, right = st.columns(3)
    with left:
        metric(f"{one} CATEGORY WINS", wins1)
    with mid:
        metric("TIES", ties)
    with right:
        metric(f"{two} CATEGORY WINS", wins2)
    if winner != "Neither team":
        st.markdown(f"### {winner} has the stronger overall rating by {abs(v1-v2):.2f} points.")
    else:
        st.markdown("### The overall ratings are tied.")
    st.caption("This is a comparison of the model's ratings, not a game prediction or guaranteed outcome.")


# ============================================================
# HISTORY + MOVEMENT
# ============================================================

def render_history():
    hero("THE LONG GAME", "RATINGS", "HISTORY.", "TRACK REAL CHANGES AS NEW RATING FILES ARE RECORDED.")
    history = read_history()
    if not history:
        st.info("No history snapshots exist yet. A first snapshot is created automatically when a valid ratings CSV is loaded.")
        return

    st.markdown(f"**Recorded snapshots:** {len(history)}")
    st.caption("A snapshot is saved when the contents of the ratings CSV change. Historical data is never invented.")
    if len(history) < 2:
        st.warning("One snapshot is currently available. Update your ratings CSV after a later rating run to unlock movement charts.")
        snap = history[-1]
        st.caption(f"First snapshot: {snap.get('captured_at', snap.get('date', 'Unknown'))}")
        return

    first, latest = history[0], history[-1]
    old = pd.DataFrame(first.get("teams", []))
    new = pd.DataFrame(latest.get("teams", []))
    required = {"team", "rank", "overall_rating"}
    if not required.issubset(old.columns) or not required.issubset(new.columns):
        st.warning("A saved snapshot is missing team data.")
        return

    merged = old[["team", "rank", "overall_rating"]].merge(
        new[["team", "rank", "overall_rating"]],
        on="team", suffixes=("_start", "_latest")
    )
    merged["rank_change"] = merged["rank_start"] - merged["rank_latest"]
    merged["rating_change"] = merged["overall_rating_latest"] - merged["overall_rating_start"]
    merged["name"] = merged["team"].map(lambda code: TEAMS.get(code, {}).get("name", code))
    risers = merged.sort_values("rank_change", ascending=False).head(5)
    fallers = merged.sort_values("rank_change").head(5)

    a, b = st.columns(2)
    with a:
        section("BIGGEST RISERS")
        for _, row in risers.iterrows():
            st.markdown(f"**{row['name']}**  ·  {int(row['rank_change']):+d} places")
    with b:
        section("BIGGEST FALLERS")
        for _, row in fallers.iterrows():
            st.markdown(f"**{row['name']}**  ·  {int(row['rank_change']):+d} places")

    section("RATING CHANGE SINCE FIRST SNAPSHOT")
    changes = merged.sort_values("rating_change", ascending=False)
    st.dataframe(
        changes[[
            "name", "rank_start", "rank_latest", "rank_change",
            "overall_rating_start", "overall_rating_latest", "rating_change"
        ]].rename(columns={
            "name": "Team", "rank_start": "First rank", "rank_latest": "Latest rank",
            "rank_change": "Rank movement", "overall_rating_start": "First rating",
            "overall_rating_latest": "Latest rating", "rating_change": "Rating change",
        }),
        use_container_width=True,
        hide_index=True,
    )

    team_choices = sorted(TEAMS, key=lambda code: TEAMS[code]["name"])
    selected = st.selectbox(
        "TEAM HISTORY", team_choices,
        format_func=lambda code: TEAMS[code]["name"],
        key="history_team_select",
    )
    series = []
    for snap in history:
        frame = pd.DataFrame(snap.get("teams", []))
        if not {"team", "overall_rating", "rank"}.issubset(frame.columns):
            continue
        match = frame[frame["team"] == selected]
        if not match.empty:
            series.append({
                "Date": snap.get("date", snap.get("captured_at", "")),
                "Overall rating": float(match.iloc[0]["overall_rating"]),
                "Rank": int(match.iloc[0]["rank"]),
            })
    if series:
        chart_data = pd.DataFrame(series).set_index("Date")
        st.line_chart(chart_data[["Overall rating"]], height=260)
        st.line_chart(chart_data[["Rank"]], height=220)


# ============================================================
# WEEKLY REPORT / LEAGUE SPOTLIGHT
# ============================================================

def render_report():
    hero("THE NFL RATINGS DESK", "THE WEEKLY", "REPORT.", "A BROADCAST-STYLE READOUT OF THE CURRENT RATINGS LANDSCAPE.")
    if rankings is None:
        st.error("Rankings CSV could not be loaded.")
        return

    data = rankings.sort_values("rank")
    awards = [
        ("CURRENT #1", data.iloc[0], "overall_rating"),
        ("OFFENSIVE STANDARD", rankings.loc[rankings["offensive_rating"].idxmax()], "offensive_rating"),
        ("DEFENSIVE STANDARD", rankings.loc[rankings["defensive_rating"].idxmax()], "defensive_rating"),
        ("SPECIAL TEAMS LEADER", rankings.loc[rankings["special_teams_rating"].idxmax()], "special_teams_rating"),
        ("DISCIPLINE LEADER", rankings.loc[rankings["discipline_rating"].idxmax()], "discipline_rating"),
        ("BIGGEST CHALLENGE", data.iloc[-1], "overall_rating"),
    ]

    for start in range(0, len(awards), 3):
        cols = st.columns(3)
        for col, (label, row, rating_col) in zip(cols, awards[start:start+3]):
            code = str(row["team"])
            with col:
                st.markdown(
                    f'<div class="panel" style="text-align:center;border-top:4px solid {TEAMS[code]["color"]}">'
                    f'<div class="micro">{label}</div>{logo(code,90)}'
                    f'<h3>{html.escape(TEAMS[code]["name"])}</h3>'
                    f'<div class="metric-number">{float(row[rating_col]):.1f}</div>'
                    f'<div class="micro">RANK #{int(row["rank"])}</div></div>',
                    unsafe_allow_html=True,
                )
                if st.button(f"OPEN {code}", key=f"report_{label}"):
                    go("PROFILE", code, True)

    section("THE FIVE BIGGEST RATINGS")
    for _, row in data.head(5).iterrows():
        rank_row(row, f"report_top_{row['team']}")

    section("EDITORIAL NOTE")
    st.markdown(
        "This report identifies leaders and standings from the current ratings file. "
        "It does not claim that a team won a particular game, improved this week, or earned a weekly award from game results. "
        "Those features become available when verified weekly snapshots or game-performance inputs are added."
    )
    st.caption(f"Historical snapshots recorded: {len(read_history())}")


# ============================================================
# METHODOLOGY
# ============================================================

def render_methodology():
    hero("SHOW YOUR WORK", "INSIDE THE", "RATINGS ENGINE.", "WHAT THE NUMBERS MEAN — AND WHAT THEY DO NOT.")
    section("THE FIVE RATING CATEGORIES")
    explanations = [
        ("OFFENSE", "Measures the team's offensive rating as supplied by the existing ratings engine."),
        ("DEFENSE", "Measures the team's defensive rating as supplied by the existing ratings engine."),
        ("SPECIAL TEAMS", "Represents the special-teams rating generated by the existing engine."),
        ("DISCIPLINE", "Represents the discipline rating generated by the existing engine."),
        ("ON-FIELD", "Represents the on-field rating generated by the existing engine."),
    ]
    for label, description in explanations:
        st.markdown(
            f'<div class="panel"><div class="micro">{label}</div><b>{description}</b></div>',
            unsafe_allow_html=True,
        )

    section("HOW TO READ THE OVERALL RATING")
    st.markdown(
        "The overall rating and team order are read directly from `nfl_rankings_2026.csv`. "
        "This website does not recalculate, normalize, or modify those values. "
        "The five category ratings are displayed as supporting attributes."
    )
    st.warning(
        "The exact weighting equation is intentionally not reproduced here because this website must not guess at the formula. "
        "The existing ratings engine remains the source of truth."
    )

    section("RATING SCALE")
    st.markdown(
        "- **Higher rating:** stronger result within this model.\n"
        "- **Lower rating:** weaker result within this model.\n"
        "- **Rank:** position among the 32 teams, based on the CSV.\n"
        "- **Category edge:** the team with the higher value in a specific category."
    )
    section("MODEL LIMITATIONS")
    st.markdown(
        "Ratings are model outputs, not a guarantee of future wins. A head-to-head category comparison is not a game simulation. "
        "The website does not invent game results, weekly movement, or historical values that are not present in its saved data."
    )
    section("DATA SOURCE")
    st.code(str(CSV_PATH), language="text")


# ============================================================
# DATABASE-POWERED NFL RECORDS
# ============================================================


# ============================================================
# WEEKLY CONTROL CENTER — RESULTS, RECORDS + SCHEDULE
# ============================================================


def render_weekly():

    # --------------------------------------------------------
    # PAGE HEADER + AUTOMATIC DATA STATUS
    # --------------------------------------------------------

    hero(
        "THE WEEKLY CONTROL CENTER",
        "GAME DAY",
        "HEADQUARTERS.",
        "LIVE NFL RESULTS. AUTOMATIC STANDINGS. COMPLETE SCHEDULE."
    )

    if NFL_DATA_STATUS["success"]:
        st.success(
            f'{NFL_DATA_STATUS["message"]} '
            f'Games: {NFL_DATA_STATUS["games"]} / '
            f'Completed: {NFL_DATA_STATUS["results"]}'
        )
    else:
        st.warning(NFL_DATA_STATUS["message"])

    if st.button("↻ REFRESH NFL DATA NOW", key="refresh_nfl_data"):
        load_espn_games.clear()
        sync_nfl_data()
        st.rerun()


    # --------------------------------------------------------
    # UPCOMING GAMES — WEEKLY MATCHUP SHOWCASE
    # --------------------------------------------------------

    section("UPCOMING GAMES")

    schedule = get_schedule()
    results = get_results()

    completed_ids = {
        str(game.get("schedule_id") or game.get("id"))
        for game in results
        if game.get("schedule_id") or game.get("id")
    }

    remaining_weeks = [
        int(game["week"])
        for game in schedule
        if game.get("week") is not None
        and str(game.get("id", "")) not in completed_ids
    ]

    current_week = min(remaining_weeks) if remaining_weeks else None

    upcoming_games = []

    if current_week is not None:

        now = datetime.now().astimezone().replace(tzinfo=None)

        for game in schedule:

            if int(game.get("week", 0)) != current_week:
                continue

            if str(game.get("id", "")) in completed_ids:
                continue

            # Exclude games that have already kicked off.
            try:
                kickoff_time = game.get("kickoff", "TBD")
                kickoff_clean = kickoff_time.rsplit(" ", 1)[0]

                game_datetime = datetime.strptime(
                    f'{game["date"]} {kickoff_clean}',
                    "%Y-%m-%d %I:%M %p"
                )

                if game_datetime <= now:
                    continue

            except (ValueError, TypeError, KeyError):
                pass

            upcoming_games.append(game)

    if upcoming_games:

        st.markdown(
            f'<div class="micro">WEEK {current_week} / '
            f'{len(upcoming_games)} UPCOMING MATCHUPS</div>',
            unsafe_allow_html=True
        )


        for game in upcoming_games:

            away = game["away"]
            home = game["home"]

            away_info = TEAMS[away]
            home_info = TEAMS[home]

            away_row = get_team_row(away)
            home_row = get_team_row(home)

            away_rank = (
                f'#{int(away_row["rank"])}'
                if away_row is not None else "—"
            )

            home_rank = (
                f'#{int(home_row["rank"])}'
                if home_row is not None else "—"
            )

            # Generate a basic matchup identity.
            if (
                away_info.get("division")
                and away_info.get("division") == home_info.get("division")
                and away_info.get("conference") == home_info.get("conference")
            ):
                tagline = "DIVISION RIVALRY"

            elif away_row is not None and home_row is not None:

                if (
                    rankings is not None
                    and float(away_row["defensive_rating"]) >= rankings["defensive_rating"].nlargest(8).min()
                    and float(home_row["defensive_rating"]) >= rankings["defensive_rating"].nlargest(8).min()
                ):
                    tagline = "DEFENSIVE SHOWDOWN"

                elif (
                    rankings is not None
                    and float(away_row["offensive_rating"]) >= rankings["offensive_rating"].nlargest(8).min()
                    and float(home_row["offensive_rating"]) >= rankings["offensive_rating"].nlargest(8).min()
                ):
                    tagline = "POTENTIAL SHOOTOUT"

                else:
                    tagline = "WEEKLY MATCHUP"

            else:
                tagline = "WEEKLY MATCHUP"

            try:
                date_label = datetime.strptime(
                    game["date"], "%Y-%m-%d"
                ).strftime("%A, %B %d").replace(" 0", " ")
            except (ValueError, TypeError):
                date_label = game.get("date", "DATE TBD")

            kickoff_label = game.get("kickoff", "TIME TBD")

            away_name = html.escape(away_info["name"])
            home_name = html.escape(home_info["name"])

            away_color = away_info.get("color", "#333333")
            home_color = home_info.get("color", "#555555")

            game_id = str(game.get("id", f"{away}_{home}_{current_week}"))

            with st.container(key=f"upcoming_matchup_card_{game_id}"):

                st.html(f"""
                    <div class="upcoming-matchup"
                         style="--away-color:{away_color};
                                --home-color:{home_color};">

                        <div class="matchup-topline">
                            <span class="matchup-tagline">{tagline}</span>
                            <span class="matchup-week">WEEK {current_week}</span>
                        </div>

                        <div class="matchup-teams">

                            <div class="matchup-team">
                                <div class="matchup-rank">{away_rank}</div>
                                {logo(away, 76)}
                                <div class="matchup-team-name">{away_name}</div>
                                <div class="matchup-side">AWAY</div>
                            </div>

                            <div class="matchup-vs">VS</div>

                            <div class="matchup-team">
                                <div class="matchup-rank">{home_rank}</div>
                                {logo(home, 76)}
                                <div class="matchup-team-name">{home_name}</div>
                                <div class="matchup-side">HOME</div>
                            </div>

                        </div>

                        <div class="matchup-bottom">
                            <div>{date_label}</div>
                            <div>{kickoff_label}</div>
                        </div>

                    </div>
                """)

                if st.button(
                    "VIEW GAME PREVIEW  →",
                    key=f"preview_{game_id}",
                    use_container_width=True,
                    type="secondary",
                ):
                    st.session_state.selected_game_preview = game_id
                    st.rerun()


        st.html("""
            <style>
                .upcoming-matchup {
                    position: relative;
                    overflow: hidden;
                    padding: 22px;
                    margin-bottom: 18px;
                    border: 1px solid #b99a5a55;
                    border-radius: 13px;
                    background:
                        linear-gradient(
                            110deg,
                            color-mix(in srgb, var(--away-color) 23%, #101010),
                            #111111 50%,
                            color-mix(in srgb, var(--home-color) 23%, #101010)
                        );
                    box-shadow: 0 8px 25px #0007;
                }

                .matchup-topline,
                .matchup-bottom {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    gap: 10px;
                    color: #c6c0b2;
                    font-size: 11px;
                    letter-spacing: 1.5px;
                    font-weight: 800;
                }

                .matchup-tagline {
                    color: #d8b86d;
                }

                .matchup-teams {
                    display: grid;
                    grid-template-columns: 1fr auto 1fr;
                    align-items: center;
                    gap: 12px;
                    padding: 27px 0;
                }

                .matchup-team {
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    text-align: center;
                    min-width: 0;
                }

                .matchup-rank {
                    color: #d8b86d;
                    font-size: 21px;
                    font-weight: 900;
                    margin-bottom: 8px;
                }

                .matchup-team img {
                    max-width: 76px;
                    margin-bottom: 12px;
                }

                .matchup-team-name {
                    color: white;
                    font-size: 14px;
                    font-weight: 900;
                    letter-spacing: 1px;
                }

                .matchup-side {
                    color: #999;
                    font-size: 10px;
                    letter-spacing: 2px;
                    margin-top: 5px;
                }

                .matchup-vs {
                    color: #d8b86d;
                    font-size: 19px;
                    font-weight: 900;
                }

                .matchup-bottom {
                    border-top: 1px solid #ffffff20;
                    padding-top: 15px;
                    flex-wrap: wrap;
                }

                @media (max-width: 500px) {
                    .upcoming-matchup {
                        padding: 15px;
                    }

                    .matchup-team-name {
                        font-size: 11px;
                    }

                    .matchup-team img {
                        max-width: 58px;
                    }
                }
                            /* UPCOMING MATCHUP CARD BUTTON */

                div[class*="st-key-upcoming_matchup_card_"] {
                    gap: 0 !important;
                }

                div[class*="st-key-upcoming_matchup_card_"] button {
                    background: #111111;
                    color: #d8b86d;
                    border: 1px solid #b99a5a55;
                    border-radius: 0 0 13px 13px;
                    font-weight: 900;
                    letter-spacing: 2px;
                    min-height: 45px;
                }

                div[class*="st-key-upcoming_matchup_card_"] button:hover {
                    background: #292316;
                    color: white;
                    border-color: #d8b86d;
                }
            </style>
        """)

    # --------------------------------------------------------
    # GAME PREVIEW DIALOG
    # --------------------------------------------------------

    @st.dialog("GAME PREVIEW", width="large", dismissible=False)
    def render_game_preview(game):

        away = game["away"]
        home = game["home"]
        away_record = game.get("away_record", "N/A")
        home_record = game.get("home_record", "N/A")
        stadium = game.get("stadium", "Stadium TBD")

        away_info = TEAMS[away]
        home_info = TEAMS[home]

        away_row = get_team_row(away)
        home_row = get_team_row(home)
        away_stats = get_team_row(away, team_metrics)
        home_stats = get_team_row(home, team_metrics)

        away_advantages, away_concerns = ([], [])
        home_advantages, home_concerns = ([], [])
        away_battles = []
        home_battles = []

        if away_stats is not None and home_stats is not None:
            away_advantages, away_concerns = build_matchup_analysis(
                away_stats, home_stats
            )

            home_advantages, home_concerns = build_matchup_analysis(
                home_stats, away_stats
            )
            away_battles = build_key_statistical_battles(
                away_stats, home_stats
            )
            home_battles = build_key_statistical_battles(
                home_stats, away_stats
            )
        away_probability = None
        home_probability = None
        underdog_advantages = []

        if away_row is not None and home_row is not None:
            home_probability = calculate_win_probability(
                float(home_row["overall_rating"]),
                float(away_row["overall_rating"]),
                True,
            )

            away_probability = 1 - home_probability

            if away_probability < home_probability:
                underdog_advantages = away_advantages
            else:
                underdog_advantages = home_advantages

            upset_alert = (
                    away_probability is not None
                    and home_probability is not None
                    and min(away_probability, home_probability) >= 0.30
                    and len(underdog_advantages) >= 2
                    and max(
                (advantage["strength"] for advantage in underdog_advantages),
                default=0,
            ) >= 0.15
            )


        away_rank = (
            f'#{int(away_row["rank"])}'
            if away_row is not None else "—"
        )

        home_rank = (
            f'#{int(home_row["rank"])}'
            if home_row is not None else "—"
        )

        try:
            date_label = datetime.strptime(
                game["date"], "%Y-%m-%d"
            ).strftime("%A, %B %d, %Y")
        except (ValueError, TypeError, KeyError):
            date_label = game.get("date", "DATE TBD")

        kickoff_label = game.get("kickoff", "TIME TBD")

        st.html(f"""
            <div style="
                padding: 25px;
                border: 1px solid #b99a5a66;
                border-radius: 15px;
                background: linear-gradient(
                    110deg,
                    {away_info.get('color', '#333333')}44,
                    #111111 50%,
                    {home_info.get('color', '#333333')}44
                );
                text-align: center;
            ">
                <div style="
                    color: #d8b86d;
                    grid-column: 1 / -1;
                    font-size: 12px;
                    font-weight: 900;
                    letter-spacing: 3px;
                ">
                    WEEK {game.get("week", current_week)}
                    
                    </div>
                    
                    <div style="
                    display: grid;
                    grid-template-columns: 1fr auto 1fr;
                    align-items: center;
                    gap: 25px;
                    padding: 25px 0;
                ">
                    <div>
                        <div style="
                            color: #d8b86d;
                            font-size: 11px;
                            font-weight: 900;
                            letter-spacing: 2px;
                            margin-bottom: 8px;
                        ">
                            AWAY
                        </div>

                        {logo(away, 105)}

                        <div style="
                            color: white;
                            font-size: 18px;
                            font-weight: 900;
                            margin-top: 12px;
                        ">
                            {html.escape(away_info["name"])}
                        </div>

                        <div style="
                            color: #d0c9b9;
                            font-size: 13px;
                            font-weight: 700;
                            margin-top: 5px;
                        ">
                            {html.escape(away_record)}
                        </div>

                        <div style="
                            color: #d8b86d;
                            font-size: 22px;
                            font-weight: 900;
                        ">
                            {away_rank}
                        </div>
                    </div>

                    <div style="
                        color: #d8b86d;
                        font-size: 24px;
                        font-weight: 900;
                    ">
                        VS
                    </div>

                    <div>
                        <div style="
                            color: #d8b86d;
                            font-size: 11px;
                            font-weight: 900;
                            letter-spacing: 2px;
                            margin-bottom: 8px;
                        ">
                            HOME
                        </div>

                        {logo(home, 105)}

                        <div style="
                            color: white;
                            font-size: 18px;
                            font-weight: 900;
                            margin-top: 12px;
                        ">
                            {html.escape(home_info["name"])}
                        </div>

                        <div style="
                            color: #d0c9b9;
                            font-size: 13px;
                            font-weight: 700;
                            margin-top: 5px;
                        ">
                            {html.escape(home_record)}
                        </div>

                        <div style="
                            color: #d8b86d;
                            font-size: 22px;
                            font-weight: 900;
                        ">
                            {home_rank}
                        </div>
                    </div>
                        <div style="
                        color: #d8b86d;
                        grid-column: 1 / -1;
                        font-size: 14px;
                        font-weight: 900;
                        letter-spacing: 1px;
                        margin-top: 12px;
                        text-align: center;
                    ">
                        {html.escape(stadium)}
                    </div>

                    <div style="
                        color: #d0c9b9;
                        font-size: 12px;
                        grid-column: 1 / -1;
                        font-weight: 700;
                        letter-spacing: 0.5px;
                        margin-top: 6px;
                        text-align: center;
                    ">
                        {date_label} &nbsp; | &nbsp; {kickoff_label}
                    </div>
                </div>
            </div>
            """)


        st.markdown("### Confidence Meter")

        if away_probability is not None and home_probability is not None:
            away_percentage = away_probability * 100
            home_percentage = home_probability * 100

            favorite = (
                away_info["name"]
                if away_probability >= 0.50
                else home_info["name"]
            )

            underdog = (
                home_info["name"]
                if away_probability >= 0.50
                else away_info["name"]
            )
        st.html(f"""
            <div style="
                background: #171717;
                border: 1px solid #b99a5a66;
                border-radius: 14px;
                padding: 22px;
                margin: 10px 0 25px 0;
            ">
                <div style="
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    gap: 15px;
                    margin-bottom: 15px;
                ">
                    <div style="text-align: left;">
                        <div style="
                            color: #d8b86d;
                            font-size: 11px;
                            font-weight: 900;
                            letter-spacing: 1px;
                        ">AWAY</div>
                        <div style="
                            color: white;
                            font-size: 25px;
                            font-weight: 900;
                        ">{away_percentage:.1f}%</div>
                        <div style="
                            color: #bdb6a7;
                            font-size: 12px;
                        ">{html.escape(away_info["name"])}</div>
                    </div>

                    <div style="text-align: right;">
                        <div style="
                            color: #d8b86d;
                            font-size: 11px;
                            font-weight: 900;
                            letter-spacing: 1px;
                        ">HOME</div>
                        <div style="
                            color: white;
                            font-size: 25px;
                            font-weight: 900;
                        ">{home_percentage:.1f}%</div>
                        <div style="
                            color: #bdb6a7;
                            font-size: 12px;
                        ">{html.escape(home_info["name"])}</div>
                    </div>
                </div>

                <div style="
                    display: flex;
                    width: 100%;
                    height: 17px;
                    overflow: hidden;
                    border-radius: 20px;
                    background: #333;
                ">
                    <div style="
                        width: {away_percentage:.2f}%;
                        background: {away_info.get('color', '#777777')};
                    "></div>
                    <div style="
                        width: {home_percentage:.2f}%;
                        background: {home_info.get('color', '#777777')};
                    "></div>
                </div>

                <div style="
                    display: flex;
                    justify-content: space-between;
                    margin-top: 14px;
                    color: #d8b86d;
                    font-size: 11px;
                    font-weight: 900;
                    letter-spacing: 1px;
                ">
                    <span>MODEL FAVORITE: {html.escape(favorite.upper())}</span>
                    <span>UNDERDOG: {html.escape(underdog.upper())}</span>
                </div>
            </div>
        """)
        if upset_alert:
            st.html(f"""
                <div style="
                    background: linear-gradient(110deg, #3b2410, #171717);
                    border: 1px solid #d8a34a;
                    border-left: 5px solid #e0a33e;
                    border-radius: 10px;
                    padding: 17px 20px;
                    margin: 0 0 25px 0;
                ">
                    <div style="
                        color: #f0b653;
                        font-size: 13px;
                        font-weight: 900;
                        letter-spacing: 2px;
                        margin-bottom: 7px;
                    ">
                        ⚠ UPSET ALERT
                    </div>
                    <div style="
                        color: white;
                        font-size: 16px;
                        font-weight: 800;
                        margin-bottom: 6px;
                    ">
                        {html.escape(underdog)} HAS A REALISTIC PATH TO AN UPSET
                    </div>
                    <div style="
                        color: #d0c9b9;
                        font-size: 13px;
                        line-height: 1.5;
                    ">
                        Despite being the underdog, this team has
                        {len(underdog_advantages)} meaningful statistical
                        matchup advantages that could help them pull off
                        the upset.
                    </div>
                </div>
            """)



        st.markdown("### Matchup Intelligence")

        def matchup_items_html(items, color, label):
            if not items:
                return (
                    '<div style="color:#999;font-size:12px;'
                    'padding:8px 0;">No significant findings</div>'
                )

            rows = ""

            for item in items[:3]:
                side_symbol = "Ⓞ" if item["side"] == "OFFENSE" else "Ⓧ"
                rows += f"""
                    <div style="
                        display:flex;
                        justify-content:space-between;
                        align-items:center;
                        gap:10px;
                        padding:10px 0;
                        border-bottom:1px solid #ffffff12;
                    ">
                        <div style="
                            color:#f2f0e9;
                            font-size:13px;
                            font-weight:700;
                        ">
                            {html.escape(item['category'])}
                        </div>
                        <span style="
                            background:{color}18;
                            color:{color};
                            border:1px solid {color}55;
                            border-radius:20px;
                            padding:4px 8px;
                            font-size:12px;
                            font-weight:900;
                            letter-spacing:0.7px;
                            white-space:nowrap;
                        ">
                            {side_symbol} {html.escape(item['side'])}
                        </span>
                    </div>
                """

            return rows

        away_advantage_html = matchup_items_html(
            away_advantages, "#65c98b", "ADVANTAGES"
        )
        away_concern_html = matchup_items_html(
            away_concerns, "#e47777", "CONCERNS"
        )
        home_advantage_html = matchup_items_html(
            home_advantages, "#65c98b", "ADVANTAGES"
        )
        home_concern_html = matchup_items_html(
            home_concerns, "#e47777", "CONCERNS"
        )

        st.html(f"""
            <div style="
                display:grid;
                grid-template-columns:repeat(2,minmax(0,1fr));
                gap:16px;
                margin:10px 0 28px 0;
            ">
                <div style="
                    background:linear-gradient(145deg,#202020,#151515);
                    border:1px solid #b99a5a66;
                    border-radius:14px;
                    padding:18px;
                    min-width:0;
                ">
                    <div style="
                        color:#d8b86d;
                        font-size:15px;
                        font-weight:900;
                        letter-spacing:1.5px;
                        margin-bottom:5px;
                    ">AWAY TEAM</div>

                    <div style="
                        color:white;
                        font-size:18px;
                        font-weight:900;
                        margin-bottom:18px;
                    ">{html.escape(away_info['name'])}</div>

                    <div style="
                        color:#65c98b;
                        font-size:14px;
                        font-weight:900;
                        letter-spacing:1px;
                        margin-bottom:5px;
                    ">▲ MATCHUP ADVANTAGES</div>

                    {away_advantage_html}

                    <div style="
                        color:#e47777;
                        font-size:14px;
                        font-weight:900;
                        letter-spacing:1px;
                        margin-top:20px;
                        margin-bottom:5px;
                    ">▼ AREAS OF CONCERN</div>

                    {away_concern_html}
                </div>

                <div style="
                    background:linear-gradient(145deg,#202020,#151515);
                    border:1px solid #b99a5a66;
                    border-radius:14px;
                    padding:18px;
                    min-width:0;
                ">
                    <div style="
                        color:#d8b86d;
                        font-size:15px;
                        font-weight:900;
                        letter-spacing:1.5px;
                        margin-bottom:5px;
                    ">HOME TEAM</div>

                    <div style="
                        color:white;
                        font-size:18px;
                        font-weight:900;
                        margin-bottom:18px;
                    ">{html.escape(home_info['name'])}</div>

                    <div style="
                        color:#65c98b;
                        font-size:14px;
                        font-weight:900;
                        letter-spacing:1px;
                        margin-bottom:5px;
                    ">▲ MATCHUP ADVANTAGES</div>

                    {home_advantage_html}

                    <div style="
                        color:#e47777;
                        font-size:14px;
                        font-weight:900;
                        letter-spacing:1px;
                        margin-top:20px;
                        margin-bottom:5px;
                    ">▼ AREAS OF CONCERN</div>

                    {home_concern_html}
                </div>
            </div>
        """)

        away_key = build_game_preview_key(
            away_advantages,
            away_concerns,
        )

        home_key = build_game_preview_key(
            home_advantages,
            home_concerns,
        )

        st.markdown("### Key to Victory")

        def key_card_html(team_name, key, color):
            stat_line = key["stat_line"] or ""

            return f"""
                <div style="
                    background:linear-gradient(145deg,#202020,#151515);
                    border:1px solid {color}66;
                    border-radius:14px;
                    padding:20px;
                    height:100%;
                ">
                    <div style="
                        color:{color};
                        font-size:10px;
                        font-weight:900;
                        letter-spacing:1.5px;
                        margin-bottom:7px;
                    ">KEY TO VICTORY</div>

                    <div style="
                        color:white;
                        font-size:18px;
                        font-weight:900;
                        margin-bottom:12px;
                    ">{html.escape(team_name)}</div>

                    <div style="
                        color:{color};
                        font-size:17px;
                        font-weight:900;
                        margin-bottom:10px;
                    ">{html.escape(key["title"])}</div>

                    <div style="
                        color:#aaa;
                        font-size:10px;
                        font-weight:800;
                        letter-spacing:1px;
                        margin-bottom:12px;
                    ">{html.escape(key["category"])} · {html.escape(key["side"])}</div>

                    <div style="
                        color:#e5e5e5;
                        font-size:13px;
                        line-height:1.6;
                    ">{html.escape(key["explanation"])}</div>

                    {f'''
                    <div style="
                        border-top:1px solid #ffffff20;
                        margin-top:16px;
                        padding-top:12px;
                        color:#d8b86d;
                        font-size:11px;
                        font-weight:700;
                        line-height:1.5;
                    ">{html.escape(stat_line)}</div>
                    ''' if stat_line else ""}
                </div>
            """

        away_key_html = key_card_html(
            away_info["name"], away_key, "#65a9e8"
        )

        home_key_html = key_card_html(
            home_info["name"], home_key, "#e47777"
        )

        st.html(f"""
            <div style="
                display:grid;
                grid-template-columns:repeat(2,minmax(0,1fr));
                gap:16px;
                margin:10px 0 28px 0;
            ">
                {away_key_html}
                {home_key_html}
            </div>
        """)

        st.markdown("### Key Stituational Battles")
        def format_battle_value(category, value):
            if category in ("Pass Protection", "Fourth Down"):
                return f"{value:.1%}"

            return f"{value:.2f}"
        def battle_card_html(team_name, battles, color):
            battle_rows = ""

            for battle in battles:
                team_value = format_battle_value(
                    battle["category"], battle["team_value"]
                )


                thresholds = {
                    "Turnover Battle": 0.15,
                    "Pass Protection": 0.01,
                    "Fourth Down": 0.03,
                    "Penalty Discipline": 5.0,
                }

                edge = battle["edge"]
                threshold = thresholds[battle["category"]]

                if edge > threshold:
                    team_value_color = "#35c979"
                elif edge < -threshold:
                    team_value_color = "#ef6262"
                else:
                    team_value_color = "#b0b0b0"

                battle_rows += f"""
                    <div style="
                        border-top:1px solid #ffffff20;
                        padding:14px 0;
                    ">
                        <div style="
                            color:#e0e0e0;
                            font-size:14px;
                            font-weight:900;
                            margin-bottom:8px;
                        ">{html.escape(battle["category"])}</div>

                        <div style="
                            display:flex;
                            justify-content:space-between;
                            gap:12px;
                            color:{team_value_color};
                            font-size:12px;
                            margin-bottom:8px;
                        ">
                            <span>{html.escape(battle["team_label"])}</span>
                            <strong>{team_value}</strong>
                        </div>


                        <div style="
                            color:#aaa;
                            font-size:11px;
                            line-height:1.5;
                        ">{html.escape(battle["description"])}</div>
                    </div>
                """

            if not battle_rows:
                battle_rows = """
                    <div style="color:#aaa;font-size:12px;">
                        Not enough statistical data available.
                    </div>
                """

            return f"""
                <div style="
                    background:linear-gradient(145deg,#202020,#151515);
                    border:1px solid #444444;
                    border-radius:14px;
                    padding:20px;
                    height:100%;
                ">
                    <div style="
                        color:white;
                        font-size:17px;
                        font-weight:900;
                        margin-bottom:14px;
                    ">{html.escape(team_name)}</div>

                    {battle_rows}
                </div>
            """
        away_battle_html = battle_card_html(
            away_info["name"], away_battles, "#65a9e8"
        )
        home_battle_html = battle_card_html(
            home_info["name"], home_battles, "#e47777"
        )
        st.html(f"""
            <div style="
                display:grid;
                grid-template-columns:repeat(2,minmax(0,1fr));
                gap:16px;
                margin:10px 0 28px 0;
            ">
                {away_battle_html}
                {home_battle_html}
            </div>
        """)

        if st.button("CLOSE PREVIEW", use_container_width=True):
            st.session_state.selected_game_preview = None
            st.rerun()

    selected_game_id = st.session_state.selected_game_preview

    selected_game = next(
        (
            game for game in upcoming_games
            if str(game.get("id")) == str(selected_game_id)
        ),
        None
    )

    if selected_game is not None:
        render_game_preview(selected_game)

    else:
        st.info("No upcoming games found for the current NFL week.")

    # --------------------------------------------------------
    # DIVISION RACE
    # --------------------------------------------------------

    section("DIVISION RACE")

    def render_division_card(conference, division):

        division_data = get_standings(
            conference=conference,
            division=division,
        )

        rows_html = ""

        for position, (_, team) in enumerate(division_data.iterrows()):

            code = team["Code"]
            name = html.escape(str(team["Team"]))
            record = (
                f'{int(team["W"])}-'
                f'{int(team["L"])}-'
                f'{int(team["T"])}'
            )
            pct = f'{float(team["PCT"]):.3f}'

            is_leader = position == 0

            row_background = (
                "linear-gradient(90deg,#B99A5A22,#B99A5A08)"
                if is_leader else "#FFFFFF05"
            )

            border_color = (
                "#B99A5A" if is_leader else "#35332D"
            )

            leader_label = (
                '<div style="font-size:9px;color:#D8B86D;'
                'font-weight:800;letter-spacing:1px;">'
                'DIVISION LEADER</div>'
                if is_leader else ""
            )

            rows_html += f"""
                <div style="
                    display:flex;
                    align-items:center;
                    gap:11px;
                    padding:10px 9px;
                    margin-top:7px;
                    border-radius:9px;
                    background:{row_background};
                    border-left:3px solid {border_color};
                ">
                    <div style="
                        width:22px;
                        color:#B99A5A;
                        font-size:12px;
                        font-weight:800;
                        text-align:center;
                    ">
                        {position + 1}
                    </div>

                    <div style="
                        width:64px;
                        height:64px;
                        display:flex;
                        align-items:center;
                        justify-content:center;
                        flex-shrink:0;
                    ">
                        {logo(code, width=60)}
                    </div>

                    <div style="flex:1;min-width:0;">
                        <div style="
                            color:#F4F0E7;
                            font-size:19px;
                            font-weight:900;
                            letter-spacing:1px;
                        ">
                            {code}
                        </div>
                        <div style="
                            color:#AAA69C;
                            font-size:15px;
                        ">
                            {name}
                        </div>
                        {leader_label}
                    </div>

                    <div style="text-align:right;">
                        <div style="
                            color:#F4F0E7;
                            font-size:20px;
                            font-weight:900;
                            font-variant-numeric:tabular-nums;
                        ">
                            {record}
                        </div>
                        <div style="
                            color:#B99A5A;
                            font-size:14px;
                            font-weight:700;
                        ">
                            {pct}
                        </div>
                    </div>
                </div>
            """

        st.html(f"""
            <div style="
                background:linear-gradient(145deg,#201F1B,#111110);
                border:1px solid #39362E;
                border-radius:14px;
                padding:15px;
                margin-bottom:14px;
                box-shadow:0 8px 22px #0005;
            ">
                <div style="
                    display:flex;
                    justify-content:space-between;
                    align-items:center;
                    padding-bottom:10px;
                    border-bottom:1px solid #39362E;
                ">
                    <div style="
                        color:#D8B86D;
                        font-size:20px;
                        font-weight:900;
                        letter-spacing:2px;
                    ">
                        {conference} {division.upper()}
                    </div>
                    <div style="
                        color:#77736A;
                        font-size:10px;
                        letter-spacing:1px;
                    ">
                        DIVISION
                    </div>
                </div>

                {rows_html}
            </div>
        """)

    def render_conference_header(abbreviation, full_name):

        st.html(f"""
            <div style="
                text-align:center;
                padding:24px 10px 18px;
                margin-top:12px;
            ">
                <div style="
                    color:#B99A5A;
                    font-size:11px;
                    font-weight:800;
                    letter-spacing:5px;
                    margin-bottom:5px;
                ">
                    {full_name}
                </div>

                <div style="
                    color:#F4F0E7;
                    font-size:36px;
                    font-weight:1000;
                    letter-spacing:7px;
                    text-shadow:0 0 22px #B99A5A55;
                ">
                    {abbreviation}
                </div>

                <div style="
                    width:100px;
                    height:2px;
                    margin:12px auto 0;
                    background:linear-gradient(
                        90deg,transparent,#B99A5A,transparent
                    );
                "></div>
            </div>
        """)

    # AFC

    render_conference_header(
        "AFC",
        "AMERICAN FOOTBALL CONFERENCE",
    )

    afc_left, afc_right = st.columns(2)

    with afc_left:
        render_division_card("AFC", "North")
        render_division_card("AFC", "South")

    with afc_right:
        render_division_card("AFC", "East")
        render_division_card("AFC", "West")

    # NFC

    render_conference_header(
        "NFC",
        "NATIONAL FOOTBALL CONFERENCE",
    )

    nfc_left, nfc_right = st.columns(2)

    with nfc_left:
        render_division_card("NFC", "North")
        render_division_card("NFC", "South")

    with nfc_right:
        render_division_card("NFC", "East")
        render_division_card("NFC", "West")

    # --------------------------------------------------------
    # PLAYOFF PICTURE
    # --------------------------------------------------------

    section("PLAYOFF PICTURE")

    playoff_picture = get_playoff_picture()

    def render_playoff_conference(conference):

        data = playoff_picture[conference]
        playoff_teams = data["playoff_teams"]
        in_the_hunt = data["in_the_hunt"]

        rows_html = ""

        for _, team in playoff_teams.iterrows():

            code = team["Code"]
            name = team["Team"]
            seed = int(team["Seed"])
            record = f'{team["W"]}-{team["L"]}'

            if team["T"] > 0:
                record += f'-{team["T"]}'

            team_type = team["Type"]

            if team_type == "DIVISION WINNER":
                label = "DIVISION WINNER"
                label_color = "#D8B86D"
            else:
                label = "WILD CARD"
                label_color = "#8CADD1"

            rows_html += f"""
                <div style="
                    display:flex;
                    align-items:center;
                    gap:12px;
                    padding:11px 10px;
                    border-bottom:1px solid #39362E;
                ">
                    <div style="
                        color:#D8B86D;
                        font-size:19px;
                        font-weight:900;
                        width:25px;
                        text-align:center;
                    ">
                        {seed}
                    </div>

                    {logo(code, width=42)}

                    <div style="flex:1;min-width:0;">
                        <div style="
                            color:#F4F0E7;
                            font-size:15px;
                            font-weight:800;
                        ">
                            {name}
                        </div>
                        <div style="
                            color:{label_color};
                            font-size:9px;
                            font-weight:800;
                            letter-spacing:1px;
                        ">
                            {label}
                        </div>
                    </div>

                    <div style="
                        color:#F4F0E7;
                        font-size:16px;
                        font-weight:900;
                        font-variant-numeric:tabular-nums;
                    ">
                        {record}
                    </div>
                </div>
            """

        hunt_html = ""

        for _, team in in_the_hunt.iterrows():

            code = team["Code"]
            name = team["Team"]
            record = f'{team["W"]}-{team["L"]}'
            games_back = team["Games Back"]

            if team["T"] > 0:
                record += f'-{team["T"]}'

            hunt_html += f"""
                <div style="
                    display:flex;
                    align-items:center;
                    gap:10px;
                    padding:9px 10px;
                    border-bottom:1px solid #302E29;
                ">
                    {logo(code, width=32)}

                    <div style="
                        flex:1;
                        color:#D8D3C8;
                        font-size:13px;
                        font-weight:700;
                    ">
                        {name}
                    </div>

                    <div style="
                        color:#AAA69C;
                        font-size:12px;
                        font-weight:700;
                    ">
                        {record}
                    </div>

                    <div style="
                        color:#D8B86D;
                        font-size:12px;
                        font-weight:900;
                        min-width:48px;
                        text-align:right;
                    ">
                        {games_back:.1f} GB
                    </div>
                </div>
            """

        if not hunt_html:
            hunt_html = """
                <div style="
                    color:#77736A;
                    padding:12px;
                    font-size:12px;
                ">
                    No teams currently within 2 games.
                </div>
            """

        st.html(f"""
            <div style="
                background:linear-gradient(145deg,#201F1B,#111110);
                border:1px solid #39362E;
                border-radius:14px;
                padding:14px;
                margin-bottom:16px;
                box-shadow:0 8px 22px #0005;
            ">
                <div style="
                    color:#D8B86D;
                    font-size:19px;
                    font-weight:900;
                    letter-spacing:2px;
                    padding:5px 8px 13px;
                    border-bottom:1px solid #39362E;
                ">
                    {conference}
                </div>

                {rows_html}

                <div style="
                    color:#D8B86D;
                    font-size:12px;
                    font-weight:900;
                    letter-spacing:2px;
                    padding:18px 8px 5px;
                ">
                    IN THE HUNT
                </div>

                {hunt_html}
            </div>
        """)

    playoff_left, playoff_right = st.columns(2)

    with playoff_left:
        render_playoff_conference("AFC")

    with playoff_right:
        render_playoff_conference("NFC")


    # --------------------------------------------------------
    # PLAYOFF SIMULATOR — VISUAL BRACKET
    # --------------------------------------------------------

    section("PLAYOFF SIMULATOR")

    simulator = st.session_state.playoff_simulator

    for conference in ("AFC", "NFC"):
        if conference not in simulator:
            simulator[conference] = build_playoff_bracket(
                playoff_picture[conference]["playoff_teams"],
                conference,
            )

    # --------------------------------------------------------
    # BRACKET STYLING
    # --------------------------------------------------------

    st.html("""
        <style>
            .bracket-heading {
                color: #D8B86D;
                font-size: 13px;
                font-weight: 900;
                letter-spacing: 2px;
                text-align: center;
                padding: 10px 2px;
                border-bottom: 2px solid #B99A5A;
                margin-bottom: 12px;
            }

            .bracket-game {
                background: linear-gradient(145deg,#201F1B,#111110);
                border: 1px solid #39362E;
                border-radius: 10px;
                padding: 9px 7px;
                margin-bottom: 12px;
                box-shadow: 0 5px 14px #0004;
            }

            .bracket-game-title {
                color: #B99A5A;
                font-size: 9px;
                font-weight: 900;
                letter-spacing: 1px;
                text-align: center;
                padding-bottom: 7px;
                border-bottom: 1px solid #39362E;
                margin-bottom: 7px;
            }

            .bracket-team {
                display: flex;
                align-items: center;
                gap: 5px;
                color: #F4F0E7;
                font-size: 11px;
                font-weight: 800;
                min-height: 40px;
                padding: 3px;
            }

            .bracket-team.winner {
                color: #D8B86D;
                background: #B99A5A18;
                border-radius: 6px;
            }

            .bracket-placeholder {
                color: #77736A;
                font-size: 10px;
                font-weight: 700;
                text-align: center;
                padding: 13px 3px;
                border: 1px dashed #39362E;
                border-radius: 7px;
                margin-bottom: 7px;
            }

            .bracket-vs {
                color: #77736A;
                font-size: 9px;
                font-weight: 900;
                text-align: center;
                padding: 3px;
            }

            .bracket-center {
                text-align: center;
                color: #D8B86D;
                font-weight: 900;
                letter-spacing: 2px;
            }
        </style>
    """)

    # --------------------------------------------------------
    # BRACKET HELPER FUNCTIONS
    # --------------------------------------------------------

    def resolve_bracket_team(bracket, value):
        if value is None:
            return None

        if isinstance(value, int):
            return bracket["teams"].get(value)

        return value

    def get_team_seed(bracket, code):
        if not code:
            return None

        for seed, team_code in bracket["teams"].items():
            if team_code == code:
                return seed

        return None


    def render_bracket_team(
        conference,
        bracket,
        round_name,
        matchup_index,
        code,
        selected_winner,
    ):
        if not code:
            st.html("""
                <div class="bracket-placeholder">
                    AWAITING WINNER
                </div>
            """)
            return

        info = TEAMS[code]
        seed = get_team_seed(bracket, code)
        is_winner = selected_winner == code

        # Unique container lets us style each team's button
        container_key = (
            f"team_{conference}_{round_name}_{matchup_index}_{code}"
        )

        logo_url = html.escape(info["logo"], quote=True)
        team_color = info["color"]
        secondary_color = info["secondary"]

        st.html(f"""
            <style>
                .st-key-{container_key} button {{
                    min-height: 48px;
                    height: 48px;
                    width: 100%;
                    border: 1px solid {team_color};
                    border-left: 4px solid {secondary_color};
                    border-radius: 6px;
                    background-color: {team_color}22;
                    background-image: url("{logo_url}");
                    background-repeat: no-repeat;
                    background-position: 10px center;
                    background-size: 32px 32px;
                    color: white;
                    font-size: 13px;
                    font-weight: 800;
                    text-align: right;
                    padding: 0 12px 0 48px;
                    box-shadow: {"0 0 10px " + team_color + "66" if is_winner else "none"};
                }}

                .st-key-{container_key} button:hover {{
                    border: 1px solid {secondary_color};
                    border-left: 4px solid {secondary_color};
                    background-color: {team_color}55;
                    color: white;
                }}
            </style>
        """)

        with st.container(key=container_key):
            if st.button(
                f"#{seed}" if seed else "—",
                key=f"bracket_{conference}_{round_name}_{matchup_index}_{code}",
                use_container_width=True,
            ):
                simulator[conference] = advance_playoff_bracket(
                    bracket,
                    round_name,
                    matchup_index,
                    code,
                )
                st.rerun()

    def render_bracket_game(
        conference,
        bracket,
        round_name,
        matchup_index,
        team_one,
        team_two,
        game_title,
    ):
        team_one = resolve_bracket_team(bracket, team_one)
        team_two = resolve_bracket_team(bracket, team_two)

        selected_winner = bracket.get("winners", {}).get(
            f"{round_name}_{matchup_index}"
        )

        st.html(f"""
            <div class="bracket-game">
                <div class="bracket-game-title">
                    {game_title}
                </div>
            </div>
        """)

        render_bracket_team(
            conference,
            bracket,
            round_name,
            matchup_index,
            team_one,
            selected_winner,
        )

        st.html('<div class="bracket-vs">VS</div>')

        render_bracket_team(
            conference,
            bracket,
            round_name,
            matchup_index,
            team_two,
            selected_winner,
        )

    # --------------------------------------------------------
    # PREPARE BRACKET DATA
    # --------------------------------------------------------

    afc_bracket = simulator["AFC"]
    nfc_bracket = simulator["NFC"]

    # --------------------------------------------------------
    # SEVEN-COLUMN BRACKET
    # --------------------------------------------------------

    (
        nfc_wc_col,
        nfc_div_col,
        nfc_champ_col,
        super_bowl_col,
        afc_champ_col,
        afc_div_col,
        afc_wc_col,
    ) = st.columns([1.2, 1.15, 1.1, 1.3, 1.1, 1.15, 1.2])

    # ========================================================
    # NFC WILD CARD — LEFT EDGE
    # ========================================================

    with nfc_wc_col:

        st.html('<div class="bracket-heading">NFC<br>WILD CARD</div>')

        for i, (seed_one, seed_two) in enumerate(
            nfc_bracket["wild_card"]
        ):
            render_bracket_game(
                "NFC",
                nfc_bracket,
                "wild_card",
                i,
                nfc_bracket["teams"].get(seed_one),
                nfc_bracket["teams"].get(seed_two),
                f"GAME {i + 1}",
            )


    # ========================================================
    # NFC DIVISIONAL
    # ========================================================

    with nfc_div_col:

        st.html('<div class="bracket-heading">NFC<br>DIVISIONAL</div>')

        nfc_wc_winners = [
            nfc_bracket.get("winners", {}).get(f"wild_card_{i}")
            for i in range(3)
        ]

        st.html('<div style="height:65px;"></div>')

        if all(nfc_wc_winners):
            divisional_matchups = nfc_bracket["divisional"]
        else:
            # Show the available teams while Wild Card games remain.
            available_teams = [
                nfc_bracket["teams"].get(1),
                *[winner for winner in nfc_wc_winners if winner],
            ]

            available_teams.sort(
                key=lambda code: next(
                    seed for seed, team in nfc_bracket["teams"].items()
                    if team == code
                )
            )

            divisional_matchups = [
                (available_teams[0] if len(available_teams) > 0 else None,
                 available_teams[3] if len(available_teams) > 3 else None),
                (available_teams[1] if len(available_teams) > 1 else None,
                 available_teams[2] if len(available_teams) > 2 else None),
            ]

        for i, matchup in enumerate(divisional_matchups):
            render_bracket_game(
                "NFC",
                nfc_bracket,
                "divisional",
                i,
                matchup[0],
                matchup[1],
                f"GAME {i + 1}",
            )

            if i == 0:
                st.html('<div style="height:85px;"></div>')


    # ========================================================
    # NFC CHAMPIONSHIP
    # ========================================================

    with nfc_champ_col:

        st.html('<div class="bracket-heading">NFC<br>CHAMPIONSHIP</div>')
        st.html('<div style="height:190px;"></div>')

        nfc_div_winners = [
            nfc_bracket.get("winners", {}).get(f"divisional_{i}")
            for i in range(2)
        ]

        if all(nfc_div_winners):
            render_bracket_game(
                "NFC",
                nfc_bracket,
                "championship",
                0,
                nfc_div_winners[0],
                nfc_div_winners[1],
                "NFC TITLE GAME",
            )
        else:
            for code in nfc_div_winners:
                if code:
                    info = TEAMS[code]
                    seed = get_team_seed(nfc_bracket, code)

                    st.html(f"""
                        <div style="
                            display:flex;
                            align-items:center;
                            gap:8px;
                            padding:9px;
                            margin-bottom:8px;
                            border-left:4px solid {info['color']};
                            background:{info['color']}22;
                            border-radius:5px;
                        ">
                            {logo(code, width=34)}
                            <span style="color:white;font-weight:800;">
                                #{seed} {info['name']}
                            </span>
                        </div>
                    """)
                else:
                    st.html("""
                        <div class="bracket-placeholder">
                            AWAITING DIVISIONAL WINNER
                        </div>
                    """)

        nfc_champion = nfc_bracket.get("conference_champion")

        if nfc_champion:
            st.success(f"NFC: {TEAMS[nfc_champion]['name']}")


    # ========================================================
    # SUPER BOWL — CENTER
    # ========================================================

    afc_champion = afc_bracket.get("conference_champion")
    nfc_champion = nfc_bracket.get("conference_champion")

    current_super_bowl_matchup = (
        (afc_champion, nfc_champion)
        if afc_champion and nfc_champion
        else None
    )

    if current_super_bowl_matchup != st.session_state.super_bowl_matchup:
        st.session_state.super_bowl_matchup = current_super_bowl_matchup
        st.session_state.super_bowl_winner = None

    with super_bowl_col:

        st.html("""
            <div class="bracket-heading">
                SUPER<br>BOWL
            </div>
            <div style="height:130px;"></div>
        """)

        for conference, code, bracket in (
            ("NFC", nfc_champion, nfc_bracket),
            ("AFC", afc_champion, afc_bracket),
        ):

            if code:
                info = TEAMS[code]
                seed = get_team_seed(bracket, code)
                is_selected = st.session_state.super_bowl_winner == code

                st.html(f"""
                    <div style="
                        display:flex;
                        align-items:center;
                        gap:8px;
                        padding:10px 6px;
                        margin-bottom:8px;
                        border:1px solid {info['color']};
                        border-left:4px solid {info['secondary']};
                        border-radius:6px;
                        background:{info['color']}22;
                        box-shadow:{"0 0 12px " + info['color'] + "66" if is_selected else "none"};
                    ">
                        {logo(code, width=48)}
                        <div style="min-width:0;">
                            <div style="color:white;font-weight:900;font-size:11px;">
                                #{seed} {info['name']}
                            </div>
                            <div style="color:#D8B86D;font-size:9px;">
                                {conference} CHAMPION
                            </div>
                        </div>
                    </div>
                """)

                if current_super_bowl_matchup:
                    if st.button(
                        f"🏆 {info['name']}",
                        key=f"super_bowl_{code}",
                        use_container_width=True,
                    ):
                        st.session_state.super_bowl_winner = code
                        st.rerun()

            else:
                st.html(f"""
                    <div class="bracket-placeholder">
                        {conference} CHAMPION<br>
                        AWAITING WINNER
                    </div>
                """)

        if current_super_bowl_matchup:
            st.html("""
                <div style="
                    text-align:center;
                    color:#D8B86D;
                    font-size:24px;
                    font-weight:1000;
                    padding:10px;
                ">
                    VS
                </div>
            """)

    # ========================================================
    # AFC CHAMPIONSHIP
    # ========================================================

    with afc_champ_col:

        st.html('<div class="bracket-heading">AFC<br>CHAMPIONSHIP</div>')
        st.html('<div style="height:190px;"></div>')

        afc_div_winners = [
            afc_bracket.get("winners", {}).get(f"divisional_{i}")
            for i in range(2)
        ]

        if all(afc_div_winners):
            render_bracket_game(
                "AFC",
                afc_bracket,
                "championship",
                0,
                afc_div_winners[0],
                afc_div_winners[1],
                "AFC TITLE GAME",
            )
        else:
            for code in afc_div_winners:
                if code:
                    info = TEAMS[code]
                    seed = get_team_seed(afc_bracket, code)

                    st.html(f"""
                        <div style="
                            display:flex;
                            align-items:center;
                            gap:8px;
                            padding:9px;
                            margin-bottom:8px;
                            border-left:4px solid {info['color']};
                            background:{info['color']}22;
                            border-radius:5px;
                        ">
                            {logo(code, width=34)}
                            <span style="color:white;font-weight:800;">
                                #{seed} {info['name']}
                            </span>
                        </div>
                    """)
                else:
                    st.html("""
                        <div class="bracket-placeholder">
                            AWAITING DIVISIONAL WINNER
                        </div>
                    """)

        if afc_champion:
            st.success(f"AFC: {TEAMS[afc_champion]['name']}")


    # ========================================================
    # AFC DIVISIONAL
    # ========================================================

    with afc_div_col:

        st.html('<div class="bracket-heading">AFC<br>DIVISIONAL</div>')
        st.html('<div style="height:65px;"></div>')

        afc_wc_winners = [
            afc_bracket.get("winners", {}).get(f"wild_card_{i}")
            for i in range(3)
        ]

        if all(afc_wc_winners):
            divisional_matchups = afc_bracket["divisional"]
        else:
            available_teams = [
                afc_bracket["teams"].get(1),
                *[winner for winner in afc_wc_winners if winner],
            ]

            available_teams.sort(
                key=lambda code: next(
                    seed for seed, team in afc_bracket["teams"].items()
                    if team == code
                )
            )

            divisional_matchups = [
                (available_teams[0] if len(available_teams) > 0 else None,
                 available_teams[3] if len(available_teams) > 3 else None),
                (available_teams[1] if len(available_teams) > 1 else None,
                 available_teams[2] if len(available_teams) > 2 else None),
            ]

        for i, matchup in enumerate(divisional_matchups):
            render_bracket_game(
                "AFC",
                afc_bracket,
                "divisional",
                i,
                matchup[0],
                matchup[1],
                f"GAME {i + 1}",
            )

            if i == 0:
                st.html('<div style="height:85px;"></div>')

    # ========================================================
    # AFC WILD CARD — RIGHT EDGE
    # ========================================================

    with afc_wc_col:

        st.html('<div class="bracket-heading">AFC<br>WILD CARD</div>')

        for i, (seed_one, seed_two) in enumerate(
            afc_bracket["wild_card"]
        ):
            render_bracket_game(
                "AFC",
                afc_bracket,
                "wild_card",
                i,
                afc_bracket["teams"].get(seed_one),
                afc_bracket["teams"].get(seed_two),
                f"GAME {i + 1}",
            )

    # --------------------------------------------------------
    # SUPER BOWL CHAMPION CELEBRATION
    # --------------------------------------------------------

    winner = st.session_state.super_bowl_winner

    if winner and current_super_bowl_matchup:

        winner_name = TEAMS[winner]["name"]

        nfc_color = TEAMS[nfc_champion]["color"]
        afc_color = TEAMS[afc_champion]["color"]

        nfc_secondary = TEAMS[nfc_champion]["secondary"]
        afc_secondary = TEAMS[afc_champion]["secondary"]

        confetti_colors = [
            "#D8B86D",
            "#FFFFFF",
            "#E74C3C",
            "#4DA6FF",
            "#72D572",
        ]

        confetti = "".join(
            f"""
            <span class="sb-confetti" style="
                left:{(i * 37) % 100}%;
                background:{confetti_colors[i % len(confetti_colors)]};
                animation-delay:{-(i % 12) * 0.3}s;
                animation-duration:{3 + (i % 5) * 0.45}s;
            "></span>
            """
            for i in range(45)
        )

        st.html(f"""
            <style>
                                @keyframes sb-confetti-fall {{
                    0% {{
                        transform:translateY(-10vh) rotate(0deg);
                        opacity:1;
                    }}
                    100% {{
                        transform:translateY(110vh) rotate(720deg);
                        opacity:0;
                    }}
                }}

                @keyframes sb-celebration-dismiss {{
                    0%, 75% {{
                        opacity:1;
                        visibility:visible;
                    }}
                    100% {{
                        opacity:0;
                        visibility:hidden;
                    }}
                }}
                    100% {{
                        opacity:0;
                        max-height:0;
                        min-height:0;
                        padding:0;
                        margin:0;
                        border-width:0;
                    }}
                }}

                @keyframes sb-champion-glow {{
                    0%,100% {{
                        text-shadow:0 0 15px #D8B86D55;
                    }}
                    50% {{
                        text-shadow:0 0 35px #D8B86D;
                    }}
                }}

                .sb-celebration {{
                    position:fixed;
                    top:0;
                    left:0;
                    right:0;
                    bottom:0;
                    z-index:9999999;
                    overflow:hidden;
                    height:100vh;
                    width:100vw;    
                    max-width:none;
                    min-height:100vh;
                    box-sizing:border-box;
                    display:flex;
                    flex-direction:column;
                    align-items:center;
                    justify-content:center;
                    text-align:center;
                    padding:45px 15px;
                    margin:0;
                    border:2px solid #D8B86D;
                    border-radius:0;
                    background:
                        radial-gradient(
                            circle at 50% 30%,
                            {TEAMS[winner]["secondary"]} 0%,
                            {TEAMS[winner]["color"]} 55%,
                            #080808 100%
                        );
                        
                    animation:sb-celebration-dismiss 5s ease forwards;
                }}

                .sb-confetti {{
                    position:absolute;
                    top:-25px;
                    width:9px;
                    height:17px;
                    border-radius:20px;
                    animation:sb-confetti-fall linear infinite;
                    pointer-events:none;
                }}

                .sb-champion-title {{
                    color:#D8B86D;
                    font-size:clamp(28px,5vw,52px);
                    font-weight:1000;
                    letter-spacing:3px;
                    animation:sb-champion-glow 2s ease-in-out infinite;
                    margin:20px 0 10px;
                }}
            </style>

            <div class="sb-celebration">
                {confetti}

                <div style="
                    position:relative;
                    z-index:2;
                    font-size:15px;
                    color:#D8B86D;
                    font-weight:900;
                    letter-spacing:6px;
                ">
                    THE SEASON ENDS HERE
                </div>

                <div style="position:relative;z-index:2;margin:20px 0;">
                    {logo(winner, width=170)}
                </div>

                <div class="sb-champion-title"
                     style="position:relative;z-index:2;">
                    SUPER BOWL CHAMPIONS!
                </div>

                <div style="
                    position:relative;
                    z-index:2;
                    color:#F4F0E7;
                    font-size:22px;
                    font-weight:800;
                ">
                    Congratulations to the
                </div>

                <div style="
                    position:relative;
                    z-index:2;
                    color:#D8B86D;
                    font-size:30px;
                    font-weight:1000;
                    margin-top:10px;
                ">
                    {winner_name}!
                </div>

                <div style="
                    position:relative;
                    z-index:2;
                    color:#AAA69C;
                    font-size:12px;
                    letter-spacing:3px;
                    margin-top:25px;
                ">
                    YOUR SUPER BOWL WINNER
                </div>
            </div>
        """)

        if st.button(
            "↻ RESET SUPER BOWL",
            key="reset_super_bowl",
            use_container_width=True,
        ):
            st.session_state.super_bowl_winner = None
            st.rerun()

# ============================================================
# APP ROUTER
# ============================================================

header()
reset_page_scroll()

if rankings is None:
    st.error("The NFL ratings CSV is unavailable or missing required columns.")
    st.code(str(CSV_PATH), language="text")
else:
    current_page = st.session_state.page
    if current_page == "HOME":
        render_home()
    elif current_page == "TEAMS":
        render_teams()
    elif current_page == "PROFILE":
        render_profile()
    elif current_page == "RANKINGS":
        render_rankings()
    elif current_page == "WAR":
        render_war_room()
    elif current_page == "WEEKLY":
        render_weekly()
    elif current_page == "HISTORY":
        render_history()
    elif current_page == "REPORT":
        render_report()
    elif current_page == "METHOD":
        render_methodology()
    else:
        render_home()

footer()

# Save the first snapshot after the app is successfully assembled.
# Snapshot writes are content-fingerprint protected, so unchanged data is not duplicated.
if rankings is not None:
    save_snapshot(rankings)
