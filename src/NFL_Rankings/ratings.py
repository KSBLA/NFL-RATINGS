
import polars as pl


# =========================================================
# SHARED HELPER FUNCTIONS
# =========================================================

def _add_percentile_score(
    df,
    metric,
    higher_is_better,
    score_name
):
    """
    Convert a metric into a 0-100 percentile score.
    Best team receives 100; worst receives 0.
    """

    team_count = df.height

    if team_count < 2:
        raise ValueError(
            "At least two teams are required for percentile scoring."
        )

    rank = pl.col(metric).rank(
        method="average",
        descending=not higher_is_better
    )

    return df.with_columns(
        (
            (rank - 1) / (team_count - 1) * 100
        ).alias(score_name)
    )


def _add_shrunk_rate(
    df,
    rate_column,
    opportunity_column,
    prior_opportunities,
    adjusted_column
):
    """
    Adjust rates for small sample sizes by shrinking them
    toward the opportunity-weighted league average.
    """

    league_rate = (
        (
            pl.col(rate_column) * pl.col(opportunity_column)
        ).sum()
        /
        pl.col(opportunity_column).sum()
    )

    return df.with_columns(
        (
            (
                pl.col(rate_column) * pl.col(opportunity_column)
                + league_rate * prior_opportunities
            )
            /
            (
                pl.col(opportunity_column)
                + prior_opportunities
            )
        ).alias(adjusted_column)
    )


def _validate_required_columns(df, required, foundation):

    missing = [
        column for column in required
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            f"{foundation} is missing required columns: {missing}"
        )


def _validate_32_teams(df, foundation):

    if "team" not in df.columns:
        raise ValueError(f"{foundation} is missing the team column.")

    if df.get_column("team").n_unique() != 32:
        raise ValueError(
            f"{foundation} must contain exactly 32 teams."
        )

    if df.height != 32:
        raise ValueError(
            f"{foundation} must contain exactly 32 rows."
        )

    if df.get_column("team").null_count() > 0:
        raise ValueError(
            f"{foundation} contains missing team names."
        )


def _validate_finite_nonnegative(df, columns, foundation):

    for column in columns:

        if df.get_column(column).null_count() > 0:
            raise ValueError(
                f"{foundation}: {column} contains null values."
            )

        invalid = df.filter(
            ~pl.col(column).is_finite()
            | (pl.col(column) < 0)
        )

        if invalid.height > 0:
            raise ValueError(
                f"{foundation}: {column} contains "
                "negative or non-finite values."
            )


def _validate_rates(df, columns, foundation):

    for column in columns:

        invalid = df.filter(
            pl.col(column).is_null()
            | ~pl.col(column).is_finite()
            | (pl.col(column) < 0)
            | (pl.col(column) > 1)
        )

        if invalid.height > 0:
            raise ValueError(
                f"{foundation}: {column} must be between 0 and 1."
            )


# =========================================================
# OFFENSIVE RATING
# =========================================================

