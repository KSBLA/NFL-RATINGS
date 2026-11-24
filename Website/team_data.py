"""
This file creates the basic level of information surrounding a team needed to build everything
else off of.
"""

import pandas as pd


def calculate_team_records(teams, results):
    records = {
        code: {"W": 0, "L": 0, "T": 0, "PF": 0, "PA": 0}
        for code in teams
    }

    for game in results:
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


def calculate_team_momentum(code, results, recent_games=5):
    """Calculate a team's recent form and current result streak."""
    code = str(code).upper()
    team_games = []

    for game in results:
        home = game.get("home")
        away = game.get("away")

        if code not in (home, away):
            continue

        try:
            home_score = int(game["home_score"])
            away_score = int(game["away_score"])
            week = int(game.get("week", 0))
        except (KeyError, TypeError, ValueError):
            continue

        if home_score == away_score:
            result = "T"
        elif (code == home and home_score > away_score) or (
                code == away and away_score > home_score
        ):
            result = "W"
        else:
            result = "L"

        team_games.append({
            "week": week,
            "date": game.get("date", ""),
            "opponent": away if code == home else home,
            "result": result,
        })

    team_games.sort(key=lambda game: (game["week"], game["date"]))

    recent = team_games[-recent_games:]
    last_result = team_games[-1]["result"] if team_games else None

    streak_type = None
    streak_length = 0

    for game in reversed(team_games):
        if streak_type is None:
            streak_type = game["result"]

        if game["result"] != streak_type:
            break

        streak_length += 1

    return {
        "games_played": len(team_games),
        "recent_form": [game["result"] for game in recent],
        "recent_games": recent,
        "last_result": last_result,
        "streak_type": streak_type,
        "streak_length": streak_length,
    }


def format_team_record(code, records):
    record = records[code]
    return f'{record["W"]}-{record["L"]}-{record["T"]}'


def build_standings(teams, records, conference=None, division=None):
    rows = []

    for code, record in records.items():
        team_info = teams[code]

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
