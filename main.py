
import sys
from pathlib import Path



import polars as pl


# ---------------------------------------------------------
# PROJECT PATHS
# ---------------------------------------------------------

PROJECT_DIR = Path(__file__).resolve().parent
SRC_DIR = PROJECT_DIR / "src" / "NFL_Rankings"

sys.path.insert(0, str(SRC_DIR))


# ---------------------------------------------------------
# IMPORTS
# ---------------------------------------------------------

from data import load_play_by_play, get_scrimmage_plays

from offense import build_offensive_metrics
from defense import build_defensive_metrics

from Team_DNA import (
    build_offensive_tendency_metrics,
    build_defensive_tendency_metrics,
    build_offensive_situational_metrics,
    build_defensive_situational_metrics,
    build_field_zone_performance_metrics,
)

from special_teams import build_special_teams_metrics
from penalties import build_penalty_metrics
from on_field import build_on_field_metrics, build_game_records

from ratings import (
    build_offensive_rating,
    build_defensive_rating,
    build_special_teams_rating,
    build_discipline_rating,
    build_on_field_rating,
    build_overall_rating,
)


# ---------------------------------------------------------
# SETTINGS
# ---------------------------------------------------------

SEASON = 2026


# ---------------------------------------------------------
# LOAD DATA
# ---------------------------------------------------------

print("=" * 65)
print("NFL TEAM RATINGS SYSTEM")
print(f"SEASON: {SEASON}")
print("=" * 65)

pbp = load_play_by_play(SEASON)

print(f"Play-by-play rows: {pbp.height:,}")
print(f"Number of columns: {len(pbp.columns)}")

scrimmage = get_scrimmage_plays(pbp)

print(f"Eligible scrimmage plays: {scrimmage.height:,}")


# ---------------------------------------------------------
# SPECIAL TEAMS DATA AUDITS
# ---------------------------------------------------------

print("\nFIELD GOAL DATA AUDIT")

field_goals = pbp.filter(
    pl.col("play_type") == "field_goal"
)

print(f"Total field goal plays: {field_goals.height:,}")

print(
    field_goals.group_by("field_goal_result")
    .len()
    .sort("field_goal_result")
)


print("\nEXTRA POINT DATA AUDIT")

extra_points = pbp.filter(
    pl.col("play_type") == "extra_point"
)

print(f"Total extra point plays: {extra_points.height:,}")

print(
    extra_points.group_by("extra_point_result")
    .len()
    .sort("extra_point_result")
)


print("\nPUNT DATA AUDIT")

punts = pbp.filter(
    pl.col("play_type") == "punt"
)

print(f"Total punt plays: {punts.height:,}")

print(
    punts.select([
        pl.col("punt_inside_twenty").null_count().alias("missing_inside_twenty"),
        pl.col("punt_in_endzone").null_count().alias("missing_in_endzone"),
        pl.col("punt_out_of_bounds").null_count().alias("missing_out_of_bounds"),
        pl.col("punt_downed").null_count().alias("missing_downed"),
        pl.col("punt_fair_catch").null_count().alias("missing_fair_catch"),
        pl.col("punt_blocked").null_count().alias("missing_blocked"),
        pl.col("touchback").null_count().alias("missing_touchbacks"),
    ])
)


print("\nPUNT FLAG OVERLAP AUDIT")

print(
    punts.select([
        (
            (pl.col("punt_out_of_bounds") == 1)
            & (pl.col("punt_downed") == 1)
        ).sum().alias("out_of_bounds_and_downed"),

        (
            (pl.col("punt_out_of_bounds") == 1)
            & (pl.col("punt_downed") != 1)
        ).sum().alias("out_of_bounds_only"),

        (
            (pl.col("punt_downed") == 1)
            & (pl.col("punt_out_of_bounds") != 1)
        ).sum().alias("downed_only"),

        (
            (pl.col("punt_blocked") == 1)
            & (pl.col("punt_inside_twenty") == 1)
        ).sum().alias("blocked_inside_twenty"),

        (
            (pl.col("punt_blocked") == 1)
            & (pl.col("touchback") == 1)
        ).sum().alias("blocked_touchbacks"),
    ])
)


print("\nKICKOFF DATA AUDIT")

kickoffs = pbp.filter(
    pl.col("play_type") == "kickoff"
)

