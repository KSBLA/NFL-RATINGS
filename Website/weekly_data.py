

from pathlib import Path

import pandas as pd
import streamlit as st

try:
    import polars as pl
except ImportError:
    pl = None


@st.cache_data(ttl=1800, show_spinner=False)
def load_weekly_team_stats(cache_path, modified_time):
    """Load cached nflreadpy weekly team statistics without changing the ratings engine."""
    path = Path(cache_path)
    if not path.exists():
        return pd.DataFrame()
    try:
        if pl is not None:
            return pl.read_parquet(path).to_pandas()
        return pd.read_parquet(path)
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=1800, show_spinner=False)
def load_play_by_play(cache_path, modified_time):
    """Load the cached play-by-play feed for player-level matchup context."""
    path = Path(cache_path)
    if not path.exists():
        return pd.DataFrame()
    try:
        if pl is not None:
            return pl.read_parquet(path).to_pandas()
        return pd.read_parquet(path)
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner=False)
def load_weekly_award_play_by_play(cache_path, modified_time, week, season):
    """Read only the columns and week needed for the weekly award cards."""
    path = Path(cache_path)
    if not path.exists():
        return pd.DataFrame()

    wanted_columns = [
        "week", "season", "posteam",
        "passer_player_id", "rusher_player_id", "receiver_player_id",
        "passer_player_name", "rusher_player_name", "receiver_player_name",
        "passing_yards", "passing_tds", "pass_touchdown", "complete_pass",
        "pass_attempt", "rushing_yards", "rush_attempt", "rushing_tds",
        "rush_touchdown", "receiving_yards", "receiving_tds", "epa",
    ]

    try:
        try:
            import pyarrow.parquet as parquet
            available = set(parquet.ParquetFile(path).schema.names)
        except Exception:
            available = None

        if available is None:
            frame = pd.read_parquet(path)
            columns = [column for column in wanted_columns if column in frame.columns]
            frame = frame[columns]
        else:
            columns = [column for column in wanted_columns if column in available]
            filters = [("week", "==", int(week))]
            if "season" in columns:
                filters.append(("season", "==", int(season)))
            try:
                frame = pd.read_parquet(path, columns=columns, filters=filters)
            except Exception:
                frame = pd.read_parquet(path, columns=columns)

        if "week" in frame.columns:
            frame = frame[pd.to_numeric(frame["week"], errors="coerce") == int(week)]
        if "season" in frame.columns:
            frame = frame[pd.to_numeric(frame["season"], errors="coerce") == int(season)]
        return frame
    except Exception:
        return pd.DataFrame()


# ============================================================
# Merged from weekly_rosters.py
# ============================================================



import pandas as pd


def load_weekly_rosters(cache_dir, nfl_season):
    path = cache_dir / f"weekly_rosters_{nfl_season}.parquet"

    if path.exists():
        return pd.read_parquet(path)

    url = (
        "https://github.com/nflverse/nflverse-data/releases/"
        f"download/weekly_rosters/roster_weekly_{nfl_season}.parquet"
    )

    try:
        rosters = pd.read_parquet(url)
        path.parent.mkdir(parents=True, exist_ok=True)
        rosters.to_parquet(path, index=False)
        return rosters
    except Exception as exc:
        print(f"Unable to load weekly rosters: {exc}")
        return pd.DataFrame()


# ============================================================
# Merged from weekly_results.py
# ============================================================




def get_latest_completed_week(get_results):
    completed = []
    for game in get_results():
        try:
            completed.append(int(game.get("week")))
        except (TypeError, ValueError):
            continue
    return max(completed) if completed else None


# ============================================================
# Merged from player_stats.py
# ============================================================



import pandas as pd


