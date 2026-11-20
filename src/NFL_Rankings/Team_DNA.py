
import polars as pl


# =========================================================
# OFFENSIVE TENDENCIES
# =========================================================

def build_offensive_tendency_metrics(scrimmage):

    metrics = (
        scrimmage
        .group_by("posteam")
        .agg(
            # Overall play selection
            pl.len().alias("dna_offensive_plays"),

            (pl.col("play_type") == "pass")
            .sum()
            .alias("dna_pass_plays"),

            (pl.col("play_type") == "run")
            .sum()
            .alias("dna_rush_plays"),

            # Formation and tempo tendencies
            pl.col("shotgun").mean().alias("dna_shotgun_rate"),
            pl.col("no_huddle").mean().alias("dna_no_huddle_rate"),

            # Passing tendencies
            pl.col("pass_length")
            .filter(pl.col("play_type") == "pass")
            .count()
            .alias("dna_pass_depth_plays"),

            (pl.col("pass_length") == "short")
            .sum()
            .alias("dna_short_passes"),

            (pl.col("pass_length") == "deep")
            .sum()
            .alias("dna_deep_passes"),

            pl.col("pass_location")
            .filter(pl.col("play_type") == "pass")
            .eq("left")
            .sum()
            .alias("dna_pass_left"),

            pl.col("pass_location")
            .filter(pl.col("play_type") == "pass")
            .eq("middle")
            .sum()
            .alias("dna_pass_middle"),

            pl.col("pass_location")
            .filter(pl.col("play_type") == "pass")
            .eq("right")
            .sum()
            .alias("dna_pass_right"),

            # Rushing tendencies
            pl.col("run_location")
            .filter(pl.col("play_type") == "run")
            .eq("left")
            .sum()
            .alias("dna_run_left"),

            pl.col("run_location")
            .filter(pl.col("play_type") == "run")
            .eq("middle")
            .sum()
            .alias("dna_run_middle"),

            pl.col("run_location")
            .filter(pl.col("play_type") == "run")
            .eq("right")
            .sum()
            .alias("dna_run_right"),

            pl.col("run_gap")
            .filter(pl.col("play_type") == "run")
            .eq("guard")
            .sum()
            .alias("dna_run_guard"),

            pl.col("run_gap")
            .filter(pl.col("play_type") == "run")
            .eq("tackle")
            .sum()
            .alias("dna_run_tackle"),

            pl.col("run_gap")
            .filter(pl.col("play_type") == "run")
            .eq("end")
            .sum()
            .alias("dna_run_end"),
        )
        .rename({"posteam": "team"})
    )

    # Calculate usage rates using the relevant sample sizes.
    metrics = metrics.with_columns(
        (
            pl.col("dna_pass_plays")
            / pl.col("dna_offensive_plays")
        ).alias("dna_pass_rate"),

        (
            pl.col("dna_rush_plays")
            / pl.col("dna_offensive_plays")
        ).alias("dna_rush_rate"),

        (
            pl.col("dna_short_passes")
            / pl.col("dna_pass_depth_plays")
        ).alias("dna_short_pass_rate"),

        (
            pl.col("dna_deep_passes")
            / pl.col("dna_pass_depth_plays")
        ).alias("dna_deep_pass_rate"),

        (
            pl.col("dna_pass_left")
            / pl.col("dna_pass_depth_plays")
        ).alias("dna_pass_left_rate"),

        (
            pl.col("dna_pass_middle")
            / pl.col("dna_pass_depth_plays")
        ).alias("dna_pass_middle_rate"),

        (
            pl.col("dna_pass_right")
            / pl.col("dna_pass_depth_plays")
        ).alias("dna_pass_right_rate"),

        (
            pl.col("dna_run_left")
            / pl.col("dna_rush_plays")
        ).alias("dna_run_left_rate"),

        (
            pl.col("dna_run_middle")
            / pl.col("dna_rush_plays")
        ).alias("dna_run_middle_rate"),

        (
            pl.col("dna_run_right")
            / pl.col("dna_rush_plays")
        ).alias("dna_run_right_rate"),

        (
            pl.col("dna_run_guard")
            / pl.col("dna_rush_plays")
        ).alias("dna_run_guard_rate"),

        (
            pl.col("dna_run_tackle")
            / pl.col("dna_rush_plays")
        ).alias("dna_run_tackle_rate"),

        (
            pl.col("dna_run_end")
            / pl.col("dna_rush_plays")
        ).alias("dna_run_end_rate"),
    )

    return metrics.sort("team")