print(f"Total kickoff plays: {kickoffs.height:,}")

print(
    kickoffs.select([
        pl.col("defteam").null_count().alias("missing_kicking_team"),
        pl.col("touchback").null_count().alias("missing_touchbacks"),
        pl.col("kickoff_inside_twenty").null_count().alias("missing_inside_twenty"),
        pl.col("kickoff_in_endzone").null_count().alias("missing_in_endzone"),
        pl.col("kickoff_out_of_bounds").null_count().alias("missing_out_of_bounds"),
        pl.col("kickoff_downed").null_count().alias("missing_downed"),
        pl.col("kickoff_fair_catch").null_count().alias("missing_fair_catch"),
    ])
)


print("\nINCOMPLETE KICKOFF RECORD")

print(
    kickoffs.filter(
        pl.col("kickoff_inside_twenty").is_null()
        | pl.col("kickoff_in_endzone").is_null()
        | pl.col("kickoff_out_of_bounds").is_null()
        | pl.col("kickoff_downed").is_null()
        | pl.col("kickoff_fair_catch").is_null()
    ).select([
        "game_id",
        "posteam",
        "defteam",
        "touchback",
        "desc",
    ])
)


# ---------------------------------------------------------
# RETURN OPPORTUNITY AUDITS
# ---------------------------------------------------------

print("\nPUNT RETURN OPPORTUNITY AUDIT")

print(
    punts.select([
        pl.len().alias("total_punts"),
        pl.col("return_team").null_count().alias("missing_return_teams"),
        pl.col("return_yards").null_count().alias("missing_return_yards"),
        pl.col("return_touchdown").null_count().alias("missing_return_touchdowns"),
        pl.col("return_team").is_not_null().sum().alias("known_return_teams"),
    ])
)


print("\nKICKOFF RETURN OPPORTUNITY AUDIT")

print(
    kickoffs.select([
        pl.len().alias("total_kickoffs"),
        pl.col("return_team").null_count().alias("missing_return_teams"),
        pl.col("return_yards").null_count().alias("missing_return_yards"),
        pl.col("return_touchdown").null_count().alias("missing_return_touchdowns"),
        pl.col("return_team").is_not_null().sum().alias("known_return_teams"),
    ])
)


print("\nMISSING KICKOFF RETURN TEAM")

print(
    kickoffs.filter(
        pl.col("return_team").is_null()
    ).group_by("touchback")
    .len()
    .sort("touchback")
)


print("\nMISSING NON-TOUCHBACK KICKOFFS")

print(
    kickoffs.filter(
        (pl.col("return_team").is_null())
        & (pl.col("touchback") == 0)
    ).select([
        "game_id",
        "posteam",
        "defteam",
        "kickoff_attempt",
        "return_yards",
        "desc",
    ])
)


# ---------------------------------------------------------
# GAME RECORDS AND DIVISION AUDITS
# ---------------------------------------------------------

print("\nGAME RECORDS AUDIT")

game_records = build_game_records(pbp)

print(f"Game records: {game_records.height:,}")
print(f"Game record columns: {len(game_records.columns)}")


print("\nDIVISION ASSIGNMENT AUDIT")

print(
    game_records.group_by("team")
    .agg([
        pl.col("division").first().alias("division"),
        pl.col("division").is_null().sum().alias("missing_team_division"),
        pl.col("opponent_division").is_null().sum().alias("missing_opponent_division"),
        pl.col("is_division_game").sum().alias("division_games"),
    ])
    .sort("team")
)


print("\nDIVISION GAME TOTALS")

print(
    game_records.group_by("division")
    .agg([
        pl.col("is_division_game").sum().alias("team_division_game_records"),
        pl.len().alias("total_team_game_records"),
    ])
    .sort("division")
)


print("\nGAME RECORD SAMPLE")

print(game_records.head(10))


# ---------------------------------------------------------
# DEFENSIVE PASS RUSH AUDIT
# ---------------------------------------------------------

print("\nDEFENSIVE PASS RUSH OVERLAP AUDIT")

dropbacks = pbp.filter(
    pl.col("qb_dropback") == 1
)