def validate_offensive_metrics(df):

    print("\nVALIDATING OFFENSIVE METRICS")

    required = [
        "offensive_plays",
        "off_epa_per_play",
        "off_success_rate",
        "off_yards_per_play",
        "pass_epa_per_play",
        "rush_epa_per_play",
        "pass_plays",
        "third_down_attempts",
        "third_down_conversion_rate",
        "fourth_down_attempts",
        "fourth_down_conversion_rate",
        "red_zone_trips",
        "red_zone_td_rate",
        "red_zone_scoring_rate",
        "explosive_pass_rate",
        "explosive_rush_rate",
        "interceptions_thrown",
        "fumbles_lost",
        "total_giveaways",
        "sack_rate_allowed",
        "qb_hit_rate_allowed",
    ]

    _validate_required_columns(df, required, "Offense")
    _validate_32_teams(df, "Offense")

    nonnegative = [
        "offensive_plays",
        "pass_plays",
        "third_down_attempts",
        "fourth_down_attempts",
        "red_zone_trips",
        "interceptions_thrown",
        "fumbles_lost",
        "total_giveaways",
    ]

    _validate_finite_nonnegative(df, nonnegative, "Offense")

    rates = [
        "off_success_rate",
        "third_down_conversion_rate",
        "fourth_down_conversion_rate",
        "red_zone_td_rate",
        "red_zone_scoring_rate",
        "explosive_pass_rate",
        "explosive_rush_rate",
        "sack_rate_allowed",
        "qb_hit_rate_allowed",
    ]

    _validate_rates(df, rates, "Offense")

    if (df["offensive_plays"] <= 0).any():
        raise ValueError("Offense contains zero offensive plays.")

    if (df["pass_plays"] <= 0).any():
        raise ValueError("Offense contains zero pass plays.")

    print("All required metrics are present and valid.")
    print("No zero denominators detected.")
    print("All percentage metrics are between 0 and 1.")
    print("\nOFFENSIVE METRIC VALIDATION PASSED.")


def build_offensive_rating(team_metrics):

    validate_offensive_metrics(team_metrics)

    df = team_metrics

    # Derive turnover rates
    df = df.with_columns(
        (
            pl.col("interceptions_thrown")
            / pl.col("pass_plays")
        ).alias("interception_rate"),

        (
            pl.col("fumbles_lost")
            / pl.col("offensive_plays")
        ).alias("fumble_lost_rate")
    )

    # Adjust low-sample conversion rates
    df = _add_shrunk_rate(
        df, "third_down_conversion_rate",
        "third_down_attempts", 20, "adj_third_down_rate"
    )

    df = _add_shrunk_rate(
        df, "fourth_down_conversion_rate",
        "fourth_down_attempts", 8, "adj_fourth_down_rate"
    )

    df = _add_shrunk_rate(
        df, "red_zone_td_rate",
        "red_zone_trips", 5, "adj_red_zone_td_rate"
    )

    df = _add_shrunk_rate(
        df, "red_zone_scoring_rate",
        "red_zone_trips", 5, "adj_red_zone_scoring_rate"
    )

    # Percentile scores
    metrics = [
        ("off_success_rate", True, "off_success_score"),
        ("off_yards_per_play", True, "off_yards_score"),
        ("pass_epa_per_play", True, "pass_epa_score"),
        ("rush_epa_per_play", True, "rush_epa_score"),
        ("adj_third_down_rate", True, "third_down_score"),
        ("adj_fourth_down_rate", True, "fourth_down_score"),
        ("adj_red_zone_td_rate", True, "red_zone_td_score"),
        ("adj_red_zone_scoring_rate", True, "red_zone_scoring_score"),
        ("explosive_pass_rate", True, "explosive_pass_score"),
        ("explosive_rush_rate", True, "explosive_rush_score"),
        ("interception_rate", False, "interception_score"),
        ("fumble_lost_rate", False, "fumble_score"),
        ("sack_rate_allowed", False, "sack_allowed_score"),
        ("qb_hit_rate_allowed", False, "qb_hit_allowed_score"),
    ]

    for metric, direction, score in metrics:
        df = _add_percentile_score(
            df, metric, direction, score
        )

    # Category scores
    df = df.with_columns(
        (
            (
                pl.col("off_success_score")
                + pl.col("off_yards_score")
            ) / 2
        ).alias("efficiency_score"),

        pl.col("pass_epa_score").alias("passing_score"),

        pl.col("rush_epa_score").alias("rushing_score"),

        (
            (
                pl.col("third_down_score")
                + pl.col("fourth_down_score")
            ) / 2
        ).alias("conversions_score"),

        (
            pl.col("red_zone_td_score") * 0.60
            + pl.col("red_zone_scoring_score") * 0.40
        ).alias("red_zone_score"),

        (
            (
                pl.col("explosive_pass_score")
                + pl.col("explosive_rush_score")
            ) / 2
        ).alias("explosive_plays_score"),

        (
            (
                pl.col("interception_score")
                + pl.col("fumble_score")
            ) / 2
        ).alias("ball_security_score"),

        (
            (
                pl.col("sack_allowed_score")
                + pl.col("qb_hit_allowed_score")
            ) / 2
        ).alias("pass_protection_score")
    )

    # Final offensive rating
    df = df.with_columns(
        (
            pl.col("efficiency_score") * 0.20
            + pl.col("passing_score") * 0.15
            + pl.col("rushing_score") * 0.10
            + pl.col("conversions_score") * 0.10
            + pl.col("red_zone_score") * 0.10
            + pl.col("explosive_plays_score") * 0.10
            + pl.col("ball_security_score") * 0.15
            + pl.col("pass_protection_score") * 0.10
        ).round(2).alias("offensive_rating")
    )

    return (
        df.select([
            "team",
            "efficiency_score",
            "passing_score",
            "rushing_score",
            "conversions_score",
            "red_zone_score",
            "explosive_plays_score",
            "ball_security_score",
            "pass_protection_score",
            "offensive_rating"
        ])
        .sort("offensive_rating", descending=True)
    )