# =========================================================
# SITUATIONAL OFFENSE
# =========================================================

def build_offensive_situational_metrics(pbp):

    # -----------------------------------------------------
    # THIRD-DOWN OFFENSE
    # -----------------------------------------------------

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
            pl.len().alias("dna_third_down_attempts"),
            pl.col("third_down_converted")
            .sum()
            .alias("dna_third_down_conversions")
        )
        .with_columns(
            (
                pl.col("dna_third_down_conversions")
                / pl.col("dna_third_down_attempts")
            ).alias("dna_third_down_conversion_rate")
        )
        .rename({"posteam": "team"})
    )

    # -----------------------------------------------------
    # FOURTH-DOWN OFFENSE
    # -----------------------------------------------------

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
            pl.len().alias("dna_fourth_down_attempts"),
            pl.col("fourth_down_converted")
            .sum()
            .alias("dna_fourth_down_conversions")
        )
        .with_columns(
            (
                pl.col("dna_fourth_down_conversions")
                / pl.col("dna_fourth_down_attempts")
            ).alias("dna_fourth_down_conversion_rate")
        )
        .rename({"posteam": "team"})
    )

    # -----------------------------------------------------
    # RED-ZONE OFFENSE
    # -----------------------------------------------------

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
            pl.col("field_goal_result")
            .is_in(["made"])
            .any()
            .alias("field_goal_made")
        )
    )

    red_zone_metrics = (
        drive_results
        .group_by("posteam")
        .agg(
            pl.len().alias("dna_red_zone_trips"),
            pl.col("touchdown")
            .sum()
            .alias("dna_red_zone_touchdowns"),
            pl.col("field_goal_made")
            .sum()
            .alias("dna_red_zone_field_goals")
        )
        .with_columns(
            (
                pl.col("dna_red_zone_touchdowns")
                / pl.col("dna_red_zone_trips")
            ).alias("dna_red_zone_td_rate"),

            (
                (
                    pl.col("dna_red_zone_touchdowns")
                    + pl.col("dna_red_zone_field_goals")
                )
                / pl.col("dna_red_zone_trips")
            ).alias("dna_red_zone_scoring_rate")
        )
        .rename({"posteam": "team"})
    )

    # -----------------------------------------------------
    # COMBINE SITUATIONAL METRICS
    # -----------------------------------------------------

    return (
        third_down_metrics
        .join(fourth_down_metrics, on="team", how="full", coalesce=True)
        .join(red_zone_metrics, on="team", how="full", coalesce=True)
        .sort("team")
    )


# =========================================================
# DEFENSIVE TENDENCIES
# =========================================================

def build_defensive_tendency_metrics(scrimmage):

    metrics = (
        scrimmage
        .group_by("defteam")
        .agg(
            # Opponent play selection
            pl.len().alias("dna_defensive_plays"),

            (pl.col("play_type") == "pass")
            .sum()
            .alias("dna_pass_plays_faced"),

            (pl.col("play_type") == "run")
            .sum()
            .alias("dna_rush_plays_faced"),

            # Opponent formation and tempo
            pl.col("shotgun").mean().alias("dna_shotgun_rate_faced"),
            pl.col("no_huddle").mean().alias("dna_no_huddle_rate_faced"),

            # Opponent passing tendencies
            pl.col("pass_length")
            .filter(pl.col("play_type") == "pass")
            .count()
            .alias("dna_pass_depth_plays_faced"),

            (pl.col("pass_length") == "short")
            .sum()
            .alias("dna_short_passes_faced"),

            (pl.col("pass_length") == "deep")
            .sum()
            .alias("dna_deep_passes_faced"),

            # Opponent rushing tendencies
            (pl.col("run_location") == "left")
            .sum()
            .alias("dna_runs_left_faced"),

            (pl.col("run_location") == "middle")
            .sum()
            .alias("dna_runs_middle_faced"),

            (pl.col("run_location") == "right")
            .sum()
            .alias("dna_runs_right_faced"),
        )
        .rename({"defteam": "team"})
    )

    metrics = metrics.with_columns(
        (
            pl.col("dna_pass_plays_faced")
            / pl.col("dna_defensive_plays")
        ).alias("dna_pass_rate_faced"),

        (
            pl.col("dna_rush_plays_faced")
            / pl.col("dna_defensive_plays")
        ).alias("dna_rush_rate_faced"),

        (
            pl.col("dna_short_passes_faced")
            / pl.col("dna_pass_depth_plays_faced")
        ).alias("dna_short_pass_rate_faced"),

        (
            pl.col("dna_deep_passes_faced")
            / pl.col("dna_pass_depth_plays_faced")
        ).alias("dna_deep_pass_rate_faced"),

        (
            pl.col("dna_runs_left_faced")
            / pl.col("dna_rush_plays_faced")
        ).alias("dna_runs_left_rate_faced"),

        (
            pl.col("dna_runs_middle_faced")
            / pl.col("dna_rush_plays_faced")
        ).alias("dna_runs_middle_rate_faced"),

        (
            pl.col("dna_runs_right_faced")
            / pl.col("dna_rush_plays_faced")
        ).alias("dna_runs_right_rate_faced"),
    )

    return metrics.sort("team")