print(
    dropbacks.select([
        pl.len().alias("total_dropbacks"),
        pl.col("sack").sum().alias("total_sacks"),
        pl.col("qb_hit").sum().alias("total_qb_hits"),
        (
            (pl.col("sack") == 1)
            & (pl.col("qb_hit") == 1)
        ).sum().alias("sacks_also_recorded_as_qb_hits"),
    ])
)


# ---------------------------------------------------------
# BUILD FOUNDATION METRICS
# ---------------------------------------------------------

print("\n" + "=" * 65)
print("BUILDING FOUNDATION METRICS")
print("=" * 65)

offensive_metrics = build_offensive_metrics(
    pbp,
    scrimmage
)

defensive_metrics = build_defensive_metrics(
    pbp,
    scrimmage
)

special_teams_metrics = build_special_teams_metrics(
    pbp
)

discipline_metrics = build_penalty_metrics(
    pbp
)

on_field_metrics = build_on_field_metrics(
    pbp
)

# ---------------------------------------------------------
# BUILD TEAM DNA METRICS
# ---------------------------------------------------------

print("\nBUILDING TEAM DNA METRICS")

offensive_tendencies = build_offensive_tendency_metrics(
    scrimmage
)

defensive_tendencies = build_defensive_tendency_metrics(
    scrimmage
)

offensive_situational = build_offensive_situational_metrics(
    pbp
)

defensive_situational = build_defensive_situational_metrics(
    pbp
)

field_zone_performance = build_field_zone_performance_metrics(
    scrimmage
)

print(f"Offensive tendencies: {offensive_tendencies.height} teams")
print(f"Defensive tendencies: {defensive_tendencies.height} teams")
print(f"Situational offense: {offensive_situational.height} teams")
print(f"Situational defense: {defensive_situational.height} teams")

# ---------------------------------------------------------
# COMBINE FOUNDATION METRICS
# ---------------------------------------------------------

combined_metrics = (
    offensive_metrics
    .join(defensive_metrics, on="team", how="inner")
    .join(special_teams_metrics, on="team", how="inner")
    .join(discipline_metrics, on="team", how="inner")
    .join(on_field_metrics, on="team", how="inner")
    .join(offensive_tendencies, on="team", how="inner")
    .join(defensive_tendencies, on="team", how="inner")
    .join(offensive_situational, on="team", how="inner")
    .join(defensive_situational, on="team", how="inner")
    .join(field_zone_performance, on="team", how="inner")
    .sort("team")
)

print("\nCOMBINED METRICS")

print(f"Teams: {combined_metrics.height}")
print(f"Columns: {len(combined_metrics.columns)}")


# ---------------------------------------------------------
# BUILD FOUNDATION RATINGS
# ---------------------------------------------------------

print("\n" + "=" * 65)
print("BUILDING FOUNDATION RATINGS")
print("=" * 65)

offensive_ratings = build_offensive_rating(
    combined_metrics
)

defensive_ratings = build_defensive_rating(
    combined_metrics
)

special_teams_ratings = build_special_teams_rating(
    combined_metrics
)

discipline_ratings = build_discipline_rating(
    combined_metrics
)

on_field_ratings = build_on_field_rating(
    combined_metrics
)


# ---------------------------------------------------------
# DISPLAY FOUNDATION RATINGS
# ---------------------------------------------------------

print("\nOFFENSIVE RATINGS")
print(offensive_ratings)

print("\nDEFENSIVE RATINGS")
print(defensive_ratings)

print("\nSPECIAL TEAMS RATINGS")
print(special_teams_ratings)

print("\nDISCIPLINE RATINGS")
print(discipline_ratings)

print("\nON-FIELD PERFORMANCE RATINGS")
print(on_field_ratings)


# ---------------------------------------------------------
# BUILD OVERALL NFL RATINGS
# ---------------------------------------------------------

print("\n" + "=" * 65)
print("CALCULATING OVERALL NFL RATINGS")
print("=" * 65)

overall_ratings = build_overall_rating(
    offensive_ratings,
    defensive_ratings,
    special_teams_ratings,
    discipline_ratings,
    on_field_ratings
)


# ---------------------------------------------------------
# FINAL NFL POWER RANKINGS
# ---------------------------------------------------------

print("\n" + "=" * 90)
print(f"2026 NFL POWER RANKINGS — WEEKS 1–10")
print("=" * 90)