# =========================================================
# DEFENSIVE RATING
# =========================================================

def validate_defensive_metrics(df):

    print("\nVALIDATING DEFENSIVE METRICS")

    required = [
        "defensive_plays",
        "def_epa_allowed_per_play",
        "def_success_rate_allowed",
        "def_yards_allowed_per_play",
        "pass_epa_allowed_per_play",
        "rush_epa_allowed_per_play",
        "def_early_down_success_allowed",
        "def_pass_plays_faced",
        "explosive_pass_rate_allowed",
        "explosive_rush_rate_allowed",
        "interceptions",
        "fumbles_recovered",
        "def_sack_rate",
        "def_non_sack_qb_hit_rate",
    ]

    _validate_required_columns(df, required, "Defense")
    _validate_32_teams(df, "Defense")

    nonnegative = [
        "defensive_plays",
        "def_pass_plays_faced",
        "interceptions",
        "fumbles_recovered",
    ]

    _validate_finite_nonnegative(df, nonnegative, "Defense")

    rates = [
        "def_success_rate_allowed",
        "def_early_down_success_allowed",
        "explosive_pass_rate_allowed",
        "explosive_rush_rate_allowed",
        "def_sack_rate",
        "def_non_sack_qb_hit_rate",
    ]

    _validate_rates(df, rates, "Defense")

    if (df["defensive_plays"] <= 0).any():
        raise ValueError("Defense contains zero defensive plays.")

    if (df["def_pass_plays_faced"] <= 0).any():
        raise ValueError("Defense contains zero pass plays faced.")

    if "total_takeaways" in df.columns:

        expected = (
            df["interceptions"] + df["fumbles_recovered"]
        )

        if not expected.equals(df["total_takeaways"]):
            raise ValueError("Defensive takeaway totals do not match.")

    print("All required metrics are present and valid.")
    print("No zero denominators detected.")
    print("All percentage metrics are between 0 and 1.")
    print("\nDEFENSIVE METRIC VALIDATION PASSED.")


