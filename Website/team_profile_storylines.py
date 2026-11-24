"""Data-backed storyline helpers for NFL Ratings team profiles.

This module deliberately uses only supplied team metrics, rankings, records,
and completed game results. It does not create missing statistics or results.
"""

from __future__ import annotations

from typing import Any

import math


TEAM_CODE_ALIASES = {
    "LA": "LAR",
    "WSH": "WAS",
    "JAC": "JAX",
}


# label, metric column, higher-is-better, category
_METRIC_CANDIDATES = (
    ("Offensive EPA per play", "off_epa_per_play", True, "OFFENSE"),
    ("Offensive success rate", "off_success_rate", True, "OFFENSE"),
    ("Explosive-play rate", "overall_explosive_rate", True, "OFFENSE"),
    ("Third-down conversion rate", "third_down_conversion_rate", True, "OFFENSE"),
    ("Red-zone touchdown rate", "red_zone_td_rate", True, "OFFENSE"),
    ("Defensive EPA allowed per play", "def_epa_allowed_per_play", False, "DEFENSE"),
    ("Defensive success rate allowed", "def_success_rate_allowed", False, "DEFENSE"),
    ("Yards allowed per play", "def_yards_allowed_per_play", False, "DEFENSE"),
    ("Explosive-play rate allowed", "overall_explosive_rate_allowed", False, "DEFENSE"),
    ("Field-goal make rate", "fg_make_rate", True, "SPECIAL TEAMS"),
    ("Punt inside-20 rate", "punt_inside_twenty_rate", True, "SPECIAL TEAMS"),
    ("Penalty yards per flag", "penalty_yards_per_flag", False, "DISCIPLINE"),
    ("Average point differential", "on_field_avg_point_differential", True, "ON-FIELD"),
)


def _normalize_team(code: Any) -> str:
    value = str(code or "").strip().upper()
    return TEAM_CODE_ALIASES.get(value, value)


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _row_for_team(frame: Any, code: str) -> dict[str, Any] | None:
    if frame is None or getattr(frame, "empty", True) or "team" not in frame.columns:
        return None
    accepted = {code}
    if code == "LAR":
        accepted.add("LA")
    elif code == "WAS":
        accepted.add("WSH")
    elif code == "JAX":
        accepted.add("JAC")
    rows = frame[frame["team"].astype(str).str.upper().str.strip().isin(accepted)]
    return rows.iloc[0].to_dict() if not rows.empty else None


def _percentile(frame: Any, column: str, value: float, higher_is_better: bool) -> float | None:
    if frame is None or getattr(frame, "empty", True) or column not in frame.columns:
        return None
    try:
        values = frame[column].astype(float)
    except (TypeError, ValueError):
        import pandas as pd
        values = pd.to_numeric(frame[column], errors="coerce")
    values = values.dropna()
    if len(values) < 16:
        return None
    if higher_is_better:
        percentile = (values <= value).mean()
    else:
        percentile = (values >= value).mean()
    return round(float(percentile) * 100, 1)


def _completed_team_games(code: str, games: list[dict[str, Any]], teams: dict[str, Any]) -> list[dict[str, Any]]:
    completed = []
    for game in games or []:
        home = _normalize_team(game.get("home"))
        away = _normalize_team(game.get("away"))
        if code not in (home, away):
            continue
        home_score = _number(game.get("home_score"))
        away_score = _number(game.get("away_score"))
        week = _number(game.get("week"))
        if home_score is None or away_score is None or week is None:
            continue
        home_score, away_score = int(home_score), int(away_score)
        if home_score == away_score:
            result = "T"
        elif (code == home and home_score > away_score) or (code == away and away_score > home_score):
            result = "W"
        else:
            result = "L"
        completed.append({
            "week": int(week),
            "date": str(game.get("date") or ""),
            "opponent": away if code == home else home,
            "result": result,
            "team_score": home_score if code == home else away_score,
            "opponent_score": away_score if code == home else home_score,
            "opponent_name": teams.get(away if code == home else home, {}).get("name", away if code == home else home),
        })
    completed.sort(key=lambda item: (item["week"], item["date"]))
    return completed