# =========================================================
# SITUATIONAL DEFENSE
# =========================================================

def build_defensive_situational_metrics(pbp):

    # -----------------------------------------------------
    # THIRD-DOWN DEFENSE
    # -----------------------------------------------------

    third_downs = pbp.filter(
        (pl.col("down") == 3)
        & pl.col("defteam").is_not_null()
        & pl.col("third_down_converted").is_not_null()
        & pl.col("play_type").is_in(["pass", "run"])
    )

    third_down_metrics = (
        third_downs
        .group_by("defteam")
        .agg(
            pl.len().alias("dna_third_down_attempts_allowed"),
            pl.col("third_down_converted")
            .sum()
            .alias("dna_third_down_conversions_allowed")
        )
        .with_columns(
            (
                pl.col("dna_third_down_conversions_allowed")
                / pl.col("dna_third_down_attempts_allowed")
            ).alias("dna_third_down_conversion_rate_allowed")
        )
        .rename({"defteam": "team"})
    )

    # -----------------------------------------------------
    # FOURTH-DOWN DEFENSE
    # -----------------------------------------------------

    fourth_downs = pbp.filter(
        (pl.col("down") == 4)
        & pl.col("defteam").is_not_null()
        & pl.col("fourth_down_converted").is_not_null()
        & pl.col("play_type").is_in(["pass", "run"])
    )

    fourth_down_metrics = (
        fourth_downs
        .group_by("defteam")
        .agg(
            pl.len().alias("dna_fourth_down_attempts_allowed"),
            pl.col("fourth_down_converted")
            .sum()
            .alias("dna_fourth_down_conversions_allowed")
        )
        .with_columns(
            (
                pl.col("dna_fourth_down_conversions_allowed")
                / pl.col("dna_fourth_down_attempts_allowed")
            ).alias("dna_fourth_down_conversion_rate_allowed")
        )
        .rename({"defteam": "team"})
    )

    # -----------------------------------------------------
    # RED-ZONE DEFENSE
    # -----------------------------------------------------

    red_zone_drives = (
        pbp.filter(
            (pl.col("yardline_100") <= 20)
            & (pl.col("yardline_100") >= 0)
            & pl.col("posteam").is_not_null()
            & pl.col("defteam").is_not_null()
            & pl.col("game_id").is_not_null()
            & pl.col("drive").is_not_null()
        )
        .select(["posteam", "defteam", "game_id", "drive"])
        .unique()
    )

    drive_results = (
        pbp.join(
            red_zone_drives,
            on=["posteam", "defteam", "game_id", "drive"],
            how="inner"
        )
        .group_by(["posteam", "defteam", "game_id", "drive"])
        .agg(
            pl.col("touchdown").max().alias("touchdown"),
            pl.col("field_goal_result")
            .is_in(["made"])
            .any()
            .alias("field_goal_made")
        )
    )

    red_zone_metrics = (
        drive_results
        .group_by("defteam")
        .agg(
            pl.len().alias("dna_red_zone_trips_allowed"),
            pl.col("touchdown")
            .sum()
            .alias("dna_red_zone_touchdowns_allowed"),
            pl.col("field_goal_made")
            .sum()
            .alias("dna_red_zone_field_goals_allowed")
        )
        .with_columns(
            (
                pl.col("dna_red_zone_touchdowns_allowed")
                / pl.col("dna_red_zone_trips_allowed")
            ).alias("dna_red_zone_td_rate_allowed"),

            (
                (
                    pl.col("dna_red_zone_touchdowns_allowed")
                    + pl.col("dna_red_zone_field_goals_allowed")
                )
                / pl.col("dna_red_zone_trips_allowed")
            ).alias("dna_red_zone_scoring_rate_allowed")
        )
        .rename({"defteam": "team"})
    )

    # -----------------------------------------------------
    # COMBINE SITUATIONAL METRICS
    # -----------------------------------------------------

    return (
        third_down_metrics
        .join(fourth_down_metrics, on="team", how="full", coalesce=True)
        .join(red_zone_metrics, on="team", how="full", coalesce=True)
        .sort("team")
    )