def build_defensive_rating(team_metrics):

    validate_defensive_metrics(team_metrics)

    df = team_metrics

    # Derive turnover rates
    df = df.with_columns(
        (
            pl.col("interceptions")
            / pl.col("def_pass_plays_faced")
        ).alias("def_interception_rate"),

        (
            pl.col("fumbles_recovered")
            / pl.col("defensive_plays")
        ).alias("def_fumble_recovery_rate")
    )

    # Adjust low-sample turnover rates
    df = _add_shrunk_rate(
        df,
        "def_interception_rate",
        "def_pass_plays_faced",
        30,
        "adj_def_interception_rate"
    )

    df = _add_shrunk_rate(
        df,
        "def_fumble_recovery_rate",
        "defensive_plays",
        50,
        "adj_def_fumble_recovery_rate"
    )

    # Percentile scores
    metrics = [
        ("def_success_rate_allowed", False, "def_success_score"),
        ("def_yards_allowed_per_play", False, "def_yards_score"),
        ("pass_epa_allowed_per_play", False, "pass_defense_score"),
        ("rush_epa_allowed_per_play", False, "run_defense_score"),
        ("def_early_down_success_allowed", False, "early_down_score"),
        ("explosive_pass_rate_allowed", False, "explosive_pass_allowed_score"),
        ("explosive_rush_rate_allowed", False, "explosive_rush_allowed_score"),
        ("adj_def_interception_rate", True, "def_interception_score"),
        ("adj_def_fumble_recovery_rate", True, "def_fumble_score"),
        ("def_sack_rate", True, "def_sack_score"),
        ("def_non_sack_qb_hit_rate", True, "def_non_sack_qb_hit_score"),
    ]

    for metric, direction, score in metrics:
        df = _add_percentile_score(
            df, metric, direction, score
        )

    # Category scores
    df = df.with_columns(
        (
            (
                pl.col("def_success_score")
                + pl.col("def_yards_score")
            ) / 2
        ).alias("efficiency_score"),

        pl.col("pass_defense_score").alias(
            "pass_defense_category_score"
        ),

        pl.col("run_defense_score").alias(
            "run_defense_category_score"
        ),

        pl.col("early_down_score").alias(
            "early_down_defense_score"
        ),

        (
            (
                pl.col("explosive_pass_allowed_score")
                + pl.col("explosive_rush_allowed_score")
            ) / 2
        ).alias("explosive_prevention_score"),

        (
            (
                pl.col("def_interception_score")
                + pl.col("def_fumble_score")
            ) / 2
        ).alias("turnovers_score"),

        (
            pl.col("def_sack_score") * 0.70
            + pl.col("def_non_sack_qb_hit_score") * 0.30
        ).alias("pass_rush_score")
    )

    # Final defensive rating
    df = df.with_columns(
        (
            pl.col("efficiency_score") * 0.25
            + pl.col("pass_defense_category_score") * 0.15
            + pl.col("run_defense_category_score") * 0.10
            + pl.col("early_down_defense_score") * 0.10
            + pl.col("explosive_prevention_score") * 0.10
            + pl.col("turnovers_score") * 0.15
            + pl.col("pass_rush_score") * 0.15
        ).round(2).alias("defensive_rating")
    )

    return (
        df.select([
            "team",
            "efficiency_score",
            "pass_defense_category_score",
            "run_defense_category_score",
            "early_down_defense_score",
            "explosive_prevention_score",
            "turnovers_score",
            "pass_rush_score",
            "defensive_rating"
        ])
        .sort("defensive_rating", descending=True)
    )


# =========================================================
# SPECIAL TEAMS RATING
# =========================================================

def validate_special_teams_metrics(df):

    print("\nVALIDATING SPECIAL TEAMS METRICS")

    required = [
        "fg_attempts",
        "fg_make_rate",
        "avg_fg_distance",
        "xp_known_results",
        "xp_success_rate",
        "punt_attempts",
        "punt_inside_twenty_rate",
        "punt_touchback_rate",
        "punt_block_rate",
        "kickoff_attempts",
        "kickoff_touchback_rate",
        "punt_return_opportunities",
        "punt_return_yards_per_opportunity",
        "punt_return_touchdowns",
        "kickoff_return_opportunities",
        "kickoff_return_yards_per_opportunity",
        "kickoff_return_touchdowns",
    ]

    _validate_required_columns(df, required, "Special Teams")
    _validate_32_teams(df, "Special Teams")

    nonnegative = [
        "fg_attempts",
        "xp_known_results",
        "punt_attempts",
        "kickoff_attempts",
        "punt_return_opportunities",
        "punt_return_touchdowns",
        "kickoff_return_opportunities",
        "kickoff_return_touchdowns",
    ]

    _validate_finite_nonnegative(df, nonnegative, "Special Teams")

    rates = [
        "fg_make_rate",
        "xp_success_rate",
        "punt_inside_twenty_rate",
        "punt_touchback_rate",
        "punt_block_rate",
        "kickoff_touchback_rate",
    ]

    _validate_rates(df, rates, "Special Teams")

    if (df["fg_attempts"] <= 0).any():
        raise ValueError("Special Teams contains zero FG attempts.")

    if (df["xp_known_results"] <= 0).any():
        raise ValueError("Special Teams contains zero known XP results.")

    if (df["punt_attempts"] <= 0).any():
        raise ValueError("Special Teams contains zero punt attempts.")

    if (df["kickoff_attempts"] <= 0).any():
        raise ValueError("Special Teams contains zero kickoff attempts.")

    print("All required metrics are present and valid.")
    print("All percentage metrics are between 0 and 1.")
    print("\nSPECIAL TEAMS METRIC VALIDATION PASSED.")