def _season_profile(team_row: dict[str, Any] | None, ratings_row: dict[str, Any] | None,
                    metrics_frame: Any, record: dict[str, Any] | None) -> dict[str, Any]:
    findings = []
    if team_row:
        for label, column, higher, category in _METRIC_CANDIDATES:
            value = _number(team_row.get(column))
            percentile = _percentile(metrics_frame, column, value, higher) if value is not None else None
            if value is None or percentile is None:
                continue
            findings.append({
                "label": label,
                "column": column,
                "category": category,
                "value": value,
                "percentile": percentile,
                "higher_is_better": higher,
            })

    strengths = sorted(findings, key=lambda item: item["percentile"], reverse=True)
    weaknesses = sorted(findings, key=lambda item: item["percentile"])
    strength = strengths[0] if strengths else None
    weakness = weaknesses[0] if weaknesses else None

    overall_rating = _number((ratings_row or {}).get("overall_rating"))
    win_pct = _number((record or {}).get("PCT"))
    identity = "The available team metrics do not support a clear statistical identity yet."
    if strength and weakness:
        if strength["category"] == weakness["category"]:
            identity = (
                f"The clearest current identity is {strength['category'].lower()}-driven, "
                f"with {strength['label'].lower()} ranking in the {strength['percentile']:.0f}th league percentile. "
                f"The same area also contains a relative weakness in {weakness['label'].lower()} "
                f"({weakness['percentile']:.0f}th percentile)."
            )
        else:
            identity = (
                f"The team's strongest measured area is {strength['label'].lower()} "
                f"({strength['percentile']:.0f}th percentile), while its clearest measured weakness is "
                f"{weakness['label'].lower()} ({weakness['percentile']:.0f}th percentile)."
            )

    if win_pct is not None and overall_rating is not None:
        identity += f" The current record-based win percentage is {win_pct:.3f}; the overall model rating is {overall_rating:.1f}."

    return {
        "identity": identity,
        "strength": strength,
        "weakness": weakness,
        "overall_rating": overall_rating,
        "win_percentage": win_pct,
        "findings_count": len(findings),
        "findings": findings,
    }


def _recent_profile(recent_games: list[dict[str, Any]], team_row: dict[str, Any] | None) -> dict[str, Any]:
    if not recent_games:
        return {"available": False, "text": "No completed game results are available for this team yet."}

    wins = sum(game["result"] == "W" for game in recent_games)
    losses = sum(game["result"] == "L" for game in recent_games)
    ties = sum(game["result"] == "T" for game in recent_games)
    scored = sum(game["team_score"] for game in recent_games) / len(recent_games)
    allowed = sum(game["opponent_score"] for game in recent_games) / len(recent_games)
    margin = scored - allowed

    season_scored = _number((team_row or {}).get("on_field_points_scored_per_game"))
    season_allowed = _number((team_row or {}).get("on_field_points_allowed_per_game"))
    offense_delta = scored - season_scored if season_scored is not None else None
    defense_delta = season_allowed - allowed if season_allowed is not None else None

    notes = [f"The last {len(recent_games)} completed games produced a {wins}-{losses}-{ties} record and an average point differential of {margin:+.1f} per game."]
    if offense_delta is not None:
        if offense_delta >= 2:
            notes.append(f"Scoring is up {offense_delta:.1f} points per game versus the season average.")
        elif offense_delta <= -2:
            notes.append(f"Scoring is down {abs(offense_delta):.1f} points per game versus the season average.")
        else:
            notes.append("Scoring is broadly in line with the season average.")
    if defense_delta is not None:
        if defense_delta >= 2:
            notes.append(f"Points allowed are down {defense_delta:.1f} per game versus the season average.")
        elif defense_delta <= -2:
            notes.append(f"Points allowed are up {abs(defense_delta):.1f} per game versus the season average.")
        else:
            notes.append("Points allowed are broadly in line with the season average.")
    if season_scored is None or season_allowed is None:
        notes.append("Season scoring/defense baselines are incomplete, so no season-to-recent comparison is shown for the missing measures.")

    return {
        "available": True,
        "record": f"{wins}-{losses}-{ties}",
        "games_count": len(recent_games),
        "points_scored_per_game": round(scored, 1),
        "points_allowed_per_game": round(allowed, 1),
        "point_differential_per_game": round(margin, 1),
        "text": " ".join(notes),
    }