# =========================================================
# TEAM DNA PERFORMANCE BY FIELD ZONE
# =========================================================

def build_field_zone_performance_metrics(scrimmage):

    # -----------------------------------------------------
    # PASSING ZONES
    # Short: 10 air yards or fewer
    # Deep: More than 10 air yards
    # -----------------------------------------------------

    pass_zones = {
        "short_left": (
            (pl.col("air_yards") <= 10)
            & (pl.col("pass_location") == "left")
        ),
        "short_middle": (
            (pl.col("air_yards") <= 10)
            & (pl.col("pass_location") == "middle")
        ),
        "short_right": (
            (pl.col("air_yards") <= 10)
            & (pl.col("pass_location") == "right")
        ),
        "deep_left": (
            (pl.col("air_yards") > 10)
            & (pl.col("pass_location") == "left")
        ),
        "deep_middle": (
            (pl.col("air_yards") > 10)
            & (pl.col("pass_location") == "middle")
        ),
        "deep_right": (
            (pl.col("air_yards") > 10)
            & (pl.col("pass_location") == "right")
        ),
    }

    passing = scrimmage.filter(
        (pl.col("play_type") == "pass")
        & pl.col("air_yards").is_not_null()
        & pl.col("pass_location").is_not_null()
    )

    offensive_pass_metrics = []

    for zone, condition in pass_zones.items():
        offensive_pass_metrics.extend([
            pl.col("epa")
            .filter(condition)
            .mean()
            .alias(f"dna_off_pass_epa_{zone}"),

            pl.col("epa")
            .filter(condition)
            .count()
            .alias(f"dna_off_pass_plays_{zone}"),
        ])

    offensive_passing = (
        passing
        .group_by("posteam")
        .agg(offensive_pass_metrics)
        .rename({"posteam": "team"})
    )

    defensive_pass_metrics = []

    for zone, condition in pass_zones.items():
        defensive_pass_metrics.extend([
            pl.col("epa")
            .filter(condition)
            .mean()
            .alias(f"dna_def_pass_epa_allowed_{zone}"),

            pl.col("epa")
            .filter(condition)
            .count()
            .alias(f"dna_def_pass_plays_{zone}"),
        ])

    defensive_passing = (
        passing
        .group_by("defteam")
        .agg(defensive_pass_metrics)
        .rename({"defteam": "team"})
    )

    # -----------------------------------------------------
    # RUSHING ZONES
    # -----------------------------------------------------

    run_zones = {
        "left": pl.col("run_location") == "left",
        "middle": pl.col("run_location") == "middle",
        "right": pl.col("run_location") == "right",
    }

    rushing = scrimmage.filter(
        (pl.col("play_type") == "run")
        & pl.col("run_location").is_not_null()
    )

    offensive_run_metrics = []

    for zone, condition in run_zones.items():
        offensive_run_metrics.extend([
            pl.col("epa")
            .filter(condition)
            .mean()
            .alias(f"dna_off_rush_epa_{zone}"),

            pl.col("epa")
            .filter(condition)
            .count()
            .alias(f"dna_off_rush_plays_{zone}"),
        ])

    offensive_rushing = (
        rushing
        .group_by("posteam")
        .agg(offensive_run_metrics)
        .rename({"posteam": "team"})
    )

    defensive_run_metrics = []

    for zone, condition in run_zones.items():
        defensive_run_metrics.extend([
            pl.col("epa")
            .filter(condition)
            .mean()
            .alias(f"dna_def_rush_epa_allowed_{zone}"),

            pl.col("epa")
            .filter(condition)
            .count()
            .alias(f"dna_def_rush_plays_{zone}"),
        ])

    defensive_rushing = (
        rushing
        .group_by("defteam")
        .agg(defensive_run_metrics)
        .rename({"defteam": "team"})
    )

    # -----------------------------------------------------
    # COMBINE ALL PERFORMANCE METRICS
    # -----------------------------------------------------

    return (
        offensive_passing
        .join(defensive_passing, on="team", how="full", coalesce=True)
        .join(offensive_rushing, on="team", how="full", coalesce=True)
        .join(defensive_rushing, on="team", how="full", coalesce=True)
        .sort("team")
    )