print(
    overall_ratings.select([
        "rank",
        "team",
        "overall_rating",
        "offensive_rating",
        "defensive_rating",
        "special_teams_rating",
        "discipline_rating",
        "on_field_rating",
    ])
)


# ---------------------------------------------------------
# OVERALL RATING VALIDATION
# ---------------------------------------------------------

print("\nOVERALL RATING VALIDATION")

print(f"Total teams ranked: {overall_ratings.height}")
print(f"Unique teams: {overall_ratings['team'].n_unique()}")

print(
    f"Highest overall rating: "
    f"{overall_ratings['overall_rating'].max():.2f}"
)

print(
    f"Lowest overall rating: "
    f"{overall_ratings['overall_rating'].min():.2f}"
)

print(
    f"Average overall rating: "
    f"{overall_ratings['overall_rating'].mean():.2f}"
)

print(
    f"Rating range: "
    f"{overall_ratings['overall_rating'].max() - overall_ratings['overall_rating'].min():.2f}"
)


# ---------------------------------------------------------
# OVERALL WEIGHTED FORMULA AUDIT
# ---------------------------------------------------------

print("\nOVERALL WEIGHTED FORMULA AUDIT")

formula_audit = overall_ratings.with_columns(
    (
        pl.col("offensive_rating") * 0.30
        + pl.col("defensive_rating") * 0.30
        + pl.col("special_teams_rating") * 0.10
        + pl.col("discipline_rating") * 0.05
        + pl.col("on_field_rating") * 0.25
    ).round(2).alias("independent_overall_rating")
)

formula_audit = formula_audit.with_columns(
    (
        pl.col("overall_rating")
        - pl.col("independent_overall_rating")
    ).abs().alias("rating_difference")
)

print(
    formula_audit.select([
        "team",
        "overall_rating",
        "independent_overall_rating",
        "rating_difference",
    ])
)

print(
    "\nMaximum formula difference:",
    formula_audit["rating_difference"].max()
)

assert formula_audit["rating_difference"].max() == 0.0

print("WEIGHTED FORMULA AUDIT PASSED.")



# ---------------------------------------------------------
# EXPANDED ON-FIELD METRICS
# ---------------------------------------------------------

print("\nEXPANDED ON-FIELD METRICS")

print(
    on_field_metrics.select([
        "team",
        "on_field_wins",
        "on_field_losses",
        "on_field_strength_of_wins",
        "on_field_quality_wins",
        "on_field_bad_losses",
        "division_wins",
        "division_losses",
        "division_win_percentage",
    ]).sort("team")
)


print("\nBAD-LOSS RATE AUDIT")

print(
    on_field_metrics.with_columns(
        pl.when(pl.col("on_field_losses") > 0)
        .then(
            pl.col("on_field_bad_losses")
            / pl.col("on_field_losses")
        )
        .otherwise(0.0)
        .alias("on_field_bad_loss_rate")
    ).select([
        "team",
        "on_field_losses",
        "on_field_bad_losses",
        "on_field_bad_loss_rate",
    ]).sort("team")
)

# ---------------------------------------------------------
# EXPORT POWER RANKINGS FOR WEBSITE
# ---------------------------------------------------------

OUTPUT_DIR = PROJECT_DIR / "data" / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

rankings_file = OUTPUT_DIR / f"nfl_rankings_{SEASON}.csv"

overall_ratings.select([
    "rank",
    "team",
    "overall_rating",
    "offensive_rating",
    "defensive_rating",
    "special_teams_rating",
    "discipline_rating",
    "on_field_rating",
]).write_csv(rankings_file)

print(f"\nPower rankings exported to: {rankings_file}")

# Export underlying team metrics for the website
metrics_file = OUTPUT_DIR / f"team_metrics_{SEASON}.csv"

combined_metrics.write_csv(metrics_file)

print(f"Team metrics exported to: {metrics_file}")

# ---------------------------------------------------------
# FINISH
# ---------------------------------------------------------

print("\n" + "=" * 90)
print("NFL TEAM RATINGS SYSTEM COMPLETED SUCCESSFULLY")
print("ALL FIVE FOUNDATION RATINGS GENERATED")
print("OVERALL NFL POWER RANKINGS GENERATED")
print("=" * 90)
