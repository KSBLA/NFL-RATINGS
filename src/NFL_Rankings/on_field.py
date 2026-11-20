
import polars as pl


# ---------------------------------------------------------
# NFL TEAM DIVISIONS
# ---------------------------------------------------------

TEAM_DIVISIONS = {
    "BUF": "AFC East",
    "MIA": "AFC East",
    "NE": "AFC East",
    "NYJ": "AFC East",

    "BAL": "AFC North",
    "CIN": "AFC North",
    "CLE": "AFC North",
    "PIT": "AFC North",

    "HOU": "AFC South",
    "IND": "AFC South",
    "JAX": "AFC South",
    "TEN": "AFC South",

    "DEN": "AFC West",
    "KC": "AFC West",
    "LV": "AFC West",
    "LAC": "AFC West",

    "DAL": "NFC East",
    "NYG": "NFC East",
    "PHI": "NFC East",
    "WAS": "NFC East",

    "CHI": "NFC North",
    "DET": "NFC North",
    "GB": "NFC North",
    "MIN": "NFC North",

    "ATL": "NFC South",
    "CAR": "NFC South",
    "NO": "NFC South",
    "TB": "NFC South",

    "ARI": "NFC West",
    "LA": "NFC West",
    "SF": "NFC West",
    "SEA": "NFC West",
}


def build_game_records(pbp):

    games = (
        pbp
        .select([
            "game_id",
            "week",
            "home_team",
            "away_team",
            "home_score",
            "away_score"
        ])
        .unique(subset=["game_id"], keep="first")
    )

    # Home team records
    home_records = games.select([
        pl.col("home_team").alias("team"),
        pl.col("away_team").alias("opponent"),
        pl.lit("home").alias("game_location"),
        "game_id",
        "week",
        pl.col("home_score").alias("points_scored"),
        pl.col("away_score").alias("points_allowed")
    ])

    # Away team records
    away_records = games.select([
        pl.col("away_team").alias("team"),
        pl.col("home_team").alias("opponent"),
        pl.lit("away").alias("game_location"),
        "game_id",
        "week",
        pl.col("away_score").alias("points_scored"),
        pl.col("home_score").alias("points_allowed")
    ])

    game_records = pl.concat([home_records, away_records])

    # Add division information
    divisions = pl.DataFrame({
        "team": list(TEAM_DIVISIONS.keys()),
        "division": list(TEAM_DIVISIONS.values())
    })

    game_records = (
        game_records
        .join(divisions, on="team", how="left")
        .join(
            divisions.rename({
                "team": "opponent",
                "division": "opponent_division"
            }),
            on="opponent",
            how="left"
        )
        .with_columns([
            (pl.col("points_scored") > pl.col("points_allowed"))
            .cast(pl.Int64).alias("wins"),

            (pl.col("points_scored") < pl.col("points_allowed"))
            .cast(pl.Int64).alias("losses"),

            (pl.col("points_scored") == pl.col("points_allowed"))
            .cast(pl.Int64).alias("ties"),

            (pl.col("points_scored") - pl.col("points_allowed"))
            .alias("point_differential")
        ])
        .with_columns(
            (pl.col("division") == pl.col("opponent_division"))
            .alias("is_division_game")
        )
    )

    # Calculate each team's overall record
    team_records = (
        game_records
        .group_by("team")
        .agg([
            pl.col("wins").sum().alias("opponent_total_wins"),
            pl.col("losses").sum().alias("opponent_total_losses"),
            pl.col("ties").sum().alias("opponent_total_ties"),
            pl.len().alias("opponent_total_games")
        ])
    )

    # Attach each opponent's record to the game
    game_records = game_records.join(
        team_records.rename({"team": "opponent"}),
        on="opponent",
        how="left"
    )

    # Remove the head-to-head game from the opponent's record
    game_records = game_records.with_columns([
        (pl.col("opponent_total_games") - 1)
        .alias("opponent_games_excluding_game"),

        (pl.col("opponent_total_wins") - pl.col("losses"))
        .alias("opponent_wins_excluding_game"),

        (pl.col("opponent_total_losses") - pl.col("wins"))
        .alias("opponent_losses_excluding_game"),

        (pl.col("opponent_total_ties") - pl.col("ties"))
        .alias("opponent_ties_excluding_game")
    ])

    game_records = game_records.with_columns(
        pl.when(pl.col("opponent_games_excluding_game") > 0)
        .then(
            (
                pl.col("opponent_wins_excluding_game")
                + 0.5 * pl.col("opponent_ties_excluding_game")
            ) / pl.col("opponent_games_excluding_game")
        )
        .otherwise(None)
        .alias("opponent_win_percentage_excluding_game")
    )

    # Identify quality wins and bad losses
    game_records = game_records.with_columns([
        (
            (pl.col("wins") == 1)
            & (pl.col("opponent_win_percentage_excluding_game") >= 0.500)
        ).alias("is_quality_win"),

        (
            (pl.col("losses") == 1)
            & (pl.col("opponent_win_percentage_excluding_game") < 0.400)
        ).alias("is_bad_loss")
    ])

    return game_records.sort(["team", "week"])