def _five_game_headline(recent_five: list[dict[str, Any]], code: str) -> tuple[str, str]:
    if not recent_five:
        return "RECENT FORM UNAVAILABLE", "No completed games are available to build a five-game summary."

    wins = sum(game["result"] == "W" for game in recent_five)
    losses = sum(game["result"] == "L" for game in recent_five)
    ties = sum(game["result"] == "T" for game in recent_five)
    record = f"{wins}-{losses}-{ties}"
    scored = sum(g["team_score"] for g in recent_five)
    allowed = sum(g["opponent_score"] for g in recent_five)
    margin = scored - allowed
    last_result = recent_five[-1]["result"]
    # Multiple headline choices per record; choose based on actual recent trends
    # so same record teams need not receive identical wording.
    headline_options = {
        5: [
            "FIVE STRAIGHT — UNSTOPPABLE MOMENTUM",
            "PERFECT RUN, STATEMENT MADE",
            "FIVE-GAME WIN STREAK: THE STANDARD IS RISING",
            "A DOMINANT FIVE-GAME STRETCH",
        ],
        4: [
            "FOUR WINS IN FIVE: CONTENDER FORM",
            "A HOT RUN WITH ONE SETBACK",
            "WINNING FORM, MOMENTUM IN THEIR FAVOR",
            "FOUR OF FIVE — KEEP THE PRESSURE ON",
        ],
        3: [
            "A SOLID STRETCH, BUT ROOM TO GROW",
            "THREE WINS KEEP THE TEAM MOVING",
            "MIXED RESULTS, POSITIVE BALANCE",
            "A .500-PLUS RUN WITH MOMENTUM TO BUILD",
        ],
        2: [
            "TWO WINS IN FIVE: SEARCHING FOR CONSISTENCY",
            "A CHOPPY FIVE-GAME stretch",
            "RESULTS HAVE BEEN MIXED",
            "A STRETCH THAT NEEDS A TURNAROUND",
        ],
        1: [
            "ONE WIN IN FIVE — THE PRESSURE IS ON",
            "A TOUGH RUN, LOOKING FOR A SPARK",
            "ONE BRIGHT SPOT IN A DIFFICULT STRETCH",
            "THE SLIDE NEEDS TO STOP",
        ],
        0: [
            "FIVE STRAIGHT LOSSES: URGENT RESPONSE NEEDED",
            "A WINLESS STRETCH AND QUESTIONS MOUNT",
            "SEARCHING FOR ANSWERS AFTER FIVE LOSSES",
            "THE TURNAROUND CAN'T WAIT",
        ],
    }
    # Use score margin and last result to vary headline selection repeatably.
    options = headline_options[wins]
    selector = (abs(margin) + (3 if last_result == "W" else 1 if last_result == "T" else 0)) % len(options)
    title = options[selector]

    biggest_win = max(
        (g for g in recent_five if g["result"] == "W"),
        key=lambda g: g["team_score"] - g["opponent_score"],
        default=None,
    )
    biggest_loss = max(
        (g for g in recent_five if g["result"] == "L"),
        key=lambda g: g["opponent_score"] - g["team_score"],
        default=None,
    )
    closest_game = min(recent_five, key=lambda g: abs(g["team_score"] - g["opponent_score"]))
    details = [f"Record across the last five: {record}."]
    if biggest_win:
        details.append(
            f"Best win: {biggest_win['opponent_name']} by "
            f"{biggest_win['team_score'] - biggest_win['opponent_score']}."
        )
    if biggest_loss and (not biggest_win or biggest_loss["opponent_score"] - biggest_loss["team_score"] > biggest_win["team_score"] - biggest_win["opponent_score"]):
        details.append(
            f"The heaviest defeat was against {biggest_loss['opponent_name']} by "
            f"{biggest_loss['opponent_score'] - biggest_loss['team_score']}."
        )
    details.append(
        f"Closest game: {closest_game['opponent_name']} "
        f"({closest_game['team_score']}-{closest_game['opponent_score']})."
    )
    return title, " ".join(details)


