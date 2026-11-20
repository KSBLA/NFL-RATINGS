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
                            logo(code, 48),
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