def build_on_field_metrics(pbp):

    game_records = build_game_records(pbp)

    on_field_metrics = (
        game_records
        .group_by("team")
        .agg([

            # Overall results
            pl.len().alias("on_field_games_played"),

            pl.col("wins").sum().alias("on_field_wins"),

            pl.col("losses").sum().alias("on_field_losses"),

            pl.col("ties").sum().alias("on_field_ties"),

            # Overall scoring
            pl.col("points_scored")
            .sum()
            .alias("on_field_points_scored"),

            pl.col("points_allowed")
            .sum()
            .alias("on_field_points_allowed"),

            pl.col("points_scored")
            .mean()
            .alias("on_field_points_scored_per_game"),

            pl.col("points_allowed")
            .mean()
            .alias("on_field_points_allowed_per_game"),

            # Overall point differential
            pl.col("point_differential")
            .sum()
            .alias("on_field_total_point_differential"),

            pl.col("point_differential")
            .mean()
            .alias("on_field_avg_point_differential"),

            pl.col("point_differential")
            .abs()
            .mean()
            .alias("on_field_avg_absolute_point_differential"),

            # Division results
            pl.col("is_division_game")
            .sum()
            .alias("division_games_played"),

            pl.when(pl.col("is_division_game"))
            .then(pl.col("wins"))
            .otherwise(0)
            .sum()
            .alias("division_wins"),

            pl.when(pl.col("is_division_game"))
            .then(pl.col("losses"))
            .otherwise(0)
            .sum()
            .alias("division_losses"),

            pl.when(pl.col("is_division_game"))
            .then(pl.col("ties"))
            .otherwise(0)
            .sum()
            .alias("division_ties"),

            pl.when(pl.col("is_division_game"))
            .then(pl.col("points_scored"))
            .otherwise(0)
            .sum()
            .alias("division_points_scored"),

            pl.when(pl.col("is_division_game"))
            .then(pl.col("points_allowed"))
            .otherwise(0)
            .sum()
            .alias("division_points_allowed"),

            pl.when(pl.col("is_division_game"))
            .then(pl.col("point_differential"))
            .otherwise(0)
            .sum()
            .alias("division_point_differential"),

            # Strength of wins
            pl.col("opponent_win_percentage_excluding_game")
            .filter(pl.col("wins") == 1)
            .mean()
            .alias("on_field_strength_of_wins"),

            # Quality wins
            pl.col("is_quality_win")
            .cast(pl.Int64)
            .sum()
            .alias("on_field_quality_wins"),

            # Bad losses
            pl.col("is_bad_loss")
            .cast(pl.Int64)
            .sum()
            .alias("on_field_bad_losses")

        ])
        .with_columns([

            (
                (pl.col("on_field_wins") + 0.5 * pl.col("on_field_ties"))
                / pl.col("on_field_games_played")
            ).alias("on_field_win_percentage"),

            (
                (pl.col("division_wins") + 0.5 * pl.col("division_ties"))
                / pl.col("division_games_played")
            ).alias("division_win_percentage")

        ])
        .sort("team")
    )

    return on_field_metrics
