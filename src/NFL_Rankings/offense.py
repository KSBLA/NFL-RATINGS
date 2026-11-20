
import polars as pl


# =========================================================
# OFFENSIVE EFFICIENCY
# =========================================================

def build_offensive_efficiency_metrics(scrimmage):

    metrics = (
        scrimmage
        .group_by("posteam")
        .agg(
            pl.len().alias("offensive_plays"),
            pl.col("epa").mean().alias("off_epa_per_play"),
            pl.col("epa").sum().alias("off_total_epa"),
            pl.col("success").mean().alias("off_success_rate"),
            pl.col("yards_gained").mean().alias("off_yards_per_play"),
            pl.col("epa").filter(pl.col("play_type") == "pass").mean().alias("pass_epa_per_play"),
            pl.col("epa").filter(pl.col("play_type") == "run").mean().alias("rush_epa_per_play"),
            pl.col("play_type").filter(pl.col("play_type") == "pass").count().alias("pass_plays"),
            pl.col("play_type").filter(pl.col("play_type") == "run").count().alias("rush_plays")
        )
        .rename({"posteam": "team"})
        .sort("team")
    )

    return metrics


# =========================================================
# THIRD-DOWN AND FOURTH-DOWN CONVERSIONS
# =========================================================

def build_offensive_down_conversion_metrics(pbp):

    third_downs = pbp.filter(
        (pl.col("down") == 3)
        & pl.col("posteam").is_not_null()
        & pl.col("third_down_converted").is_not_null()
        & pl.col("play_type").is_in(["pass", "run"])
    )

    third_down_metrics = (
        third_downs
        .group_by("posteam")
        .agg(
            pl.len().alias("third_down_attempts"),
            pl.col("third_down_converted").sum().alias("third_down_conversions")
        )
        .with_columns(
            (pl.col("third_down_conversions") / pl.col("third_down_attempts"))
            .alias("third_down_conversion_rate")
        )
        .rename({"posteam": "team"})
    )

    fourth_downs = pbp.filter(
        (pl.col("down") == 4)
        & pl.col("posteam").is_not_null()
        & pl.col("fourth_down_converted").is_not_null()
        & pl.col("play_type").is_in(["pass", "run"])
    )

    fourth_down_metrics = (
        fourth_downs
        .group_by("posteam")
        .agg(
            pl.len().alias("fourth_down_attempts"),
            pl.col("fourth_down_converted").sum().alias("fourth_down_conversions")
        )
        .with_columns(
            (pl.col("fourth_down_conversions") / pl.col("fourth_down_attempts"))
            .alias("fourth_down_conversion_rate")
        )
        .rename({"posteam": "team"})
    )

    return (
        third_down_metrics
        .join(fourth_down_metrics, on="team", how="full", coalesce=True)
        .sort("team")
    )


# =========================================================
# RED-ZONE OFFENSIVE PERFORMANCE
# =========================================================

def build_offensive_red_zone_metrics(pbp):

    red_zone_drives = (
        pbp.filter(
            (pl.col("yardline_100") <= 20)
            & (pl.col("yardline_100") >= 0)
            & pl.col("posteam").is_not_null()
            & pl.col("game_id").is_not_null()
            & pl.col("drive").is_not_null()
        )
        .select(["posteam", "game_id", "drive"])
        .unique()
    )

    drive_results = (
        pbp.join(
            red_zone_drives,
            on=["posteam", "game_id", "drive"],
            how="inner"
        )
        .group_by(["posteam", "game_id", "drive"])
        .agg(
            pl.col("touchdown").max().alias("touchdown"),
            pl.col("field_goal_result").is_in(["made"]).any().alias("field_goal_made")
        )
    )

    metrics = (
        drive_results
        .group_by("posteam")
        .agg(
            pl.len().alias("red_zone_trips"),
            pl.col("touchdown").sum().alias("red_zone_touchdowns"),
            pl.col("field_goal_made").sum().alias("red_zone_field_goals")
        )
        .with_columns(
            (pl.col("red_zone_touchdowns") / pl.col("red_zone_trips"))
            .alias("red_zone_td_rate"),
            (
                (pl.col("red_zone_touchdowns") + pl.col("red_zone_field_goals"))
                / pl.col("red_zone_trips")
            ).alias("red_zone_scoring_rate")
        )
        .rename({"posteam": "team"})
        .sort("team")
    )

    return metrics


# =========================================================
# EARLY-DOWN OFFENSIVE PERFORMANCE
# =========================================================

