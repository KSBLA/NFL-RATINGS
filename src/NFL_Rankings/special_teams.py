
import polars as pl


# ---------------------------------------------------------
# FIELD GOAL METRICS
# ---------------------------------------------------------

def build_field_goal_metrics(pbp):

    plays = pbp.filter(
        pl.col("play_type") == "field_goal"
    )

    return (
        plays.group_by("posteam")
        .agg(
            pl.len().alias("fg_attempts"),

            (pl.col("field_goal_result") == "made")
            .sum()
            .alias("fg_made"),

            (pl.col("field_goal_result") == "missed")
            .sum()
            .alias("fg_missed"),

            (pl.col("field_goal_result") == "blocked")
            .sum()
            .alias("fg_blocked"),

            pl.col("kick_distance")
            .mean()
            .alias("avg_fg_distance"),

            pl.col("kick_distance")
            .max()
            .alias("longest_fg_attempt")
        )
        .with_columns(
            (
                pl.col("fg_made") / pl.col("fg_attempts")
            ).alias("fg_make_rate")
        )
        .rename({"posteam": "team"})
    )


# ---------------------------------------------------------
# EXTRA POINT METRICS
# ---------------------------------------------------------

def build_extra_point_metrics(pbp):

    plays = pbp.filter(
        pl.col("play_type") == "extra_point"
    )

    return (
        plays.group_by("posteam")
        .agg(
            pl.len().alias("xp_attempts"),

            (pl.col("extra_point_result") == "good")
            .sum()
            .alias("xp_made"),

            (pl.col("extra_point_result") == "failed")
            .sum()
            .alias("xp_failed"),

            (pl.col("extra_point_result") == "blocked")
            .sum()
            .alias("xp_blocked"),

            pl.col("extra_point_result")
            .is_not_null()
            .sum()
            .alias("xp_known_results")
        )
        .with_columns(
            (
                pl.col("xp_made") / pl.col("xp_known_results")
            ).alias("xp_success_rate")
        )
        .rename({"posteam": "team"})
    )


# ---------------------------------------------------------
# PUNTING METRICS
# ---------------------------------------------------------

def build_punting_metrics(pbp):

    plays = pbp.filter(
        pl.col("play_type") == "punt"
    )

    return (
        plays.group_by("posteam")
        .agg(
            pl.len().alias("punt_attempts"),

            pl.col("punt_inside_twenty")
            .fill_null(0)
            .sum()
            .alias("punts_inside_twenty"),

            pl.col("punt_in_endzone")
            .fill_null(0)
            .sum()
            .alias("punts_in_endzone"),

            pl.col("punt_out_of_bounds")
            .fill_null(0)
            .sum()
            .alias("punts_out_of_bounds"),

            pl.col("punt_downed")
            .fill_null(0)
            .sum()
            .alias("punts_downed"),

            pl.col("punt_fair_catch")
            .fill_null(0)
            .sum()
            .alias("punt_fair_catches"),

            pl.col("punt_blocked")
            .fill_null(0)
            .sum()
            .alias("punts_blocked"),

            pl.col("touchback")
            .fill_null(0)
            .sum()
            .alias("punt_touchbacks")
        )
        .with_columns(
            (
                pl.col("punts_inside_twenty")
                / pl.col("punt_attempts")
            ).alias("punt_inside_twenty_rate"),

            (
                pl.col("punt_touchbacks")
                / pl.col("punt_attempts")
            ).alias("punt_touchback_rate"),

            (
                pl.col("punts_blocked")
                / pl.col("punt_attempts")
            ).alias("punt_block_rate")
        )
        .rename({"posteam": "team"})
    )

# ---------------------------------------------------------
# KICKOFF METRICS
# ---------------------------------------------------------

