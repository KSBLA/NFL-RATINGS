
import polars as pl


# ---------------------------------------------------------
# TEAM PENALTY PERFORMANCE
# ---------------------------------------------------------

def build_penalty_metrics(pbp):

    penalties = pbp.filter(
        (pl.col("penalty") == 1)
        & pl.col("penalty_team").is_not_null()
    )

    metrics = (
        penalties.group_by("penalty_team")
        .agg(
            pl.len().alias("penalty_flags"),

            pl.col("penalty_yards")
            .sum()
            .alias("penalty_yards"),

            pl.col("first_down_penalty")
            .fill_null(0)
            .sum()
            .alias("first_down_penalties")
        )
        .with_columns(
            (
                pl.col("penalty_yards")
                / pl.col("penalty_flags")
            ).alias("penalty_yards_per_flag")
        )
        .rename({"penalty_team": "team"})
        .sort("team")
    )

    return metrics