def build_offensive_early_down_metrics(scrimmage):

    early_downs = scrimmage.filter(
        pl.col("down").is_in([1.0, 2.0])
    )

    metrics = (
        early_downs
        .group_by("posteam")
        .agg(
            pl.len().alias("early_down_plays"),
            pl.col("success").mean().alias("off_early_down_success_rate"),
            pl.col("success").filter(pl.col("down") == 1).mean().alias("off_first_down_success_rate"),
            pl.col("success").filter(pl.col("down") == 2).mean().alias("off_second_down_success_rate")
        )
        .rename({"posteam": "team"})
        .sort("team")
    )

    return metrics


# =========================================================
# EXPLOSIVE OFFENSIVE PLAYS
# =========================================================

def build_offensive_explosive_play_metrics(scrimmage):

    explosive_passes = scrimmage.filter(
        (pl.col("play_type") == "pass")
        & (pl.col("yards_gained") >= 20)
    )

    explosive_runs = scrimmage.filter(
        (pl.col("play_type") == "run")
        & (pl.col("yards_gained") >= 10)
    )

    metrics = (
        scrimmage
        .group_by("posteam")
        .agg(
            pl.len().alias("total_scrimmage_plays"),
            (pl.col("play_type") == "pass").sum().alias("total_pass_plays"),
            (pl.col("play_type") == "run").sum().alias("total_rush_plays")
        )
        .join(
            explosive_passes.group_by("posteam").agg(
                pl.len().alias("explosive_pass_plays"),
                pl.col("yards_gained").sum().alias("explosive_pass_yards")
            ),
            on="posteam",
            how="left"
        )
        .join(
            explosive_runs.group_by("posteam").agg(
                pl.len().alias("explosive_rush_plays"),
                pl.col("yards_gained").sum().alias("explosive_rush_yards")
            ),
            on="posteam",
            how="left"
        )
        .with_columns(
            pl.col([
                "explosive_pass_plays",
                "explosive_pass_yards",
                "explosive_rush_plays",
                "explosive_rush_yards"
            ]).fill_null(0)
        )
        .with_columns(
            (pl.col("explosive_pass_plays") / pl.col("total_pass_plays")).alias("explosive_pass_rate"),
            (pl.col("explosive_rush_plays") / pl.col("total_rush_plays")).alias("explosive_rush_rate"),
            (
                (pl.col("explosive_pass_plays") + pl.col("explosive_rush_plays"))
                / pl.col("total_scrimmage_plays")
            ).alias("overall_explosive_rate")
        )
        .rename({"posteam": "team"})
        .sort("team")
    )

    return metrics


# =========================================================
# OFFENSIVE TURNOVERS
# =========================================================

def build_offensive_turnover_metrics(pbp):

    metrics = (
        pbp
        .filter(pl.col("posteam").is_not_null())
        .group_by("posteam")
        .agg(
            pl.col("interception").sum().alias("interceptions_thrown"),
            pl.col("fumble_lost").sum().alias("fumbles_lost")
        )
        .with_columns(
            (pl.col("interceptions_thrown") + pl.col("fumbles_lost"))
            .alias("total_giveaways")
        )
        .rename({"posteam": "team"})
        .sort("team")
    )

    return metrics


# =========================================================
# PASS PROTECTION
# =========================================================

def build_offensive_pass_protection_metrics(pbp):

    metrics = (
        pbp
        .filter(
            pl.col("posteam").is_not_null()
            & (pl.col("qb_dropback") == 1)
        )
        .group_by("posteam")
        .agg(
            pl.len().alias("qb_dropbacks"),
            pl.col("sack").sum().alias("sacks_allowed"),
            pl.col("qb_hit").sum().alias("qb_hits_allowed")
        )
        .with_columns(
            (
                pl.col("sacks_allowed")
                / pl.col("qb_dropbacks")
            ).alias("sack_rate_allowed"),

            (
                pl.col("qb_hits_allowed")
                / pl.col("qb_dropbacks")
            ).alias("qb_hit_rate_allowed")
        )
        .rename({"posteam": "team"})
        .sort("team")
    )

    return metrics

# =========================================================
# COMBINE ALL OFFENSIVE METRICS
# =========================================================

def build_offensive_metrics(pbp, scrimmage):

    efficiency = build_offensive_efficiency_metrics(scrimmage)
    downs = build_offensive_down_conversion_metrics(pbp)
    red_zone = build_offensive_red_zone_metrics(pbp)
    early_downs = build_offensive_early_down_metrics(scrimmage)
    explosive_plays = build_offensive_explosive_play_metrics(scrimmage)
    turnovers = build_offensive_turnover_metrics(pbp)
    pass_protection = build_offensive_pass_protection_metrics(pbp)

    metric_tables = [
        downs,
        red_zone,
        early_downs,
        explosive_plays,
        turnovers,
        pass_protection
    ]

    metrics = efficiency

    for table in metric_tables:
        metrics = metrics.join(
            table,
            on="team",
            how="left"
        )

    return metrics.sort("team")
