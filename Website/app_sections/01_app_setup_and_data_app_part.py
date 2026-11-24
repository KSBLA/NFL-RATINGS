from pathlib import Path
from datetime import datetime, date, timedelta
from weekly_report import render_report
from rankings_page import render_rankings
from game_themes import GAME_THEMES, get_game_presentation
from team_data import (
    calculate_team_records,
    calculate_team_momentum,
    format_team_record,
    build_standings,
)
from weekly_data import (
    load_weekly_team_stats,
    load_play_by_play,
    load_weekly_award_play_by_play,
    load_weekly_rosters,
    get_latest_completed_week as find_latest_completed_week,
    get_player_leaders as build_player_leaders,
    build_player_highlights as calculate_player_highlights,
)
from weekly_storage import (
    WEEKLY_DIR,
    RESULTS_PATH,
    SCHEDULE_PATH,
    read_json_list,
    write_json_list,
    get_results,
    get_schedule,
)

import hashlib
import html
import json
import urllib.request
import sys
import math
import textwrap

import pandas as pd
import streamlit as st

try:
    import polars as pl
except ImportError:
    pl = None

from importlib.util import spec_from_file_location, module_from_spec

_STORYLINES_MODULE_PATH = Path(__file__).resolve().parent / "team_profile_storylines.py"
_STORYLINES_SPEC = spec_from_file_location(
    "_nfl_team_profile_storylines",
    _STORYLINES_MODULE_PATH,
)
if _STORYLINES_SPEC is None or _STORYLINES_SPEC.loader is None:
    raise ImportError(f"Unable to load storyline module: {_STORYLINES_MODULE_PATH}")
_STORYLINES_MODULE = module_from_spec(_STORYLINES_SPEC)
_STORYLINES_SPEC.loader.exec_module(_STORYLINES_MODULE)
build_team_profile_storylines = _STORYLINES_MODULE.build_team_profile_storylines

_LEADERSHIP_MODULE_PATH = Path(__file__).resolve().parent / "team_profile_leadership.py"
_LEADERSHIP_SPEC = spec_from_file_location("_nfl_team_profile_leadership", _LEADERSHIP_MODULE_PATH)
if _LEADERSHIP_SPEC is None or _LEADERSHIP_SPEC.loader is None:
    raise ImportError(f"Unable to load leadership module: {_LEADERSHIP_MODULE_PATH}")
_LEADERSHIP_MODULE = module_from_spec(_LEADERSHIP_SPEC)
_LEADERSHIP_SPEC.loader.exec_module(_LEADERSHIP_MODULE)
render_team_profile_leadership = _LEADERSHIP_MODULE.render_team_profile_leadership



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
CACHE_DIR = BASE_DIR / "Data" / "cache"

# ============================================================
# NFL PROJECT DATABASE CONNECTION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from NFL_Rankings.grade_scale import grade_label

# ============================================================
# WEEKLY RESULTS + UPCOMING SCHEDULE STORAGE
# ============================================================


@st.cache_data
def load_team_metrics():
    if not METRICS_PATH.exists():
        return pd.DataFrame()

    try:
        return pd.read_csv(METRICS_PATH)
    except (OSError, pd.errors.ParserError):
        return pd.DataFrame()



def get_weekly_team_stats():
    path = CACHE_DIR / f"team_stats_{NFL_SEASON}.parquet"
    if not path.exists():
        return pd.DataFrame()
    return load_weekly_team_stats(str(path), path.stat().st_mtime)


def get_play_by_play():
    path = CACHE_DIR / f"play_by_play_{NFL_SEASON}.parquet"
    if not path.exists():
        return pd.DataFrame()
    return load_play_by_play(str(path), path.stat().st_mtime)



def get_weekly_rosters():
    return load_weekly_rosters(CACHE_DIR, NFL_SEASON)

def get_latest_completed_week():
    return find_latest_completed_week(get_results)

def get_team_week_row(team_code, week, stats=None):
    stats = get_weekly_team_stats() if stats is None else stats
    if stats.empty or not {"team", "week"}.issubset(stats.columns):
        return None
    stats_aliases = {"LAR": {"LAR", "LA"}}
    accepted_codes = stats_aliases.get(team_code, {team_code})
    rows = stats[
        (stats["team"].astype(str).str.upper().isin(accepted_codes))
        & (pd.to_numeric(stats["week"], errors="coerce") == int(week))
    ]
    if rows.empty:
        return None
    # nflreadpy's weekly team-stat cache is one row per team/game.
    return rows.iloc[0].to_dict()


