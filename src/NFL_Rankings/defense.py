
import polars as pl


# ---------------------------------------------------------
# DEFENSIVE EFFICIENCY
# ---------------------------------------------------------

def build_defensive_efficiency_metrics(scrimmage):

    metrics = (
        scrimmage.group_by("defteam")
        .agg(
            pl.len().alias("defensive_plays"),

            pl.col("epa").mean().alias("def_epa_allowed_per_play"),

            pl.col("epa").sum().alias("def_total_epa_allowed"),

            pl.col("success").mean().alias("def_success_rate_allowed"),

            pl.col("yards_gained").mean().alias("def_yards_allowed_per_play"),

            pl.col("epa")
            .filter(pl.col("play_type") == "pass")
            .mean()
            .alias("pass_epa_allowed_per_play"),

            pl.col("epa")
            .filter(pl.col("play_type") == "run")
            .mean()
            .alias("rush_epa_allowed_per_play")
        )
        .rename({"defteam": "team"})
        .sort("team")
    )

    return metrics

# ---------------------------------------------------------
# DEFENSIVE EARLY-DOWN PERFORMANCE
# ---------------------------------------------------------

def build_defensive_early_down_metrics(scrimmage):

    early_downs = scrimmage.filter(
        pl.col("down").is_in([1.0, 2.0])
    )

    metrics = (
        early_downs.group_by("defteam")
        .agg(
            pl.len().alias("def_early_down_plays"),

            pl.col("success").mean().alias("def_early_down_success_allowed"),

            pl.col("success")
            .filter(pl.col("down") == 1)
            .mean()
            .alias("def_first_down_success_allowed"),

            pl.col("success")
            .filter(pl.col("down") == 2)
            .mean()
            .alias("def_second_down_success_allowed")
        )
        .rename({"defteam": "team"})
        .sort("team")
    )

    return metrics


# ---------------------------------------------------------
# DEFENSIVE EXPLOSIVE-PLAY PERFORMANCE
# ---------------------------------------------------------

def build_defensive_explosive_play_metrics(scrimmage):

    explosive_passes = scrimmage.filter(
        (pl.col("play_type") == "pass")
        & (pl.col("yards_gained") >= 20)
    )

    explosive_runs = scrimmage.filter(
        (pl.col("play_type") == "run")
        & (pl.col("yards_gained") >= 10)
    )

    defense = (
        scrimmage.group_by("defteam")
        .agg(
            (pl.col("play_type") == "pass")
            .sum()
            .alias("def_pass_plays_faced"),

            (pl.col("play_type") == "run")
            .sum()
            .alias("def_rush_plays_faced")
        )
        .join(
            explosive_passes.group_by("defteam")
            .agg(
                pl.len().alias("explosive_pass_plays_allowed"),
                pl.col("yards_gained").sum().alias("explosive_pass_yards_allowed")
            ),
            on="defteam",
            how="left"
        )
        .join(
            explosive_runs.group_by("defteam")
            .agg(
                pl.len().alias("explosive_rush_plays_allowed"),
                pl.col("yards_gained").sum().alias("explosive_rush_yards_allowed")
            ),
            on="defteam",
            how="left"
        )
        .with_columns(
            pl.col([
                "explosive_pass_plays_allowed",
                "explosive_pass_yards_allowed",
                "explosive_rush_plays_allowed",
                "explosive_rush_yards_allowed"
            ]).fill_null(0)
        )
        .with_columns(
            (
                pl.col("explosive_pass_plays_allowed")
                / pl.col("def_pass_plays_faced")
            ).alias("explosive_pass_rate_allowed"),

            (
                pl.col("explosive_rush_plays_allowed")
                / pl.col("def_rush_plays_faced")
            ).alias("explosive_rush_rate_allowed"),

            (
                (
                    pl.col("explosive_pass_plays_allowed")
                    + pl.col("explosive_rush_plays_allowed")
                )
                / (
                    pl.col("def_pass_plays_faced")
                    + pl.col("def_rush_plays_faced")
                )
            ).alias("overall_explosive_rate_allowed")
        )
        .rename({"defteam": "team"})
        .sort("team")
    )

    return defense


# ---------------------------------------------------------
# DEFENSIVE TURNOVER PERFORMANCE
# ---------------------------------------------------------


def build_defensive_turnover_metrics(pbp):
    turnovers = pbp.filter(
        pl.col("defteam").is_not_null()
    )

    metrics = (
        turnovers.group_by("defteam")
        .agg(
            pl.col("interception")
            .sum()
            .alias("interceptions"),

            (
                (
                    (pl.col("fumble_lost") == 1)
                    & (
                        (pl.col("fumble_recovery_1_team") == pl.col("defteam"))
                        | (pl.col("fumble_recovery_2_team") == pl.col("defteam"))
                    )
                )
                .fill_null(False)
                .cast(pl.Int64)
                .sum()
            ).alias("fumbles_recovered")
        )
        .with_columns(
            (
                pl.col("interceptions")
                + pl.col("fumbles_recovered")
            ).alias("total_takeaways")
        )
        .rename({"defteam": "team"})
        .sort("team")
    )

    return metrics


# ---------------------------------------------------------
# DEFENSIVE PASS RUSH
# ---------------------------------------------------------


def build_defensive_pass_rush_metrics(pbp):

    dropbacks = pbp.filter(
        (pl.col("qb_dropback") == 1)
        & pl.col("defteam").is_not_null()
    )

    metrics = (
        dropbacks.group_by("defteam")
        .agg(
            pl.len().alias("def_qb_dropbacks"),

            pl.col("sack")
            .sum()
            .alias("sacks_recorded"),

            pl.col("qb_hit")
            .sum()
            .alias("qb_hits_generated"),

            (
                (
                    (pl.col("qb_hit") == 1)
                    & (pl.col("sack") != 1)
                )
                .fill_null(False)
                .cast(pl.Int64)
                .sum()
            ).alias("non_sack_qb_hits_generated")
        )
        .with_columns(
            (
                pl.col("sacks_recorded")
                / pl.col("def_qb_dropbacks")
            ).alias("def_sack_rate"),

            (
                pl.col("non_sack_qb_hits_generated")
                / pl.col("def_qb_dropbacks")
            ).alias("def_non_sack_qb_hit_rate")
        )
        .rename({"defteam": "team"})
        .sort("team")
    )

    return metrics

# ---------------------------------------------------------
# COMPLETE DEFENSIVE METRICS
# ---------------------------------------------------------


def build_defensive_metrics(pbp, scrimmage):

    efficiency = build_defensive_efficiency_metrics(scrimmage)
    early_downs = build_defensive_early_down_metrics(scrimmage)
    explosive_plays = build_defensive_explosive_play_metrics(scrimmage)
    turnovers = build_defensive_turnover_metrics(pbp)
    pass_rush = build_defensive_pass_rush_metrics(pbp)

    metrics = (
        efficiency
        .join(early_downs, on="team", how="inner")
        .join(explosive_plays, on="team", how="inner")
        .join(turnovers, on="team", how="left")
        .join(pass_rush, on="team", how="left")
        .with_columns(
            pl.col([
                "interceptions",
                "fumbles_recovered",
                "total_takeaways",
                "def_qb_dropbacks",
                "sacks_recorded",
                "qb_hits_generated",
                "non_sack_qb_hits_generated",
                "def_sack_rate",
                "def_non_sack_qb_hit_rate",
            ]).fill_null(0)
        )
        .sort("team")
    )

    return metrics