def build_special_teams_rating(team_metrics):

    validate_special_teams_metrics(team_metrics)

    df = team_metrics

    # Shrink low-sample rates
    df = _add_shrunk_rate(
        df, "fg_make_rate", "fg_attempts",
        5, "adj_fg_make_rate"
    )

    df = _add_shrunk_rate(
        df, "xp_success_rate", "xp_known_results",
        10, "adj_xp_success_rate"
    )

    df = _add_shrunk_rate(
        df, "punt_inside_twenty_rate", "punt_attempts",
        10, "adj_punt_inside_rate"
    )

    df = _add_shrunk_rate(
        df, "punt_touchback_rate", "punt_attempts",
        10, "adj_punt_touchback_rate"
    )

    df = _add_shrunk_rate(
        df, "punt_block_rate", "punt_attempts",
        10, "adj_punt_block_rate"
    )

    df = _add_shrunk_rate(
        df, "kickoff_touchback_rate", "kickoff_attempts",
        10, "adj_kickoff_touchback_rate"
    )

    metrics = [
        ("adj_fg_make_rate", True, "fg_make_score"),
        ("adj_xp_success_rate", True, "xp_score"),
        ("adj_punt_inside_rate", True, "punt_inside_score"),
        ("adj_punt_touchback_rate", False, "punt_touchback_score"),
        ("adj_punt_block_rate", False, "punt_block_score"),
        ("adj_kickoff_touchback_rate", True, "kickoff_score"),
        ("punt_return_yards_per_opportunity", True, "punt_return_yards_score"),
        ("kickoff_return_yards_per_opportunity", True, "kickoff_return_yards_score"),
    ]

    for metric, direction, score in metrics:
        df = _add_percentile_score(
            df, metric, direction, score
        )

    df = df.with_columns(
        pl.col("fg_make_score").alias("field_goals_score"),

        pl.col("xp_score").alias("extra_points_score"),

        (
            pl.col("punt_inside_score") * 0.60
            + pl.col("punt_touchback_score") * 0.25
            + pl.col("punt_block_score") * 0.15
        ).alias("punting_score"),

        pl.col("kickoff_score").alias("kickoffs_score"),

        pl.col("punt_return_yards_score").alias("punt_returns_score"),

        pl.col("kickoff_return_yards_score").alias("kickoff_returns_score")
    )

    df = df.with_columns(
        (
            pl.col("field_goals_score") * 0.25
            + pl.col("extra_points_score") * 0.10
            + pl.col("punting_score") * 0.20
            + pl.col("kickoffs_score") * 0.10
            + pl.col("punt_returns_score") * 0.15
            + pl.col("kickoff_returns_score") * 0.20
        ).round(2).alias("special_teams_rating")
    )

    return (
        df.select([
            "team",
            "field_goals_score",
            "extra_points_score",
            "punting_score",
            "kickoffs_score",
            "punt_returns_score",
            "kickoff_returns_score",
            "special_teams_rating"
        ])
        .sort("special_teams_rating", descending=True)
    )