def get_player_leaders(team_code, pbp, week=None):
    """Build a small player-stat profile from cached play-by-play; return None if unavailable."""
    if pbp.empty or "posteam" not in pbp.columns:
        return None

    data = pbp.copy()

    if week is not None and "week" in data.columns:
        data = data[pd.to_numeric(data["week"], errors="coerce") <= int(week)]

    stats_aliases = {
        "LAR": {"LAR", "LA"},
        "WAS": {"WAS", "WSH"},
        "JAX": {"JAX", "JAC"},
    }

    accepted_codes = stats_aliases.get(team_code, {team_code})
    data = data[data["posteam"].astype(str).str.upper().isin(accepted_codes)]

    leaders = []

    for name_col, yards_col, label in [
        ("passer_player_name", "passing_yards", "Passing"),
        ("rusher_player_name", "rushing_yards", "Rushing"),
        ("receiver_player_name", "receiving_yards", "Receiving"),
    ]:
        if name_col not in data.columns or yards_col not in data.columns:
            continue

        player_rows = data[[name_col, yards_col]].copy()
        player_rows[yards_col] = pd.to_numeric(
            player_rows[yards_col], errors="coerce"
        ).fillna(0)

        player_rows = player_rows[
            player_rows[name_col].notna()
            & (player_rows[name_col].astype(str).str.strip() != "")
        ]

        if player_rows.empty:
            continue

        totals = (
            player_rows.groupby(name_col)[yards_col]
            .sum()
            .sort_values(ascending=False)
        )

        if not totals.empty:
            leaders.append({
                "name": str(totals.index[0]),
                "yards": float(totals.iloc[0]),
                "category": label,
            })

    return leaders or None


# ============================================================
# Merged from player_highlights.py
# ============================================================


import numpy as np
import pandas as pd


