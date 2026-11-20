from pathlib import Path
from datetime import datetime
import hashlib
import html
import json
import urllib.request
import sys


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
CSV_PATH = BASE_DIR / "data" / "output" / "nfl_rankings_2026.csv"
HISTORY_DIR = BASE_DIR / "data" / "history"
HISTORY_PATH = HISTORY_DIR / "snapshots.json"

# ============================================================
# NFL PROJECT DATABASE CONNECTION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from NFL_Rankings.database import get_games

# ============================================================
# WEEKLY RESULTS + UPCOMING SCHEDULE STORAGE
# ============================================================

WEEKLY_DIR = BASE_DIR / "data" / "weekly"
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

    records = get_database_records(2026)

    rows = []

    for code, record in records.items():

        team_info = TEAMS[code]

        team_conference = team_info.get("conference", "")
        team_division = team_info.get("division", "")

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


def get_upcoming_games():

    games = get_games(2026, "scheduled")

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
        home = aliases.get(game["home_team"], game["home_team"])
        away = aliases.get(game["away_team"], game["away_team"])

        upcoming.append({
            "id": game["game_id"],
            "home": home,
            "away": away,
            "week": game["week"],
            "date": game["gameday"] or "",
            "kickoff": game["gametime"] or "",
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
    request = urllib.request.Request(
        ESPN_SCOREBOARD_URL,
        headers={"User-Agent": "Mozilla/5.0 NFL-Ratings-App"},
    )

    with urllib.request.urlopen(request, timeout=25) as response:
        payload = json.loads(response.read().decode("utf-8"))

    events = payload.get("events", [])
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
        competitors = competition.get("competitors", [])

        home = None
        away = None
        home_score = None
        away_score = None

        for competitor in competitors:
            team = competitor.get("team", {})
            code = team.get("abbreviation", "").upper()
            code = aliases.get(code, code)

            if code not in TEAMS:
                continue

            score = competitor.get("score")

            if competitor.get("homeAway") == "home":
                home = code
                home_score = score
            elif competitor.get("homeAway") == "away":
                away = code
                away_score = score

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


def get_team_row(code, data=None):
    source = rankings if data is None else data
    if source is None:
        return None
    found = source[source["team"] == code]
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
    """Use Streamlit's built-in HTML element; no component iframe is created."""
    if st.session_state.get("scroll_to_top", False):
        st.html(
            """
            <script>
            (() => {
                window.scrollTo(0, 0);
                document.documentElement.scrollTop = 0;
                document.body.scrollTop = 0;
                const main = document.querySelector("section.main");
                if (main) main.scrollTop = 0;
                const app = document.querySelector(
                    '[data-testid="stAppViewContainer"]'
                );
                if (app) app.scrollTop = 0;
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


def metric(label, value, suffix=""):
    st.markdown(
        f'<div class="metric-card"><div class="metric-label">{html.escape(str(label))}</div>'
        f'<div class="metric-number">{html.escape(str(value))}{suffix}</div></div>',
        unsafe_allow_html=True,
    )


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
                if st.button(label, key=f"nav_{page}", use_container_width=True):
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
        metric("TEAMS RATED", len(ordered))
        metric("LEAGUE AVERAGE", f'{ordered["overall_rating"].mean():.1f}')
        metric("TOP-TO-BOTTOM GAP", f'{ordered.iloc[0]["overall_rating"] - ordered.iloc[-1]["overall_rating"]:.1f}')

    section("THE TOP FIVE")
    for _, row in top.iterrows():
        rank_row(row, f"home_top_{row['team']}")

    section("THE BOTTOM FIVE")
    for _, row in bottom.iterrows():
        rank_row(row, f"home_bottom_{row['team']}")

    section("CURRENT LEAGUE STANDINGS")

    standings = get_standings()

    standings_display = standings[
        ["Team", "W", "L", "T", "PCT", "DIFF"]
    ].head(8).copy()

    standings_display["PCT"] = standings_display["PCT"].map(
        lambda value: f"{value:.3f}"
    )

    st.dataframe(
        standings_display,
        use_container_width=True,
        hide_index=True,
    )

    section("NEXT UP")

    upcoming = get_upcoming_games()

    if not upcoming:
        st.info("No upcoming games have been added yet. Visit WEEKLY to manage the schedule.")
    else:
        for game in upcoming[:3]:
            home = game["home"]
            away = game["away"]

            st.markdown(
                f'<div class="panel">'
                f'<div class="micro">WEEK {game.get("week", "?")} '
                f'/ {html.escape(game.get("date", ""))} '
                f'/ {html.escape(game.get("kickoff", ""))}</div>'
                f'<div style="display:flex;align-items:center;justify-content:space-around;'
                f'gap:15px;flex-wrap:wrap;text-align:center">'
                f'<div>{logo(away,60)}<b>{html.escape(TEAMS[away]["name"])}</b></div>'
                f'<div class="metric-number" style="font-size:35px">AT</div>'
                f'<div>{logo(home,60)}<b>{html.escape(TEAMS[home]["name"])}</b></div>'
                f'</div></div>',
                unsafe_allow_html=True,
            )
    section("AROUND THE LEAGUE")
    award_specs = [
        ("TOP-RATED OFFENSE", "offensive_rating"),
        ("TOP-RATED DEFENSE", "defensive_rating"),
        ("TOP SPECIAL TEAMS", "special_teams_rating"),
        ("TOP DISCIPLINE", "discipline_rating"),
    ]
    cols = st.columns(4)
    for col, (label, rating_col) in zip(cols, award_specs):
        row = rankings.loc[rankings[rating_col].idxmax()]
        code = str(row["team"])
        with col:
            st.markdown(
                f'<div class="panel" style="text-align:center">{logo(code,72)}'
                f'<div class="micro">{label}</div><b>{html.escape(TEAMS[code]["name"])}</b>'
                f'<div class="metric-number">{float(row[rating_col]):.1f}</div></div>',
                unsafe_allow_html=True,
            )
            if st.button(f"VIEW {code}", key=f"award_{label}"):
                go("PROFILE", code, True)

    st.caption("League spotlights are calculated from the current ratings file. They are not claims about on-field weekly results.")


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

# ============================================================
# TEAM PROFILE
# ============================================================

def render_profile():
    code = st.session_state.selected_team
    if code not in TEAMS:
        st.warning("Choose a team first.")
        go("TEAMS")
        return

    row = get_team_row(code)
    if row is None:
        st.error(f"No ratings found for {code} in the CSV.")
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
    # Current record is calculated from saved weekly game results.
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

    section("HOW THIS TEAM STACKS UP")
    compare = pd.DataFrame({
        "Category": [item[0] for item in CATEGORIES],
        "Team": [float(row[item[1]]) for item in CATEGORIES],
        "League average": [float(rankings[item[1]].mean()) for item in CATEGORIES],
    }).set_index("Category")
    st.bar_chart(compare, height=300)

    section("NEAREST RATING NEIGHBORS")
    neighbors = rankings.assign(gap=(rankings["overall_rating"] - overall).abs())
    neighbors = neighbors[neighbors["team"] != code].nsmallest(3, "gap")
    for _, near in neighbors.iterrows():
        rank_row(near, f"neighbor_{code}_{near['team']}")

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

    f1, f2, f3 = st.columns([2, 1, 1])
    with f1:
        search = st.text_input("SEARCH TEAM", placeholder="Type a team name or abbreviation...")
    with f2:
        conference = st.selectbox("CONFERENCE", ["ALL", "AFC", "NFC"])
    with f3:
        division = st.selectbox("DIVISION", ["ALL", "East", "North", "South", "West"])

    data = rankings.copy()
    data["conference"] = data["team"].map(lambda code: TEAMS.get(code, {}).get("conf", ""))
    data["division"] = data["team"].map(lambda code: TEAMS.get(code, {}).get("div", ""))
    data["team_name"] = data["team"].map(lambda code: TEAMS.get(code, {}).get("name", code))
    if conference != "ALL":
        data = data[data["conference"] == conference]
    if division != "ALL":
        data = data[data["division"] == division]
    if search.strip():
        needle = search.strip().lower()
        data = data[
            data.apply(
                lambda row: needle in row["team"].lower()
                or needle in row["team_name"].lower(),
                axis=1,
            )
        ]

    section(f"RANKED TEAMS / {len(data)} RESULTS")
    if data.empty:
        st.info("No teams match those filters.")
        return

    for _, row in data.sort_values("rank").iterrows():
        rating = float(row["overall_rating"])
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
            f'<div class="rank-num">#{int(row["rank"]):02d}</div>{logo(code,56)}'
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

def get_database_records(season=2026):

    games = get_games(season, "final")

    records = {
        code: {
            "W": 0,
            "L": 0,
            "T": 0,
            "PF": 0,
            "PA": 0,
        }
        for code in TEAMS
    }

    for game in games:

        aliases = {
            "LA": "LAR",
            "JAC": "JAX",
            "WSH": "WAS",
            "WFT": "WAS",
            "OAK": "LV",
            "SD": "LAC",
            "STL": "LAR",
        }

        home = aliases.get(game["home_team"], game["home_team"])
        away = aliases.get(game["away_team"], game["away_team"])

        if home not in records or away not in records:
            continue

        home_score = game["home_score"]
        away_score = game["away_score"]

        if home_score is None or away_score is None:
            continue

        home_score = int(home_score)
        away_score = int(away_score)

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

    for code, record in records.items():

        games_played = (
            record["W"] + record["L"] + record["T"]
        )

        record["PCT"] = (
            (record["W"] + record["T"] * 0.5) / games_played
            if games_played else 0.0
        )

        record["DIFF"] = record["PF"] - record["PA"]

    return records


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
    # LEAGUE STANDINGS
    # --------------------------------------------------------

    section("LEAGUE STANDINGS")

    conference_filter = st.selectbox(
        "VIEW STANDINGS",
        ["ALL", "AFC", "NFC"],
        key="weekly_standings_filter",
    )

    standings = get_standings(
        conference=None if conference_filter == "ALL"
        else conference_filter
    )

    display = standings[
        ["Team", "W", "L", "T", "PCT", "PF", "PA", "DIFF"]
    ].copy()

    display["PCT"] = display["PCT"].map(
        lambda value: f"{value:.3f}"
    )

    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
    )

    # --------------------------------------------------------
    # RECORDS BY DIVISION
    # --------------------------------------------------------

    section("RECORDS BY DIVISION")

    division_options = [
        ("AFC", "East"),
        ("AFC", "North"),
        ("AFC", "South"),
        ("AFC", "West"),
        ("NFC", "East"),
        ("NFC", "North"),
        ("NFC", "South"),
        ("NFC", "West"),
    ]

    division_cols = st.columns(4)

    for index, (conference, division) in enumerate(division_options):

        with division_cols[index % 4]:

            st.markdown(
                f'<div class="panel">'
                f'<div class="micro">{conference} {division.upper()}</div>',
                unsafe_allow_html=True,
            )

            division_data = get_standings(
                conference=conference,
                division=division,
            )

            for _, team in division_data.iterrows():

                st.markdown(
                    f'**{team["Code"]}** '
                    f'{int(team["W"])}-{int(team["L"])}-{int(team["T"])}'
                    f'<span style="color:#B99A5A"> '
                    f'{team["PCT"]:.3f}</span>',
                    unsafe_allow_html=True,
                )

            st.markdown("</div>", unsafe_allow_html=True)

    # --------------------------------------------------------
    # TEAM OPTIONS
    # --------------------------------------------------------

    team_codes = sorted(
        TEAMS.keys(),
        key=lambda code: TEAMS[code]["name"]
    )

    # --------------------------------------------------------
    # ENTER COMPLETED GAME
    # --------------------------------------------------------

    section("ENTER A COMPLETED GAME")

    with st.form("weekly_result_form"):

        st.markdown("**GAME INFORMATION**")

        result_week = st.number_input(
            "WEEK",
            min_value=1,
            max_value=30,
            value=1,
            step=1,
            key="result_week",
        )

        result_date = st.date_input(
            "GAME DATE",
            key="result_date",
        )

        result_home = st.selectbox(
            "HOME TEAM",
            team_codes,
            format_func=lambda code: TEAMS[code]["name"],
            key="result_home",
        )

        result_away = st.selectbox(
            "AWAY TEAM",
            team_codes,
            index=1,
            format_func=lambda code: TEAMS[code]["name"],
            key="result_away",
        )

        score_home, score_away = st.columns(2)

        with score_home:
            home_score = st.number_input(
                "HOME SCORE",
                min_value=0,
                max_value=200,
                value=0,
                step=1,
                key="result_home_score",
            )

        with score_away:
            away_score = st.number_input(
                "AWAY SCORE",
                min_value=0,
                max_value=200,
                value=0,
                step=1,
                key="result_away_score",
            )

        save_result = st.form_submit_button(
            "SAVE GAME RESULT",
            use_container_width=True,
        )

    if save_result:

        if result_home == result_away:
            st.error("A team cannot play against itself.")

        else:
            results = get_results()

            duplicate = any(
                int(game.get("week", -1)) == int(result_week)
                and game.get("home") == result_home
                and game.get("away") == result_away
                for game in results
            )

            if duplicate:
                st.error("That game has already been entered.")

            else:
                matching_schedule = next(
                    (
                        game for game in get_schedule()
                        if int(game.get("week", -1)) == int(result_week)
                        and game.get("home") == result_home
                        and game.get("away") == result_away
                    ),
                    None,
                )

                game_id = hashlib.sha256(
                    (
                        f"{result_week}-{result_date.isoformat()}-"
                        f"{result_home}-{result_away}-{datetime.now().isoformat()}"
                    ).encode("utf-8")
                ).hexdigest()[:16]

                new_result = {
                    "id": game_id,
                    "week": int(result_week),
                    "date": result_date.isoformat(),
                    "home": result_home,
                    "away": result_away,
                    "home_score": int(home_score),
                    "away_score": int(away_score),
                }

                if matching_schedule:
                    new_result["schedule_id"] = matching_schedule.get("id")

                results.append(new_result)

                write_json_list(RESULTS_PATH, results)

                st.success(
                    f"Result saved: {result_away} "
                    f"{int(away_score)} - {int(home_score)} "
                    f"{result_home}"
                )

                st.rerun()

    # --------------------------------------------------------
    # ADD UPCOMING GAME
    # --------------------------------------------------------

    section("ADD AN UPCOMING GAME")

    with st.form("weekly_schedule_form"):

        st.markdown("**SCHEDULE INFORMATION**")

        schedule_week = st.number_input(
            "SCHEDULE WEEK",
            min_value=1,
            max_value=30,
            value=1,
            step=1,
            key="schedule_week",
        )

        schedule_date = st.date_input(
            "SCHEDULE DATE",
            key="schedule_date",
        )

        kickoff = st.text_input(
            "KICKOFF TIME",
            placeholder="Example: 1:00 PM ET",
            key="schedule_kickoff",
        )

        schedule_home = st.selectbox(
            "SCHEDULE HOME TEAM",
            team_codes,
            format_func=lambda code: TEAMS[code]["name"],
            key="schedule_home",
        )

        schedule_away = st.selectbox(
            "SCHEDULE AWAY TEAM",
            team_codes,
            index=1,
            format_func=lambda code: TEAMS[code]["name"],
            key="schedule_away",
        )

        save_schedule = st.form_submit_button(
            "ADD TO UPCOMING SCHEDULE",
            use_container_width=True,
        )

    if save_schedule:

        if schedule_home == schedule_away:
            st.error("A team cannot play against itself.")

        else:
            schedule = get_schedule()

            duplicate = any(
                int(game.get("week", -1)) == int(schedule_week)
                and game.get("home") == schedule_home
                and game.get("away") == schedule_away
                for game in schedule
            )

            if duplicate:
                st.error("That matchup is already on the schedule.")

            else:
                schedule_id = hashlib.sha256(
                    (
                        f"{schedule_week}-{schedule_date.isoformat()}-"
                        f"{schedule_home}-{schedule_away}-{datetime.now().isoformat()}"
                    ).encode("utf-8")
                ).hexdigest()[:16]

                schedule.append({
                    "id": schedule_id,
                    "week": int(schedule_week),
                    "date": schedule_date.isoformat(),
                    "kickoff": kickoff.strip() or "TBD",
                    "home": schedule_home,
                    "away": schedule_away,
                })

                write_json_list(SCHEDULE_PATH, schedule)

                st.success("Upcoming game added successfully.")
                st.rerun()

    # --------------------------------------------------------
    # UPCOMING GAMES
    # --------------------------------------------------------

    section("UPCOMING GAMES")

    upcoming = get_upcoming_games()

    if not upcoming:

        st.info(
            "There are currently no upcoming games in your schedule."
        )

    else:

        for game in upcoming:

            home = game.get("home")
            away = game.get("away")

            if home not in TEAMS or away not in TEAMS:
                continue

            st.markdown(
                f'<div class="panel">'
                f'<div class="micro">WEEK {game.get("week", "?")} '
                f'/ {html.escape(game.get("date", ""))} '
                f'/ {html.escape(game.get("kickoff", "TBD"))}</div>'
                f'<div style="display:flex;align-items:center;'
                f'justify-content:space-around;gap:15px;'
                f'flex-wrap:wrap;text-align:center">'
                f'<div>{logo(away,65)}<br>'
                f'<b>{html.escape(TEAMS[away]["name"])}</b></div>'
                f'<div class="metric-number" style="font-size:36px">AT</div>'
                f'<div>{logo(home,65)}<br>'
                f'<b>{html.escape(TEAMS[home]["name"])}</b></div>'
                f'</div></div>',
                unsafe_allow_html=True,
            )

    # --------------------------------------------------------
    # COMPLETED GAME RESULTS
    # --------------------------------------------------------

    section("COMPLETED GAME RESULTS")

    results = sorted(
        get_results(),
        key=lambda game: (
            int(game.get("week", 0)),
            game.get("date", ""),
        ),
        reverse=True,
    )

    if not results:

        st.info("No completed games have been entered yet.")

    else:

        result_rows = []

        for game in results:

            home = game.get("home")
            away = game.get("away")

            if home not in TEAMS or away not in TEAMS:
                continue

            result_rows.append({
                "Week": game.get("week", "?"),
                "Date": game.get("date", ""),
                "Away Team": TEAMS[away]["name"],
                "Away": game.get("away_score", 0),
                "Home": game.get("home_score", 0),
                "Home Team": TEAMS[home]["name"],
            })

        if result_rows:

            st.dataframe(
                pd.DataFrame(result_rows),
                use_container_width=True,
                hide_index=True,
            )

    # --------------------------------------------------------
    # FOOTNOTE
    # --------------------------------------------------------

    st.caption(
        "Team records are calculated from the completed games saved here. "
        "Entering results does not change the ratings CSV or the ratings formula."
    )

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