# =========================================================
# DISCIPLINE RATING
# =========================================================

def validate_discipline_metrics(df):

    print("\nVALIDATING DISCIPLINE METRICS")

    required = [
        "penalty_flags",
        "penalty_yards",
        "first_down_penalties",
        "penalty_yards_per_flag",
        "offensive_plays",
        "defensive_plays",
    ]

    _validate_required_columns(df, required, "Discipline")
    _validate_32_teams(df, "Discipline")

    nonnegative = [
        "penalty_flags",
        "penalty_yards",
        "first_down_penalties",
        "penalty_yards_per_flag",
        "offensive_plays",
        "defensive_plays",
    ]

    _validate_finite_nonnegative(df, nonnegative, "Discipline")

    if (df["penalty_flags"] <= 0).any():
        raise ValueError("Discipline contains teams with zero penalties.")

    if (df["offensive_plays"] <= 0).any():
        raise ValueError("Discipline contains zero offensive plays.")

    if (df["defensive_plays"] <= 0).any():
        raise ValueError("Discipline contains zero defensive plays.")

    if (
        df["first_down_penalties"] > df["penalty_flags"]
    ).any():
        raise ValueError(
            "First-down penalties exceed total penalty flags."
        )

    print("All required metrics are present and valid.")
    print("All teams have valid play counts and penalty counts.")
    print("\nDISCIPLINE METRIC VALIDATION PASSED.")



def build_discipline_rating(team_metrics):

    validate_discipline_metrics(team_metrics)

    df = team_metrics.with_columns(
        (
            pl.col("offensive_plays")
            + pl.col("defensive_plays")
        ).alias("total_team_plays")
    )

    df = df.with_columns(
        (
            pl.col("penalty_flags")
            / pl.col("total_team_plays") * 100
        ).alias("penalty_flags_per_100_plays"),

        (
            pl.col("first_down_penalties")
            / pl.col("total_team_plays") * 100
        ).alias("first_down_penalties_per_100_plays")
    )

    metrics = [
        (
            "penalty_flags_per_100_plays",
            False,
            "penalty_frequency_score"
        ),
        (
            "penalty_yards_per_flag",
            False,
            "penalty_severity_score"
        ),
        (
            "first_down_penalties_per_100_plays",
            False,
            "first_down_impact_score"
        ),
    ]

    for metric, direction, score in metrics:
        df = _add_percentile_score(
            df, metric, direction, score
        )

    df = df.with_columns(
        (
            pl.col("penalty_frequency_score") * 0.50
            + pl.col("penalty_severity_score") * 0.25
            + pl.col("first_down_impact_score") * 0.25
        ).round(2).alias("discipline_rating")
    )

    return (
        df.select([
            "team",
            "penalty_frequency_score",
            "penalty_severity_score",
            "first_down_impact_score",
            "discipline_rating"
        ])
        .sort("discipline_rating", descending=True)
    )


# =========================================================
# ON-FIELD PERFORMANCE RATING
# =========================================================