def build_player_highlights(team_code, opponent_code, pbp, roster, week):
    """Build four team-only highlights across offensive and defensive players/units."""
    if pbp.empty or "posteam" not in pbp.columns:
        return None

    data = pbp.copy()
    if week is not None and "week" in data.columns:
        data = data[pd.to_numeric(data["week"], errors="coerce") <= int(week)]

    aliases = {"LAR": {"LAR", "LA"}, "WAS": {"WAS", "WSH"}, "JAX": {"JAX", "JAC"}}
    own_codes = aliases.get(team_code, {team_code})
    own_pbp = data[data["posteam"].astype(str).str.upper().isin(own_codes)].copy()

    if own_pbp.empty:
        return None

    # Use this team's weekly roster to classify players into real position groups.
    position_by_name = {}
    if isinstance(roster, pd.DataFrame) and not roster.empty:
        roster_name = next((c for c in ("player_name", "full_name", "display_name") if c in roster.columns), None)
        roster_pos = next((c for c in ("position", "position_group") if c in roster.columns), None)
        roster_team = next((c for c in ("team", "team_abbr") if c in roster.columns), None)

        if roster_name and roster_pos:
            rows = roster.copy()
            if roster_team:
                rows = rows[rows[roster_team].astype(str).str.upper().isin(own_codes)]

            position_by_name = {
                str(r[roster_name]).strip().casefold(): str(r[roster_pos]).upper().strip()
                for _, r in rows.iterrows()
                if pd.notna(r[roster_name]) and pd.notna(r[roster_pos])
            }

    def position_group(position, fallback):
        if position == "QB": return "Quarterback room"
        if position in {"RB", "FB", "HB"}: return "Running backs"
        if position == "WR": return "Wide receivers"
        if position == "TE": return "Tight ends"
        if position in {"C", "G", "OG", "T", "OT", "OL", "LG", "RG", "LT", "RT"}: return "Offensive line"
        if position in {"DE", "DT", "NT", "DL", "EDGE", "OLB", "ILB", "LB"}: return "Front seven"
        if position in {"CB", "DB", "S", "FS", "SS"}: return "Secondary"
        if position in {"K", "P", "LS"}: return "Special teams"
        return fallback

    player_totals = {}

    def add_events(
        name_col,
        yards_col=None,
        volume_col=None,
        fallback_pos="UNK",
        fallback_group="Team unit",
        event_kind="offense",
    ):
        if name_col not in own_pbp.columns:
            return

        cols = [name_col]
        if yards_col and yards_col in own_pbp.columns:
            cols.append(yards_col)
        if volume_col and volume_col in own_pbp.columns:
            cols.append(volume_col)
        if "epa" in own_pbp.columns:
            cols.append("epa")

        chunk = own_pbp[cols].copy()
        chunk = chunk[
            chunk[name_col].notna()
            & (chunk[name_col].astype(str).str.strip() != "")
        ]

        if chunk.empty:
            return

        chunk["_name"] = chunk[name_col].astype(str).str.strip()
        chunk["_yards"] = (
            pd.to_numeric(chunk[yards_col], errors="coerce").fillna(0)
            if yards_col and yards_col in chunk else 0.0
        )
        chunk["_epa"] = (
            pd.to_numeric(chunk["epa"], errors="coerce")
            if "epa" in chunk else np.nan
        )

        if volume_col and volume_col in chunk:
            chunk["_volume"] = (
                pd.to_numeric(chunk[volume_col], errors="coerce").fillna(0) > 0
            ).astype(int)
        else:
            chunk["_volume"] = 1

        for name, grp in chunk.groupby("_name"):
            key = str(name).casefold()
            position = position_by_name.get(key, fallback_pos)
            group = position_group(position, fallback_group)

            bucket = player_totals.setdefault(
                key,
                {
                    "name": str(name),
                    "position": position,
                    "group": group,
                    "yards": 0.0,
                    "volume": 0,
                    "epa_sum": 0.0,
                    "epa_count": 0,
                    "side": event_kind,
                },
            )

            bucket["yards"] += float(grp["_yards"].sum())
            bucket["volume"] += int(grp["_volume"].sum())

            valid_epa = grp["_epa"].dropna()
            bucket["epa_sum"] += float(valid_epa.sum()) * (
                -1 if event_kind == "defense" else 1
            )
            bucket["epa_count"] += len(valid_epa)

    # Offensive production.
    add_events("passer_player_name", "passing_yards", "pass_attempt", "QB", "Quarterback room")
    add_events("rusher_player_name", "rushing_yards", "rush_attempt", "RB", "Running backs")
    add_events("receiver_player_name", "receiving_yards", "complete_pass", "WR", "Receiving corps")

    # Defensive production: tackle, sack, interception, forced-fumble and recovery events.
    # These columns are attributed to the defense facing the offense on that play.
    defensive_events = [
        ("solo_tackle_1_player_name", "Solo tackles"),
        ("solo_tackle_2_player_name", "Solo tackles"),
        ("assist_tackle_1_player_name", "Assisted tackles"),
        ("assist_tackle_2_player_name", "Assisted tackles"),
        ("sack_player_name", "Sacks"),
        ("interception_player_name", "Interceptions"),
        ("forced_fumble_player_1_player_name", "Forced fumbles"),
        ("forced_fumble_player_2_player_name", "Forced fumbles"),
        ("fumble_recovery_1_player_name", "Fumble recoveries"),
        ("fumble_recovery_2_player_name", "Fumble recoveries"),
    ]

    defense_pbp = data[
        data.get(
            "defteam",
            pd.Series(index=data.index, dtype=object),
        ).astype(str).str.upper().isin(own_codes)
    ].copy()

    if not defense_pbp.empty:
        original = own_pbp
        own_pbp = defense_pbp

        for col, label in defensive_events:
            add_events(col, None, None, "UNK", "Defense", "defense")

        own_pbp = original

    player_rows = []
    for item in player_totals.values():
        if item["volume"] <= 0:
            continue

        efficiency = (
            item["epa_sum"] / item["epa_count"]
            if item["epa_count"]
            else item["yards"] / item["volume"]
        )

        player_rows.append({
            "name": item["name"],
            "position": item["position"],
            "group": item["group"],
            "yards": item["yards"],
            "volume": item["volume"],
            "efficiency": efficiency,
            "side": item["side"],
        })

    qualified = [x for x in player_rows if x["volume"] >= 8]
    if not qualified:
        return None

    positive_player = max(
        qualified,
        key=lambda x: (x["efficiency"], x["yards"]),
    )

    concern_pool = [x for x in qualified if x["volume"] >= 15]
    negative_player = min(
        concern_pool or qualified,
        key=lambda x: x["efficiency"],
    )

    by_group = {}
    for item in player_rows:
        bucket = by_group.setdefault(
            item["group"],
            {"yards": 0.0, "volume": 0, "weighted_eff": 0.0},
        )
        bucket["yards"] += item["yards"]
        bucket["volume"] += item["volume"]
        bucket["weighted_eff"] += item["efficiency"] * item["volume"]

    groups = [
        {
            "name": name,
            "yards": vals["yards"],
            "volume": vals["volume"],
            "efficiency": vals["weighted_eff"] / vals["volume"],
        }
        for name, vals in by_group.items()
        if vals["volume"] >= 20
    ]

    if not groups:
        return None

    return {
        "positive_player": positive_player,
        "positive_group": max(groups, key=lambda x: x["efficiency"]),
        "negative_player": negative_player,
        "negative_group": min(groups, key=lambda x: x["efficiency"]),
        "week": week,
        "sample_note": "Season-to-date play-by-play; qualified players and units from both offense and defense are eligible, filtered to the profiled team. Defensive efficiency is direction-adjusted so stronger defensive plays score better.",
    }