def get_player_leaders(team_code, week=None):
    return build_player_leaders(
        team_code,
        get_play_by_play(),
        week=week,
    )

def build_player_highlights(team_code, opponent_code):
    return calculate_player_highlights(
        team_code,
        opponent_code,
        get_play_by_play(),
        get_weekly_rosters(),
        get_latest_completed_week(),
    )


def get_records():
    return calculate_team_records(TEAMS, get_results())


def get_team_momentum(code, recent_games=5):
    return calculate_team_momentum(
        code,
        get_results(),
        recent_games,
    )


def format_record(code):
    return format_team_record(code, get_records())


def get_standings(conference=None, division=None):
    return build_standings(
        TEAMS,
        get_records(),
        conference,
        division,
    )



def evaluate_matchup_storyline(
        away_team,
        home_team,
        is_division_game,
        is_conference_game,
):
    """Select the strongest applicable overall matchup storyline."""

    away_name = away_team["name"]
    home_name = home_team["name"]

    away_pct = away_team["win_percentage"]
    home_pct = home_team["win_percentage"]

    away_position = away_team.get("division_position")
    home_position = home_team.get("division_position")

    if not isinstance(away_position, int) or away_position < 1:
        away_position = None

    if not isinstance(home_position, int) or home_position < 1:
        home_position = None

    away_status = away_team["playoff_status"]
    home_status = home_team["playoff_status"]

    away_seed = away_status.startswith("SEED")
    home_seed = home_status.startswith("SEED")

    away_hunt = away_status == "IN THE HUNT"
    home_hunt = home_status == "IN THE HUNT"

    away_winning = away_pct > 0.500
    home_winning = home_pct > 0.500

    away_struggling = away_pct <= 0.400
    home_struggling = home_pct <= 0.400

    gap = abs(away_pct - home_pct)

    candidates = []

    def add(score, headline, description):
        candidates.append({
            "score": score,
            "headline": headline,
            "description": description,
        })

    # --------------------------------------------------
    # 1. DIVISION RACES AND RIVALRIES
    # --------------------------------------------------

    if (
            is_division_game
            and away_position is not None
            and home_position is not None
    ):
        if (
                away_position <= 2
                and home_position <= 2
                and gap <= 0.118
        ):
            add(
                100,
                "DIVISION RACE HEATS UP",
                f"{away_name} and {home_name} are both among "
                "the top two teams in their division. This "
                "head-to-head matchup could significantly "
                "influence the division race."
            )

        if (
                (away_position == 1 and home_position >= 2)
                or (home_position == 1 and away_position >= 2)
        ):
            leader = away_name if away_position == 1 else home_name
            challenger = home_name if away_position == 1 else away_name

            add(
                90,
                "DIVISION LEADER UNDER PRESSURE",
                f"{leader} currently leads the division, while "
                f"{challenger} has an opportunity to close "
                "the gap with a divisional victory."
            )

        if (
                away_position == 2 and home_position == 1
                or home_position == 2 and away_position == 1
        ):
            challenger = away_name if away_position == 2 else home_name

            add(
                92,
                "CHASING THE DIVISION LEAD",
                f"{challenger} has an opportunity to gain ground "
                "on the division leader with a head-to-head win."
            )

        if away_winning and home_winning:
            add(
                85,
                "DIVISIONAL WINNING RECORDS COLLIDE",
                f"Both {away_name} and {home_name} enter this "
                "divisional matchup with winning records. "
                "A victory offers an opportunity to gain ground "
                "on a division rival."
            )

        if away_struggling and home_struggling:
            add(
                75,
                "DIVISIONAL BATTLE FOR A TURNAROUND",
                f"Both {away_name} and {home_name} have struggled "
                "to build winning records. A divisional victory "
                "would provide an opportunity to turn things around."
            )

    # --------------------------------------------------
    # 2. PLAYOFF RACES AND POSTSEASON PRESSURE
    # --------------------------------------------------

    if away_seed and home_seed:
        add(
            98,
            "PLAYOFF POSITIONING BATTLE",
            f"Both {away_name} and {home_name} currently occupy "
            "playoff positions. A victory could help strengthen "
            "their postseason standing."
        )

    if (away_seed and home_hunt) or (home_seed and away_hunt):
        playoff_team = away_name if away_seed else home_name
        challenger = home_name if away_seed else away_name

        add(
            96,
            "PLAYOFF SPOT IN SIGHT",
            f"{playoff_team} currently holds a playoff position, "
            f"while {challenger} remains in the hunt. "
            "The result could influence the postseason picture."
        )

    if away_hunt and home_hunt:
        add(
            97,
            "POSTSEASON HOPES COLLIDE",
            f"Both {away_name} and {home_name} remain in the "
            "hunt for a playoff position. A victory could "
            "provide a valuable boost in the postseason race."
        )

    if away_hunt or home_hunt:
        team = away_name if away_hunt else home_name

        add(
            82,
            "KEEPING THE PLAYOFF PUSH ALIVE",
            f"{team} remains in the playoff hunt and has an "
            "opportunity to strengthen its position with "
            "another important result."
        )

    if away_seed or home_seed:
        team = away_name if away_seed else home_name
        opponent = home_name if away_seed else away_name

        add(
            80,
            "A TEST FOR A PLAYOFF CONTENDER",
            f"{team} currently occupies a playoff position "
            f"and faces {opponent} in an opportunity to "
            "strengthen its postseason standing."
        )

    # --------------------------------------------------
    # 3. CONFERENCE STANDINGS
    # --------------------------------------------------

    if is_conference_game:
        if away_winning and home_winning:
            add(
                88,
                "CONFERENCE WINNING RECORDS COLLIDE",
                f"Both {away_name} and {home_name} enter this "
                "conference matchup with winning records. "
                "A victory would strengthen their conference results."
            )

        if away_hunt or home_hunt:
            add(
                86,
                "CONFERENCE PLAYOFF PUSH",
                "This conference matchup gives teams competing "
                "for postseason positioning an opportunity "
                "to influence the playoff picture."
            )

        if away_pct >= 0.650 and home_pct >= 0.650:
            add(
                94,
                "CONFERENCE CONTENDERS COLLIDE",
                f"{away_name} and {home_name} have both "
                "established themselves with strong records. "
                "This matchup provides a significant test."
            )

        if away_struggling and home_struggling:
            add(
                70,
                "CONFERENCE BATTLE FOR RESPECT",
                f"{away_name} and {home_name} are both looking "
                "to improve their conference records and "
                "establish greater consistency."
            )

        if gap <= 0.100:
            add(
                78,
                "A CLOSE CONFERENCE MATCHUP",
                f"{away_name} and {home_name} enter this matchup "
                "with closely matched winning percentages. "
                "A victory offers an opportunity to gain "
                "ground within the conference."
            )

    # --------------------------------------------------
    # 4. CONTENDER MATCHUPS
    # --------------------------------------------------

    if away_pct >= 0.650 and home_pct >= 0.650:
        add(
            93,
            "CONTENDERS COLLIDE",
            f"{away_name} and {home_name} have both put together "
            "strong seasons. This matchup provides an important "
            "test against another successful team."
        )

    if away_pct >= 0.600 and home_pct >= 0.600:
        add(
            87,
            "A SHOWDOWN BETWEEN WINNING TEAMS",
            f"Both {away_name} and {home_name} have established "
            "winning records. Each team has an opportunity "
            "to strengthen its position with a quality victory."
        )

    if away_winning != home_winning:
        winning_team = away_name if away_winning else home_name
        other_team = home_name if away_winning else away_name

        add(
            76,
            "CONTRASTING SEASONS",
            f"{winning_team} enters with a winning record, "
            f"while {other_team} looks to improve its season "
            "with a statement performance."
        )

    if away_pct >= 0.650 or home_pct >= 0.650:
        strong_team = away_name if away_pct >= 0.650 else home_name
        opponent = home_name if away_pct >= 0.650 else away_name

        add(
            84,
            "A TEST AGAINST A TOP OPPONENT",
            f"{opponent} faces {strong_team}, a team that "
            "has established itself with a strong winning record."
        )

    if gap <= 0.050:
        add(
            82,
            "A MATCHUP BETWEEN EVENLY MATCHED TEAMS",
            f"{away_name} and {home_name} enter this game "
            "with nearly identical winning percentages, "
            "setting up a closely matched contest."
        )

    # 5. RECORD-BASED MATCHUPS
    away_games = away_team["wins"] + away_team["losses"] + away_team["ties"]
    home_games = home_team["wins"] + home_team["losses"] + home_team["ties"]

    away_next_win_pct = (away_team["wins"] + away_team["ties"] * 0.5 + 1) / (away_games + 1)
    home_next_win_pct = (home_team["wins"] + home_team["ties"] * 0.5 + 1) / (home_games + 1)

    if away_pct < 0.500 <= away_next_win_pct:
        add(
            73,
            "A CHANCE TO REACH .500",
            f"{away_name} can reach a .500 winning percentage with a victory in this matchup."
        )

    if (0.500 <= away_pct <= 0.550 or 0.500 <= home_pct <= 0.550):
        team = away_name if away_pct <= home_pct else home_name
        add(72, "LOOKING TO BUILD A WINNING RECORD",
            f"{team} is hovering near the .500 mark and has an opportunity to establish a stronger winning record.")
    if home_pct < 0.500 <= home_next_win_pct:
        add(
            73,
            "A CHANCE TO REACH .500",
            f"{home_name} can reach a .500 winning percentage with a victory in this matchup."
        )

    # --------------------------------------------------
    # 6. PERFORMANCE AND STATISTICAL MATCHUPS
    # --------------------------------------------------

    away_rating = away_team.get("ratings", {}).get("overall_rating")
    home_rating = home_team.get("ratings", {}).get("overall_rating")

    try:
        away_rating = float(away_rating)
    except (TypeError, ValueError):
        away_rating = None

    try:
        home_rating = float(home_rating)
    except (TypeError, ValueError):
        home_rating = None

    if away_rating is not None and not math.isfinite(away_rating):
        away_rating = None

    if home_rating is not None and not math.isfinite(home_rating):
        home_rating = None
    if away_rating is not None and home_rating is not None:
        rating_gap = abs(float(away_rating) - float(home_rating))

        if rating_gap <= 3:
            add(
                89,
                "A MATCHUP OF EVENLY RATED TEAMS",
                f"{away_name} and {home_name} have closely "
                "matched overall ratings, setting up a "
                "competitive matchup on paper."
            )

        if rating_gap >= 12:
            stronger = away_name if away_rating > home_rating else home_name
            other = home_name if away_rating > home_rating else away_name

            add(
                77,
                "A TEST OF TEAM STRENGTH",
                f"{other} faces {stronger}, whose overall rating "
                "indicates a considerable difference in "
                "measured team strength."
            )

    if away_rating is not None and home_rating is not None:
        if (
                float(away_rating) > float(home_rating)
                and away_pct < home_pct
        ) or (
                float(home_rating) > float(away_rating)
                and home_pct < away_pct
        ):
            stronger_rating = (
                away_name if away_rating > home_rating else home_name
            )
            better_record = (
                home_name if away_rating > home_rating else away_name
            )

            add(
                91,
                "THE RATINGS TELL A DIFFERENT STORY",
                f"{stronger_rating} holds the higher overall "
                f"rating, while {better_record} has the better "
                "record. This matchup puts those contrasting "
                "indicators to the test."
            )

    # --------------------------------------------------
    # 7. MOMENTUM AND RECENT FORM
    # --------------------------------------------------

    away_momentum = away_team.get("momentum", {})
    home_momentum = home_team.get("momentum", {})

    away_streak = away_momentum.get("streak_length", 0)
    home_streak = home_momentum.get("streak_length", 0)

    away_streak_type = away_momentum.get("streak_type")
    home_streak_type = home_momentum.get("streak_type")

    if (
            away_streak_type == "W"
            and away_streak >= 3
            and home_streak_type == "W"
            and home_streak >= 3
    ):
        add(
            95,
            "WINNING STREAKS COLLIDE",
            f"Both {away_name} and {home_name} enter this "
            "matchup riding winning streaks. One team's "
            "run will face a serious test."
        )

    if away_streak_type == "W" and away_streak >= 3:
        add(
            83,
            "LOOKING TO KEEP THE WINNING STREAK ALIVE",
            f"{away_name} enters this matchup on a "
            f"{away_streak}-game winning streak and looks "
            "to keep its run going."
        )

    if home_streak_type == "W" and home_streak >= 3:
        add(
            83,
            "LOOKING TO KEEP THE WINNING STREAK ALIVE",
            f"{home_name} enters this matchup on a "
            f"{home_streak}-game winning streak and looks "
            "to keep its run going."
        )

    if away_streak_type == "L" and away_streak >= 3:
        add(
            81,
            "A LOSING STREAK MUST END",
            f"{away_name} enters this matchup on a "
            f"{away_streak}-game losing streak and needs "
            "to find a way to turn things around."
        )

    if home_streak_type == "L" and home_streak >= 3:
        add(
            81,
            "A LOSING STREAK MUST END",
            f"{home_name} enters this matchup on a "
            f"{home_streak}-game losing streak and needs "
            "to find a way to turn things around."
        )

    if (
            away_streak_type == "W"
            and home_streak_type == "L"
    ) or (
            home_streak_type == "W"
            and away_streak_type == "L"
    ):
        winning_team = away_name if away_streak_type == "W" else home_name
        losing_team = home_name if away_streak_type == "W" else away_name

        add(
            80,
            "CONTRASTING MOMENTUM",
            f"{winning_team} enters with a winning streak, "
            f"while {losing_team} is looking to stop a losing run."
        )

    # --------------------------------------------------
    # 8. UNDERDOGS AND SPOILER OPPORTUNITIES
    # --------------------------------------------------

    if (
            away_pct < home_pct
            and away_rating is not None
            and home_rating is not None
            and float(away_rating) > float(home_rating)
    ) or (
            home_pct < away_pct
            and away_rating is not None
            and home_rating is not None
            and float(home_rating) > float(away_rating)
    ):
        underdog = away_name if away_pct < home_pct else home_name

        add(
            90,
            "AN UNDERDOG WITH SOMETHING TO PROVE",
            f"{underdog} has the opportunity to show that "
            "its record does not tell the entire story "
            "against this opponent."
        )

    if away_hunt and home_struggling:
        add(
            79,
            "A SPOILER OPPORTUNITY",
            f"{home_name} can make life more difficult for "
            f"{away_name} as the playoff race continues."
        )

    if home_hunt and away_struggling:
        add(
            79,
            "A SPOILER OPPORTUNITY",
            f"{away_name} can make life more difficult for "
            f"{home_name} as the playoff race continues."
        )

    if away_seed and home_struggling:
        add(
            74,
            "A CHANCE TO PLAY SPOILER",
            f"{home_name} has an opportunity to disrupt "
            f"{away_name}'s postseason push with an upset."
        )

    if home_seed and away_struggling:
        add(
            74,
            "A CHANCE TO PLAY SPOILER",
            f"{away_name} has an opportunity to disrupt "
            f"{home_name}'s postseason push with an upset."
        )

    # --------------------------------------------------
    # FINAL SELECTION
    # --------------------------------------------------

    if candidates:
        selected = max(
            candidates,
            key=lambda candidate: candidate["score"],
        )

        return {
            "headline": selected["headline"],
            "description": selected["description"],
        }

    # General fallback
    if is_division_game:
        return {
            "headline": "DIVISIONAL MATCHUP",
            "description": (
                f"{away_name} and {home_name} meet in a "
                "divisional matchup, giving both teams "
                "an opportunity to improve their standing."
            ),
        }

    if is_conference_game:
        return {
            "headline": "CONFERENCE MATCHUP",
            "description": (
                f"{away_name} and {home_name} meet in a "
                "conference matchup, with an opportunity "
                "to strengthen their overall records."
            ),
        }

    return {
        "headline": "INTERCONFERENCE MATCHUP",
        "description": (
            f"{away_name} faces {home_name} in an "
            "interconference matchup. Both teams have "
            "an opportunity to improve their overall record."
        ),
    }


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
    "ARI": {"name": "Arizona Cardinals", "color": "#97233F", "secondary": "#FFB612", "effect": "fire", "conf": "NFC",
            "div": "West"},
    "ATL": {"name": "Atlanta Falcons", "color": "#A71930", "secondary": "#000000", "effect": "fire", "conf": "NFC",
            "div": "South"},
    "BAL": {"name": "Baltimore Ravens", "color": "#241773", "secondary": "#9E7C0C", "effect": "lightning",
            "conf": "AFC", "div": "North"},
    "BUF": {"name": "Buffalo Bills", "color": "#00338D", "secondary": "#C60C30", "effect": "storm", "conf": "AFC",
            "div": "East"},
    "CAR": {"name": "Carolina Panthers", "color": "#0085CA", "secondary": "#101820", "effect": "lightning",
            "conf": "NFC", "div": "South"},
    "CHI": {"name": "Chicago Bears", "color": "#0B162A", "secondary": "#C83803", "effect": "storm", "conf": "NFC",
            "div": "North"},
    "CIN": {"name": "Cincinnati Bengals", "color": "#FB4F14", "secondary": "#000000", "effect": "claws", "conf": "AFC",
            "div": "North"},
    "CLE": {"name": "Cleveland Browns", "color": "#311D00", "secondary": "#FF3C00", "effect": "fire", "conf": "AFC",
            "div": "North"},
    "DAL": {"name": "Dallas Cowboys", "color": "#003594", "secondary": "#869397", "effect": "spotlight", "conf": "NFC",
            "div": "East"},
    "DEN": {"name": "Denver Broncos", "color": "#FB4F14", "secondary": "#002244", "effect": "storm", "conf": "AFC",
            "div": "West"},
    "DET": {"name": "Detroit Lions", "color": "#0076B6", "secondary": "#B0B7BC", "effect": "lightning", "conf": "NFC",
            "div": "North"},
    "GB": {"name": "Green Bay Packers", "color": "#203731", "secondary": "#FFB612", "effect": "spotlight",
           "conf": "NFC", "div": "North"},
    "HOU": {"name": "Houston Texans", "color": "#03202F", "secondary": "#A71930", "effect": "fire", "conf": "AFC",
            "div": "South"},
    "IND": {"name": "Indianapolis Colts", "color": "#002C5F", "secondary": "#A2AAAD", "effect": "lightning",
            "conf": "AFC", "div": "South"},
    "JAX": {"name": "Jacksonville Jaguars", "color": "#006778", "secondary": "#D7A22A", "effect": "wave", "conf": "AFC",
            "div": "South"},
    "KC": {"name": "Kansas City Chiefs", "color": "#E31837", "secondary": "#FFB81C", "effect": "fire", "conf": "AFC",
           "div": "West"},
    "LV": {"name": "Las Vegas Raiders", "color": "#000000", "secondary": "#A5ACAF", "effect": "spotlight",
           "conf": "AFC", "div": "West"},
    "LAC": {"name": "Los Angeles Chargers", "color": "#0080C6", "secondary": "#FFC20E", "effect": "lightning",
            "conf": "AFC", "div": "West"},
    "LAR": {"name": "Los Angeles Rams", "color": "#003594", "secondary": "#FFA300", "effect": "speed", "conf": "NFC",
            "div": "West"},
    "MIA": {"name": "Miami Dolphins", "color": "#008E97", "secondary": "#FC4C02", "effect": "wave", "conf": "AFC",
            "div": "East"},
    "MIN": {"name": "Minnesota Vikings", "color": "#4F2683", "secondary": "#FFC62F", "effect": "storm", "conf": "NFC",
            "div": "North"},
    "NE": {"name": "New England Patriots", "color": "#002244", "secondary": "#C60C30", "effect": "spotlight",
           "conf": "AFC", "div": "East"},
    "NO": {"name": "New Orleans Saints", "color": "#D3BC8D", "secondary": "#101820", "effect": "spotlight",
           "conf": "NFC", "div": "South"},
    "NYG": {"name": "New York Giants", "color": "#0B2265", "secondary": "#A71930", "effect": "lightning", "conf": "NFC",
            "div": "East"},
    "NYJ": {"name": "New York Jets", "color": "#125740", "secondary": "#FFFFFF", "effect": "speed", "conf": "AFC",
            "div": "East"},
    "PHI": {"name": "Philadelphia Eagles", "color": "#004C54", "secondary": "#A5ACAF", "effect": "storm", "conf": "NFC",
            "div": "East"},
    "PIT": {"name": "Pittsburgh Steelers", "color": "#FFB612", "secondary": "#101820", "effect": "fire", "conf": "AFC",
            "div": "North"},
    "SF": {"name": "San Francisco 49ers", "color": "#AA0000", "secondary": "#B3995D", "effect": "fire", "conf": "NFC",
           "div": "West"},
    "SEA": {"name": "Seattle Seahawks", "color": "#002244", "secondary": "#69BE28", "effect": "wave", "conf": "NFC",
            "div": "West"},
    "TB": {"name": "Tampa Bay Buccaneers", "color": "#D50A0A", "secondary": "#34302B", "effect": "fire", "conf": "NFC",
           "div": "South"},
    "TEN": {"name": "Tennessee Titans", "color": "#0C2340", "secondary": "#4B92DB", "effect": "lightning",
            "conf": "AFC", "div": "South"},
    "WAS": {"name": "Washington Commanders", "color": "#5A1414", "secondary": "#FFB612", "effect": "speed",
            "conf": "NFC", "div": "East"},
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
        broadcasts = competition.get("broadcasts", [])

        broadcast = (
            broadcasts[0].get("names", [""])[0]
            if broadcasts and broadcasts[0].get("names")
            else ""
        )

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
            "broadcast": broadcast,
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
                "broadcast": game.get("broadcast", ""),
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
    """Save changed ratings and one snapshot per new completed week; never fabricate past data."""
    if frame is None or frame.empty:
        return
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    csv_bytes = frame.sort_values("team").to_csv(index=False).encode("utf-8")
    fingerprint = hashlib.sha256(csv_bytes).hexdigest()
    history = read_history()
    current_week = get_latest_completed_week()
    if (
        history
        and history[-1].get("fingerprint") == fingerprint
        and history[-1].get("week") == current_week
    ):
        return
    now = datetime.now()
    history.append({
        "captured_at": now.isoformat(timespec="seconds"),
        "date": now.strftime("%Y-%m-%d"),
        "week": current_week,
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

    overall_rating = float(row["overall_rating"])
    classification = grade_label(overall_rating)

    st.markdown(
        f'<div class="rank-row">'
        f'<div class="rank-num">#{int(row["rank"]):02d}</div>'
        f'{logo(code, 58)}'
        f'<div class="rank-name">{html.escape(info["name"].upper())}'
        f'<div class="micro">'
        f'{info["conf"]} / {info["div"]} / '
        f'<span class="tier">{html.escape(classification.upper())}</span>'
        f'</div></div>'
        f'<div class="rank-score">{overall_rating:.1f}</div></div>',
        unsafe_allow_html=True,
    )

    if button_key and st.button(
        f"OPEN {code} PROFILE →",
        key=button_key
    ):
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
            f'<div class="profile-hero" style="--team:{leader_info.get("color", "#B99A5A")}">'
            f'<div class="micro">#1 IN THE NFL / CURRENT RATINGS LEADER</div>'
            f'<div style="display:flex;align-items:center;gap:25px;flex-wrap:wrap">'
            f'{logo(leader_code, 130)}<div><div class="profile-name">{html.escape(leader_info.get("name", ""))}</div>'
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
                            logo(code, width=60),
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
    """Find the next unplayed scheduled game, including a later kickoff today."""
    today = datetime.now().date()
    completed_ids = {
        str(game.get("schedule_id") or game.get("id") or "").strip()
        for game in get_results()
    }
    upcoming_games = []

    for game in get_schedule():
        if code not in (game.get("home"), game.get("away")):
            continue
        game_id = str(game.get("id") or "").strip()
        if game_id and game_id in completed_ids:
            continue
        try:
            game_date = datetime.strptime(game.get("date", ""), "%Y-%m-%d").date()
        except (ValueError, TypeError):
            continue
        if game_date < today:
            continue
        if game_date == today:
            kickoff_text = str(game.get("kickoff", "")).strip()
            try:
                kickoff_time = datetime.strptime(kickoff_text[:8], "%I:%M %p").time()
                if datetime.combine(game_date, kickoff_time) < datetime.now():
                    continue
            except (ValueError, TypeError):
                # If kickoff is TBD/unparseable, retain the unplayed same-day game.
                pass
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