def validate_on_field_metrics(df):

    print("\nVALIDATING ON-FIELD PERFORMANCE METRICS")

    required = [
        "on_field_games_played",
        "on_field_wins",
        "on_field_losses",
        "on_field_ties",
        "on_field_points_scored",
        "on_field_points_allowed",
        "on_field_points_scored_per_game",
        "on_field_points_allowed_per_game",
        "on_field_total_point_differential",
        "on_field_avg_point_differential",
        "on_field_win_percentage",
        "on_field_strength_of_wins",
        "division_win_percentage",
        "on_field_bad_losses",
    ]

    _validate_required_columns(
        df, required, "On-Field Performance"
    )

    _validate_32_teams(df, "On-Field Performance")

    nonnegative = [
        "on_field_games_played",
        "on_field_wins",
        "on_field_losses",
        "on_field_ties",
        "on_field_points_scored",
        "on_field_points_allowed",
        "on_field_bad_losses",
    ]

    _validate_finite_nonnegative(
        df, nonnegative, "On-Field Performance"
    )

    _validate_finite_nonnegative(
        df,
        [
            "on_field_strength_of_wins",
            "division_win_percentage",
        ],
        "On-Field Performance"
    )

    _validate_rates(
        df,
        [
            "on_field_win_percentage",
            "on_field_strength_of_wins",
            "division_win_percentage",
        ],
        "On-Field Performance"
    )

    if (df["on_field_games_played"] <= 0).any():
        raise ValueError("On-field metrics contain zero games.")

    expected_games = (
        df["on_field_wins"]
        + df["on_field_losses"]
        + df["on_field_ties"]
    )

    if not expected_games.equals(df["on_field_games_played"]):
        raise ValueError("On-field game records do not balance.")

    if (df["on_field_bad_losses"] > df["on_field_losses"]).any():
        raise ValueError("Bad losses exceed total losses.")

    expected_win_percentage = (
        (
            df["on_field_wins"]
            + 0.5 * df["on_field_ties"]
        )
        / df["on_field_games_played"]
    )

    if not (
        (
            df["on_field_win_percentage"]
            - expected_win_percentage
        ).abs() < 0.000001
    ).all():
        raise ValueError("On-field win percentages do not match.")

    expected_differential = (
        df["on_field_points_scored"]
        - df["on_field_points_allowed"]
    )

    if not expected_differential.equals(
        df["on_field_total_point_differential"]
    ):
        raise ValueError("Point differentials do not match.")

    expected_scored_per_game = (
        df["on_field_points_scored"]
        / df["on_field_games_played"]
    )

    expected_allowed_per_game = (
        df["on_field_points_allowed"]
        / df["on_field_games_played"]
    )

    expected_avg_differential = (
        df["on_field_total_point_differential"]
        / df["on_field_games_played"]
    )

    if not (
        (
            df["on_field_points_scored_per_game"]
            - expected_scored_per_game
        ).abs() < 0.000001
    ).all():
        raise ValueError("Points scored per game do not match.")

    if not (
        (
            df["on_field_points_allowed_per_game"]
            - expected_allowed_per_game
        ).abs() < 0.000001
    ).all():
        raise ValueError("Points allowed per game do not match.")

    if not (
        (
            df["on_field_avg_point_differential"]
            - expected_avg_differential
        ).abs() < 0.000001
    ).all():
        raise ValueError("Average point differential does not match.")

    print("All required metrics are present and valid.")
    print("All 32 teams have valid game records.")
    print("Win percentages and point differentials verified.")
    print("Strength of wins, division performance, and bad losses verified.")
    print("\nON-FIELD METRIC VALIDATION PASSED.")


def build_on_field_rating(team_metrics):

    validate_on_field_metrics(team_metrics)

    df = team_metrics

    # Bad-loss rate
    df = df.with_columns(
        pl.when(pl.col("on_field_losses") > 0)
        .then(
            pl.col("on_field_bad_losses")
            / pl.col("on_field_losses")
        )
        .otherwise(0.0)
        .alias("on_field_bad_loss_rate")
    )

    # Percentile scores
    df = _add_percentile_score(
        df,
        "on_field_win_percentage",
        True,
        "win_percentage_score"
    )

    df = _add_percentile_score(
        df,
        "on_field_avg_point_differential",
        True,
        "point_differential_score"
    )

    df = _add_percentile_score(
        df,
        "on_field_strength_of_wins",
        True,
        "strength_of_wins_score"
    )

    df = _add_percentile_score(
        df,
        "division_win_percentage",
        True,
        "division_performance_score"
    )

    df = _add_percentile_score(
        df,
        "on_field_bad_loss_rate",
        False,
        "bad_loss_score"
    )

    # Final On-Field Performance Rating
    df = df.with_columns(
        (
            pl.col("win_percentage_score") * 0.30
            + pl.col("point_differential_score") * 0.25
            + pl.col("strength_of_wins_score") * 0.20
            + pl.col("division_performance_score") * 0.15
            + pl.col("bad_loss_score") * 0.10
        )
        .round(2)
        .alias("on_field_rating")
    )

    return (
        df.select([
            "team",
            "win_percentage_score",
            "point_differential_score",
            "strength_of_wins_score",
            "division_performance_score",
            "bad_loss_score",
            "on_field_rating"
        ])
        .sort("on_field_rating", descending=True)
    )