def build_kickoff_metrics(pbp):

    plays = pbp.filter(
        (pl.col("play_type") == "kickoff")
        & pl.col("defteam").is_not_null()
    )

    return (
        plays.group_by("defteam")
        .agg(
            pl.len().alias("kickoff_attempts"),

            pl.col("touchback")
            .fill_null(0)
            .sum()
            .alias("kickoff_touchbacks"),

            pl.col("kickoff_inside_twenty")
            .fill_null(0)
            .sum()
            .alias("kickoffs_inside_twenty"),

            pl.col("kickoff_in_endzone")
            .fill_null(0)
            .sum()
            .alias("kickoffs_in_endzone"),

            pl.col("kickoff_out_of_bounds")
            .fill_null(0)
            .sum()
            .alias("kickoffs_out_of_bounds"),

            pl.col("kickoff_downed")
            .fill_null(0)
            .sum()
            .alias("kickoffs_downed"),

            pl.col("kickoff_fair_catch")
            .fill_null(0)
            .sum()
            .alias("kickoff_fair_catches")
        )
        .with_columns(
            (
                pl.col("kickoff_touchbacks")
                / pl.col("kickoff_attempts")
            ).alias("kickoff_touchback_rate")
        )
        .rename({"defteam": "team"})
    )


# ---------------------------------------------------------
# PUNT RETURN METRICS
# ---------------------------------------------------------

def build_punt_return_metrics(pbp):

    plays = pbp.filter(
        (pl.col("play_type") == "punt")
        & pl.col("return_team").is_not_null()
    )

    return (
        plays.group_by("return_team")
        .agg(
            pl.len().alias("punt_return_opportunities"),

            pl.col("return_yards")
            .fill_null(0)
            .sum()
            .alias("punt_return_yards"),

            pl.col("return_touchdown")
            .fill_null(0)
            .sum()
            .alias("punt_return_touchdowns")
        )
        .with_columns(
            (
                pl.col("punt_return_yards")
                / pl.col("punt_return_opportunities")
            ).alias("punt_return_yards_per_opportunity")
        )
        .rename({"return_team": "team"})
    )


# ---------------------------------------------------------
# KICKOFF RETURN METRICS
# ---------------------------------------------------------

def build_kickoff_return_metrics(pbp):

    plays = pbp.filter(
        (pl.col("play_type") == "kickoff")
        & pl.col("return_team").is_not_null()
    )

    return (
        plays.group_by("return_team")
        .agg(
            pl.len().alias("kickoff_return_opportunities"),

            pl.col("return_yards")
            .fill_null(0)
            .sum()
            .alias("kickoff_return_yards"),

            pl.col("return_touchdown")
            .fill_null(0)
            .sum()
            .alias("kickoff_return_touchdowns")
        )
        .with_columns(
            (
                pl.col("kickoff_return_yards")
                / pl.col("kickoff_return_opportunities")
            ).alias("kickoff_return_yards_per_opportunity")
        )
        .rename({"return_team": "team"})
    )


# ---------------------------------------------------------
# COMBINE ALL SPECIAL TEAMS METRICS
# ---------------------------------------------------------

def build_special_teams_metrics(pbp):

    teams = (
        pbp
        .select(
            pl.col("posteam")
            .drop_nulls()
            .unique()
            .alias("team")
        )
        .sort("team")
    )

    metrics = [
        build_field_goal_metrics(pbp),
        build_extra_point_metrics(pbp),
        build_punting_metrics(pbp),
        build_kickoff_metrics(pbp),
        build_punt_return_metrics(pbp),
        build_kickoff_return_metrics(pbp)
    ]

    result = teams

    for metric in metrics:
        result = result.join(
            metric,
            on="team",
            how="left"
        )

    metric_columns = [
        column for column in result.columns
        if column != "team"
    ]

    result = result.with_columns(
        [
            pl.col(column).fill_null(0)
            for column in metric_columns
        ]
    )

    return result.sort("team")


# ---------------------------------------------------------
# TEST SPECIAL TEAMS METRICS
# ---------------------------------------------------------

if __name__ == "__main__":

    from data import load_play_by_play

    print("=" * 70)
    print("BUILDING SPECIAL TEAMS METRICS")
    print("=" * 70)

    pbp = load_play_by_play()

    special_teams_metrics = build_special_teams_metrics(pbp)

    print(f"\nTeams: {special_teams_metrics.height}")
    print(
        f"Special teams metrics: "
        f"{len(special_teams_metrics.columns) - 1}"
    )

    print("\nFIRST FIVE TEAMS")
    print(special_teams_metrics.head(5))

    print("\nSPECIAL TEAMS METRICS COMPLETED SUCCESSFULLY")