def _season_storylines(season: dict[str, Any], record: dict[str, Any] | None, team_name: str) -> dict[str, Any]:
    """Build one season-wide headline plus four distinct offense/defense stories."""
    strength = season.get("strength")
    weakness = season.get("weakness")
    rating = season.get("overall_rating")
    pct = season.get("win_percentage")

    findings = season.get("findings", [])
    offensive = [item for item in findings if item.get("category") == "OFFENSE"]
    defensive = [item for item in findings if item.get("category") == "DEFENSE"]

    def two_stories(items, side):
        # A positive and a challenge are more interesting than two duplicate stat summaries.
        best = max(items, key=lambda x: x.get("percentile", -1), default=None)
        worst = min(items, key=lambda x: x.get("percentile", 101), default=None)
        chosen = []
        if best:
            chosen.append({
                "headline": f"{best['label']} IS A SEASON STRENGTH",
                "description": f"{best['label']} ranks in the {best['percentile']:.0f}th league percentile, making it one of the team's clearest {side.lower()} strengths.",
                "kind": "strength",
            })
        if worst and (not best or worst.get("column") != best.get("column")):
            chosen.append({
                "headline": f"{worst['label']} IS AN AREA TO WATCH",
                "description": f"{worst['label']} sits in the {worst['percentile']:.0f}th league percentile, making it a key {side.lower()} area to improve.",
                "kind": "challenge",
            })
        while len(chosen) < 2:
            chosen.append({
                "headline": f"{side} STORY DATA LIMITED",
                "description": f"There isn't enough verified {side.lower()} data to establish another distinct full-season storyline.",
                "kind": "limited",
            })
        return chosen[:2]

    supporting = {
        "offense": two_stories(offensive, "OFFENSE"),
        "defense": two_stories(defensive, "DEFENSE"),
    }
    if strength and weakness:
        main = f"{team_name.upper()}: {strength['label'].upper()} SHAPES THE SEASON"
        main_detail = (
            f"Across the season, {strength['label'].lower()} has been the team's strongest measured trait "
            f"({strength['percentile']:.0f}th percentile), while {weakness['label'].lower()} "
            f"({weakness['percentile']:.0f}th percentile) remains its clearest vulnerability."
        )
    elif rating is not None and pct is not None:
        main = f"{team_name.upper()}: {pct:.3f} WIN PERCENTAGE, {rating:.1f} MODEL RATING"
        main_detail = "The season's defining picture from the verified record and current overall rating."
    else:
        main = f"{team_name.upper()}: SEASON SNAPSHOT"
        main_detail = "The available verified data does not yet establish a stronger season-wide headline."
    return {"main_headline": main, "main_detail": main_detail, "supporting": supporting}


def build_team_profile_storylines(team_code: str, team_metrics: Any, rankings: Any,
                                  games: list[dict[str, Any]], teams: dict[str, Any],
                                  record: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return season storylines and last-five results for one team."""
    code = _normalize_team(team_code)
    team_row = _row_for_team(team_metrics, code)
    ratings_row = _row_for_team(rankings, code)
    team_games = _completed_team_games(code, games, teams)
    last_three = team_games[-3:]
    last_five = team_games[-5:]

    season = _season_profile(team_row, ratings_row, team_metrics, record)
    # Compare overall rating against all teams using the ratings table.
    if ratings_row and rankings is not None and not getattr(rankings, "empty", True):
        rating = _number(ratings_row.get("overall_rating"))
        if rating is not None:
            season["overall_rating_percentile"] = _percentile(rankings, "overall_rating", rating, True)
    recent = _recent_profile(last_three, team_row)  # retained for data compatibility
    five_title, five_detail = _five_game_headline(last_five, code)
    storylines = _season_storylines(season, record, teams.get(code, {}).get("name", code))

    return {
        "season": season,
        "storylines": storylines,
        "recent": recent,
        "last_five": last_five,
        "five_game_record": (
            f"{sum(g['result'] == 'W' for g in last_five)}-"
            f"{sum(g['result'] == 'L' for g in last_five)}-"
            f"{sum(g['result'] == 'T' for g in last_five)}"
        ) if last_five else "N/A",
        "five_game_title": five_title,
        "five_game_detail": five_detail,
        "available_games": len(team_games),
    }