def build_overall_rating(
    offensive_ratings,
    defensive_ratings,
    special_teams_ratings,
    discipline_ratings,
    on_field_ratings
):
    rating_inputs = [
        (offensive_ratings, "offensive_rating"),
        (defensive_ratings, "defensive_rating"),
        (special_teams_ratings, "special_teams_rating"),
        (discipline_ratings, "discipline_rating"),
        (on_field_ratings, "on_field_rating"),
    ]

    expected_teams = None

    # Validate each foundation rating table
    for df, rating_column in rating_inputs:

        required_columns = ["team", rating_column]

        missing_columns = [
            column for column in required_columns
            if column not in df.columns
        ]

        if missing_columns:
            raise ValueError(
                f"Missing columns for {rating_column}: {missing_columns}"
            )

        if df.height != 32:
            raise ValueError(
                f"{rating_column} must contain exactly 32 teams. "
                f"Found {df.height}."
            )

        if df["team"].null_count() > 0:
            raise ValueError(
                f"{rating_column} contains null team names."
            )

        if df["team"].n_unique() != 32:
            raise ValueError(
                f"{rating_column} must contain 32 unique teams."
            )

        current_teams = set(df["team"].to_list())

        if expected_teams is None:
            expected_teams = current_teams
        elif current_teams != expected_teams:
            raise ValueError(
                f"Team mismatch detected in {rating_column}."
            )

        invalid_ratings = df.filter(
            pl.col(rating_column).is_null()
            | ~pl.col(rating_column).is_finite()
            | (pl.col(rating_column) < 0)
            | (pl.col(rating_column) > 100)
        )

        if invalid_ratings.height > 0:
            raise ValueError(
                f"{rating_column} contains invalid scores."
            )

    # Combine the five foundation ratings
    overall = (
        offensive_ratings
        .select(["team", "offensive_rating"])
        .join(
            defensive_ratings.select(["team", "defensive_rating"]),
            on="team",
            how="inner"
        )
        .join(
            special_teams_ratings.select([
                "team", "special_teams_rating"
            ]),
            on="team",
            how="inner"
        )
        .join(
            discipline_ratings.select(["team", "discipline_rating"]),
            on="team",
            how="inner"
        )
        .join(
            on_field_ratings.select(["team", "on_field_rating"]),
            on="team",
            how="inner"
        )
    )

    if overall.height != 32:
        raise ValueError(
            f"Overall rating must contain 32 teams. Found {overall.height}."
        )

    # Calculate weighted overall rating
    overall = overall.with_columns(
        (
            pl.col("offensive_rating") * 0.30
            + pl.col("defensive_rating") * 0.30
            + pl.col("special_teams_rating") * 0.10
            + pl.col("discipline_rating") * 0.05
            + pl.col("on_field_rating") * 0.25
        ).round(2).alias("overall_rating")
    )

    # Rank teams from highest to lowest
    overall = (
        overall
        .sort(
            ["overall_rating", "team"],
            descending=[True, False]
        )
        .with_row_index("rank", offset=1)
        .with_columns(
            pl.col("rank").cast(pl.Int64)
        )
        .select([
            "rank",
            "team",
            "overall_rating",
            "offensive_rating",
            "defensive_rating",
            "special_teams_rating",
            "discipline_rating",
            "on_field_rating"
        ])
    )

    return overall
