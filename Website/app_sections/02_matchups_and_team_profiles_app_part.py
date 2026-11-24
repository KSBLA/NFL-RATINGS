

def build_key_statistical_battles(team_stats, opponent_stats):
    battles = [
        {
            "category": "Turnover Battle",
            "team_metric": "net_turnovers",
            "opponent_metric": "net_turnovers",
            "team_label": "Net Turnovers / game",
            "opponent_label": "Net Turnovers / game",
            "team_games": True,
            "opponent_games": True,
            "lower_is_better": False,
            "description": "Create turnovers while protecting the football.",
        },
        {
            "category": "Pass Protection",
            "team_metric": "sack_rate_allowed",
            "opponent_metric": "sack_rate_allowed",
            "team_label": "Sack Rate Allowed",
            "opponent_label": "Sack Rate Allowed",
            "lower_is_better": True,
            "description": "Keep the quarterback protected and limit sacks.",
        },
        {
            "category": "Fourth Down",
            "team_metric": "dna_fourth_down_conversion_rate",
            "opponent_metric": "dna_fourth_down_conversion_rate",
            "team_label": "Conversion Rate",
            "opponent_label": "Conversion Rate",
            "team_sample": "dna_fourth_down_attempts",
            "opponent_sample": "dna_fourth_down_attempts",
            "lower_is_better": False,
            "minimum": 5,
            "description": "Convert critical fourth downs and keep drives alive.",
        },
        {
            "category": "Penalty Discipline",
            "team_metric": "penalty_yards",
            "opponent_metric": "penalty_yards",
            "team_label": "Penalty Yards / game",
            "opponent_label": "Penalty Yards / game",
            "team_games": True,
            "opponent_games": True,
            "lower_is_better": True,
            "description": "Avoid costly penalties and giving away field position.",
        },
    ]

    def number(row, column):
        value = pd.to_numeric(
            pd.Series([row.get(column)]),
            errors="coerce",
        ).iloc[0]

        return None if pd.isna(value) else float(value)

    results = []

    for battle in battles:
        if battle["category"] == "Turnover Battle":
            team_takeaways = number(team_stats, "total_takeaways")
            team_giveaways = number(team_stats, "total_giveaways")
            opponent_takeaways = number(opponent_stats, "total_takeaways")
            opponent_giveaways = number(opponent_stats, "total_giveaways")

            if None in (
                    team_takeaways,
                    team_giveaways,
                    opponent_takeaways,
                    opponent_giveaways,
            ):
                continue

            team_value = team_takeaways - team_giveaways
            opponent_value = opponent_takeaways - opponent_giveaways
        else:
            team_value = number(team_stats, battle["team_metric"])
            opponent_value = number(
                opponent_stats, battle["opponent_metric"]
            )

        if team_value is None or opponent_value is None:
            continue

        if battle.get("team_games"):
            games = number(team_stats, "on_field_games_played")
            if games is None or games <= 0:
                continue
            team_value /= games

        if battle.get("opponent_games"):
            games = number(opponent_stats, "on_field_games_played")
            if games is None or games <= 0:
                continue
            opponent_value /= games

        team_sample = battle.get("team_sample")
        opponent_sample = battle.get("opponent_sample")

        if team_sample:
            sample = number(team_stats, team_sample)
            if sample is None or sample < battle["minimum"]:
                continue

        if opponent_sample:
            sample = number(opponent_stats, opponent_sample)
            if sample is None or sample < battle["minimum"]:
                continue

        if battle["lower_is_better"]:
            edge = opponent_value - team_value
        else:
            edge = team_value - opponent_value

        results.append({
            "category": battle["category"],
            "team_value": team_value,
            "opponent_value": opponent_value,
            "team_label": battle["team_label"],
            "opponent_label": battle["opponent_label"],
            "edge": edge,
            "description": battle["description"],
        })

    results.sort(
        key=lambda item: abs(item["edge"]),
        reverse=True,
    )

    return results[:3]


def build_matchup_analysis(team_stats, opponent_stats):
    comparisons = [
        {
            "category": "Overall Efficiency",
            "offense": "off_epa_per_play",
            "defense": "def_epa_allowed_per_play",
            "offense_sample": "offensive_plays",
            "defense_sample": "defensive_plays",
            "threshold": 0.025,
            "unit": "EPA/play",
        },
        {
            "category": "Passing",
            "offense": "pass_epa_per_play",
            "defense": "pass_epa_allowed_per_play",
            "offense_sample": "pass_plays",
            "defense_sample": "def_pass_plays_faced",
            "threshold": 0.035,
            "unit": "EPA/play",
        },
        {
            "category": "Rushing",
            "offense": "rush_epa_per_play",
            "defense": "rush_epa_allowed_per_play",
            "offense_sample": "rush_plays",
            "defense_sample": "def_rush_plays_faced",
            "threshold": 0.025,
            "unit": "EPA/play",
        },
        {
            "category": "Explosive Plays",
            "offense": "overall_explosive_rate",
            "defense": "overall_explosive_rate_allowed",
            "offense_sample": "offensive_plays",
            "defense_sample": "defensive_plays",
            "threshold": 0.015,
            "unit": "rate",
        },
        {
            "category": "Third Down",
            "offense": "dna_third_down_conversion_rate",
            "defense": "dna_third_down_conversion_rate_allowed",
            "offense_sample": "dna_third_down_attempts",
            "defense_sample": "dna_third_down_attempts_allowed",
            "threshold": 0.04,
            "unit": "rate",
        },
        {
            "category": "Red Zone",
            "offense": "dna_red_zone_td_rate",
            "defense": "dna_red_zone_td_rate_allowed",
            "offense_sample": "dna_red_zone_trips",
            "defense_sample": "dna_red_zone_trips_allowed",
            "threshold": 0.06,
            "unit": "rate",
        },
    ]

    advantages = []
    concerns = []

    def number(row, column):
        value = pd.to_numeric(
            pd.Series([row.get(column)]),
            errors="coerce",
        ).iloc[0]

        return None if pd.isna(value) else float(value)

    def add_comparison(category, side, edge, threshold,
                       team_value, opponent_value, unit):
        normalized_edge = edge / threshold

        if edge > threshold:
            advantages.append({
                "category": category,
                "side": side,
                "team_value": team_value,
                "opponent_value": opponent_value,
                "edge": edge,
                "strength": normalized_edge,
                "unit": unit,
            })
        elif edge < -threshold:
            concerns.append({
                "category": category,
                "side": side,
                "team_value": team_value,
                "opponent_value": opponent_value,
                "edge": edge,
                "strength": abs(normalized_edge),
                "unit": unit,
            })

    for item in comparisons:
        category = item["category"]
        threshold = item["threshold"]

        # Selected team's offense vs. opponent's defense.
        offense_value = number(team_stats, item["offense"])
        opponent_defense = number(opponent_stats, item["defense"])

        offense_plays = number(
            team_stats, item["offense_sample"]
        )
        opponent_defense_plays = number(
            opponent_stats, item["defense_sample"]
        )

        if (
                offense_value is not None
                and opponent_defense is not None
                and offense_plays is not None
                and opponent_defense_plays is not None
                and offense_plays >= 50
                and opponent_defense_plays >= 50
        ):
            edge = offense_value - opponent_defense

            add_comparison(
                category,
                "OFFENSE",
                edge,
                threshold,
                offense_value,
                opponent_defense,
                item["unit"],
            )

        # Selected team's defense vs. opponent's offense.
        opponent_offense = number(
            opponent_stats, item["offense"]
        )
        defense_value = number(
            team_stats, item["defense"]
        )

        opponent_offense_plays = number(
            opponent_stats, item["offense_sample"]
        )
        defense_plays = number(
            team_stats, item["defense_sample"]
        )

        if (
                opponent_offense is not None
                and defense_value is not None
                and opponent_offense_plays is not None
                and defense_plays is not None
                and opponent_offense_plays >= 50
                and defense_plays >= 50
        ):
            edge = opponent_offense - defense_value

            add_comparison(
                category,
                "DEFENSE",
                edge,
                threshold,
                defense_value,
                opponent_offense,
                item["unit"],
            )

    advantages.sort(
        key=lambda item: item["strength"],
        reverse=True,
    )

    concerns.sort(
        key=lambda item: item["strength"],
        reverse=True,
    )

    return advantages, concerns


def build_keys_to_victory(advantages, concerns):
    keys = []

    advantages = sorted(
        advantages,
        key=lambda item: item["strength"],
        reverse=True,
    )

    concerns = sorted(
        concerns,
        key=lambda item: item["strength"],
        reverse=True,
    )

    # Turn offensive advantages into game-plan recommendations.
    for item in advantages:
        if item["side"] != "OFFENSE":
            continue

        category = item["category"]

        recommendations = {
            "Overall Efficiency": (
                "Stay ahead of the chains and sustain efficient drives. "
                "Make the opponent defend the entire field."
            ),
            "Passing": (
                "Attack through the air. Use the passing game to create "
                "favorable matchups and move the chains."
            ),
            "Rushing": (
                "Establish the ground game and use it to control the "
                "tempo and create manageable situations."
            ),
            "Explosive Plays": (
                "Look for opportunities to generate explosive gains. "
                "Take calculated shots downfield."
            ),
            "Third Down": (
                "Capitalize on third-down opportunities and keep drives "
                "alive instead of settling for short possessions."
            ),
            "Red Zone": (
                "Finish drives with touchdowns. Take advantage of "
                "opportunities inside the opponent's 20-yard line."
            ),
        }

        recommendation = recommendations.get(category)

        if recommendation:
            keys.append(recommendation)

    # Turn defensive advantages into game-plan recommendations.
    for item in advantages:
        if item["side"] != "DEFENSE":
            continue

        category = item["category"]

        recommendations = {
            "Overall Efficiency": (
                "Make the opponent earn every yard. Limit efficient "
                "drives and force difficult situations."
            ),
            "Passing": (
                "Disrupt the opposing passing game. Pressure the "
                "quarterback and make completions difficult."
            ),
            "Rushing": (
                "Control the line of scrimmage and make the opponent "
                "one-dimensional."
            ),
            "Explosive Plays": (
                "Keep everything in front of the defense. Prevent "
                "big plays and force the opponent to sustain long drives."
            ),
            "Third Down": (
                "Get off the field on third down and prevent the "
                "opponent from extending possessions."
            ),
            "Red Zone": (
                "Tighten up in the red zone and force field goals "
                "instead of allowing touchdowns."
            ),
        }

        recommendation = recommendations.get(category)

        if recommendation:
            keys.append(recommendation)

    # Address the selected team's statistical weaknesses.
    for item in concerns:
        category = item["category"]
        side = item["side"]

        if side == "OFFENSE":
            recommendations = {
                "Overall Efficiency": (
                    "Avoid negative plays and stay on schedule. "
                    "Sustaining drives will be especially important."
                ),
                "Passing": (
                    "Protect the quarterback and avoid forcing throws "
                    "against a difficult pass defense."
                ),
                "Rushing": (
                    "Be selective with rushing attempts. Avoid predictable "
                    "runs and use other ways to create offensive balance."
                ),
                "Explosive Plays": (
                    "Find ways to create chunk plays without forcing "
                    "low-percentage opportunities."
                ),
                "Third Down": (
                    "Improve third-down execution by creating more "
                    "manageable situations on early downs."
                ),
                "Red Zone": (
                    "Prioritize execution near the goal line and find "
                    "ways to turn red-zone trips into touchdowns."
                ),
            }
        else:
            recommendations = {
                "Overall Efficiency": (
                    "Limit the opponent's offensive rhythm and force "
                    "longer, more difficult drives."
                ),
                "Passing": (
                    "Give the secondary help and find ways to disrupt "
                    "the opposing passing attack."
                ),
                "Rushing": (
                    "Improve gap discipline and win more battles at "
                    "the line of scrimmage."
                ),
                "Explosive Plays": (
                    "Emphasize tackling and assignment discipline to "
                    "prevent the opponent from breaking big plays."
                ),
                "Third Down": (
                    "Find ways to create more third-and-long situations "
                    "and get off the field."
                ),
                "Red Zone": (
                    "Improve execution near the goal line and make the "
                    "opponent settle for field goals."
                ),
            }

        recommendation = recommendations.get(category)

        if recommendation:
            keys.append(recommendation)

    # Remove duplicate recommendations while preserving their order.
    return list(dict.fromkeys(keys))[:5]


def build_game_preview_key(advantages, concerns):
    strategy_library = {
        "Overall Efficiency": {
            "OFFENSE": {
                "advantage": [
                    ("Stay ahead of the chains",
                     "Use efficient early-down offense to stay out of "
                     "obvious passing situations and sustain drives."),
                    ("Keep the offense balanced",
                     "Mix the run and pass to keep the defense guessing "
                     "and consistently move the chains."),
                    ("Make every possession count",
                     "Lean into the offense's efficiency and force the "
                     "opponent to defend sustained drives."),
                ],
                "concern": [
                    ("Simplify the offensive approach",
                     "Prioritize manageable plays, avoid negative "
                     "yardage, and prevent the defense from dictating "
                     "the situation."),
                    ("Win on early downs",
                     "Create more manageable second and third downs "
                     "instead of putting the offense behind schedule."),
                    ("Protect every possession",
                     "Limit risky plays and focus on efficient, "
                     "high-percentage decisions."),
                ],
            },
            "DEFENSE": {
                "advantage": [
                    ("Make every yard difficult",
                     "Use the defensive efficiency advantage to force "
                     "longer drives and make the offense earn everything."),
                    ("Disrupt their offensive rhythm",
                     "Keep the opponent from settling into a rhythm and "
                     "force them into difficult situations."),
                    ("Win the down-to-down battle",
                     "Stay disciplined and make it difficult for the "
                     "opponent to string together successful plays."),
                ],
                "concern": [
                    ("Make them earn every drive",
                     "Focus on limiting easy completions and runs. "
                     "Force the opponent to execute consistently."),
                    ("Improve defensive consistency",
                     "Eliminate assignment mistakes and prevent "
                     "individual plays from turning into sustained drives."),
                    ("Create tougher situations",
                     "Focus on winning early downs and forcing the "
                     "opponent into longer-yardage situations."),
                ],
            },
        },
        "Passing": {
            "OFFENSE": {
                "advantage": [
                    ("Attack the secondary",
                     "Take advantage of the passing matchup by "
                     "challenging coverage and creating opportunities "
                     "through the air."),
                    ("Spread the defense out",
                     "Use the passing game to stretch the defense "
                     "horizontally and create favorable matchups."),
                    ("Build the game plan around the pass",
                     "Lean into the passing advantage to move the "
                     "chains and open opportunities elsewhere."),
                ],
                "concern": [
                    ("Use a quicker passing approach",
                     "Get the ball out quickly, use high-percentage "
                     "throws, and limit opportunities for the defense "
                     "to disrupt the quarterback."),
                    ("Protect the quarterback",
                     "Emphasize protection and avoid predictable "
                     "passing situations against a difficult defense."),
                    ("Create easier passing opportunities",
                     "Use shorter throws and varied formations to "
                     "help the passing game find its rhythm."),
                ],
            },
            "DEFENSE": {
                "advantage": [
                    ("Make the quarterback uncomfortable",
                     "Use the passing defensive advantage to disrupt "
                     "timing and make completions more difficult."),
                    ("Challenge their passing attack",
                     "Make the opponent prove it can consistently "
                     "complete passes against this secondary."),
                    ("Take away easy throws",
                     "Disrupt the passing rhythm and force the "
                     "quarterback to hold the ball longer."),
                ],
                "concern": [
                    ("Disrupt the passing rhythm",
                     "Mix coverages and pressure looks to make "
                     "the quarterback work for every completion."),
                    ("Limit opportunities downfield",
                     "Prioritize coverage discipline and prevent "
                     "the passing game from producing easy gains."),
                    ("Make protection work",
                     "Find ways to create pressure without leaving "
                     "the secondary exposed."),
                ],
            },
        },
        "Rushing": {
            "OFFENSE": {
                "advantage": [
                    ("Attack the defensive front",
                     "Make the ground game a central part of the plan "
                     "and consistently challenge the opponent's "
                     "run defense."),
                    ("Set the physical tone",
                     "Establish the run early and make the defense "
                     "prove it can handle a physical rushing attack."),
                    ("Use the run to control the game",
                     "Lean on the rushing advantage to sustain drives, "
                     "control possession, and dictate the tempo."),
                ],
                "concern": [
                    ("Be selective with rushing attempts",
                     "Vary the run concepts and avoid repeatedly "
                     "challenging the defense in predictable situations."),
                    ("Create better running opportunities",
                     "Use formations and offensive balance to prevent "
                     "the defense from loading the box."),
                    ("Make the run game more efficient",
                     "Focus on execution and favorable rushing "
                     "situations instead of forcing carries."),
                ],
            },
            "DEFENSE": {
                "advantage": [
                    ("Win the line of scrimmage",
                     "Use the defensive front to limit rushing lanes "
                     "and make the opponent earn yards through the air."),
                    ("Make them one-dimensional",
                     "Take away the ground game and force the "
                     "opponent to rely more heavily on passing."),
                    ("Control the rushing lanes",
                     "Maintain gap discipline and prevent the "
                     "opponent from establishing a consistent run game."),
                ],
                "concern": [
                    ("Fix the run defense",
                     "Prioritize gap integrity and tackling to prevent "
                     "the opponent from controlling the ground game."),
                    ("Stop the run early",
                     "Focus on winning first down and avoiding the "
                     "long rushing gains that keep drives alive."),
                    ("Make rushing yards difficult",
                     "Improve defensive discipline and close running "
                     "lanes before the opponent reaches the second level."),
                ],
            },
        },
        "Explosive Plays": {
            "OFFENSE": {
                "advantage": [
                    ("Create explosive opportunities",
                     "Look for favorable opportunities to generate "
                     "chunk plays and put immediate pressure on the defense."),
                    ("Attack space downfield",
                     "Use the offense's ability to create big plays "
                     "to stretch the defense and change field position."),
                    ("Take calculated shots",
                     "Mix explosive opportunities into the game plan "
                     "without sacrificing offensive efficiency."),
                ],
                "concern": [
                    ("Create chunk plays more efficiently",
                     "Use varied formations and play designs to create "
                     "space without forcing low-percentage attempts."),
                    ("Find opportunities after the catch",
                     "Use shorter completions and create opportunities "
                     "for receivers to gain additional yardage."),
                    ("Avoid forcing explosive plays",
                     "Stay patient, take available yards, and let "
                     "bigger opportunities develop naturally."),
                ],
            },
            "DEFENSE": {
                "advantage": [
                    ("Keep everything in front",
                     "Use the defensive advantage to prevent big plays "
                     "and force the opponent to sustain long drives."),
                    ("Eliminate explosive opportunities",
                     "Stay disciplined in coverage and prevent "
                     "individual plays from changing the game."),
                    ("Force them to be patient",
                     "Take away the big play and make the opponent "
                     "execute repeatedly to move the ball."),
                ],
                "concern": [
                    ("Eliminate defensive breakdowns",
                     "Prioritize assignment discipline and communication "
                     "to prevent explosive gains."),
                    ("Protect against the big play",
                     "Keep appropriate coverage help over the top "
                     "and avoid unnecessary risks."),
                    ("Improve tackling in space",
                     "Limit yards after contact and prevent ordinary "
                     "plays from becoming major gains."),
                ],
            },
        },
        "Third Down": {
            "OFFENSE": {
                "advantage": [
                    ("Own third down",
                     "Capitalize on the favorable matchup by keeping "
                     "drives alive and extending possessions."),
                    ("Stay on the field",
                     "Use the third-down advantage to sustain drives "
                     "and keep the opponent's offense on the sideline."),
                    ("Finish offensive possessions",
                     "Make third-down execution a priority and "
                     "consistently turn opportunities into first downs."),
                ],
                "concern": [
                    ("Create manageable third downs",
                     "Improve early-down execution so the offense "
                     "is not consistently facing long-yardage situations."),
                    ("Simplify third-down decisions",
                     "Use favorable formations and high-percentage "
                     "plays to improve conversion opportunities."),
                    ("Avoid obvious passing situations",
                     "Establish more productive early downs and "
                     "keep the offense's playbook open."),
                ],
            },
            "DEFENSE": {
                "advantage": [
                    ("Get off the field",
                     "Use the third-down advantage to end possessions "
                     "and give the offense more opportunities."),
                    ("Force difficult conversions",
                     "Create longer third-down situations and make "
                     "the opponent earn every first down."),
                    ("Win the critical downs",
                     "Stay aggressive and disciplined when the "
                     "opponent needs to extend a drive."),
                ],
                "concern": [
                    ("Improve third-down execution",
                     "Focus on coverage discipline and pressure "
                     "to create more opportunities to get off the field."),
                    ("Win first and second down",
                     "Create longer third-down situations instead "
                     "of allowing the opponent to convert comfortably."),
                    ("Finish defensive possessions",
                     "Improve situational execution and prevent "
                     "the opponent from extending drives."),
                ],
            },
        },
        "Red Zone": {
            "OFFENSE": {
                "advantage": [
                    ("Finish drives with touchdowns",
                     "Capitalize on the red-zone matchup and turn "
                     "scoring opportunities into touchdowns."),
                    ("Be aggressive near the goal line",
                     "Use the team's red-zone strength to put "
                     "pressure on the defense inside the 20."),
                    ("Turn possessions into points",
                     "Make red-zone execution a priority and "
                     "maximize every scoring opportunity."),
                ],
                "concern": [
                    ("Improve red-zone execution",
                     "Emphasize situational play-calling and "
                     "execution when the field becomes compressed."),
                    ("Finish more scoring drives",
                     "Find ways to create favorable matchups "
                     "near the goal line instead of settling for field goals."),
                    ("Simplify near the goal line",
                     "Prioritize reliable plays and avoid mistakes "
                     "that waste scoring opportunities."),
                ],
            },
            "DEFENSE": {
                "advantage": [
                    ("Force field goals",
                     "Use the red-zone defensive advantage to "
                     "prevent touchdowns and limit scoring damage."),
                    ("Tighten up near the goal line",
                     "Make the opponent work for every yard "
                     "and protect the most important part of the field."),
                    ("Win the red-zone battle",
                     "Stay disciplined inside the 20 and turn "
                     "opponent scoring opportunities into field goals."),
                ],
                "concern": [
                    ("Strengthen goal-line defense",
                     "Improve assignment discipline and tackling "
                     "when the opponent gets inside scoring range."),
                    ("Make red-zone stops",
                     "Focus on limiting easy scoring opportunities "
                     "and forcing the opponent into difficult plays."),
                    ("Prevent touchdowns",
                     "Emphasize situational defense and make "
                     "the opponent settle for field goals."),
                ],
            },
        },
    }

    candidates = (
            [(item, "advantage") for item in advantages]
            + [(item, "concern") for item in concerns]
    )

    candidates = [
        (item, result_type)
        for item, result_type in candidates
        if item.get("category") in strategy_library
           and item.get("side") in ("OFFENSE", "DEFENSE")
    ]

    if not candidates:
        return {
            "title": "Win the fundamentals",
            "category": "Game Management",
            "side": "BOTH",
            "explanation": (
                "Protect the football, execute in key situations, "
                "and avoid giving the opponent easy opportunities."
            ),
            "stat_line": None,
        }

    item, result_type = max(
        candidates,
        key=lambda candidate: candidate[0].get("strength", 0),
    )

    category = item["category"]
    side = item["side"]

    variations = strategy_library[category][side][result_type]

    # Use the matchup values to select between strategic variations.
    team_value = item.get("team_value", 0) or 0
    opponent_value = item.get("opponent_value", 0) or 0

    variant_index = (
            int(abs(team_value * 1000) + abs(opponent_value * 1000))
            % len(variations)
    )

    title, explanation = variations[variant_index]

    if item.get("unit") == "EPA/play":
        team_display = f"{team_value:+.3f}"
        opponent_display = f"{opponent_value:+.3f}"
        unit_label = "EPA/play"
    else:
        team_display = f"{team_value:.1%}"
        opponent_display = f"{opponent_value:.1%}"
        unit_label = ""

    if side == "OFFENSE":
        stat_line = (
            f"Your offense: {team_display} {unit_label} "
            f"| Opponent defense allows: "
            f"{opponent_display} {unit_label}"
        )
    else:
        stat_line = (
            f"Your defense allows: {team_display} {unit_label} "
            f"| Opponent offense: "
            f"{opponent_display} {unit_label}"
        )

    return {
        "title": title,
        "category": category,
        "side": side,
        "explanation": explanation,
        "stat_line": stat_line,
    }


def render_up_next(code, info):
    game = get_next_game(code)

    section("UP NEXT")

    if game is None:
        st.info("No upcoming game is currently scheduled.")
        return

    opponent = (
        game["away"] if game["home"] == code else game["home"]
    )

    opponent_info = TEAMS[opponent]

    team_row = get_team_row(code)
    opponent_row = get_team_row(opponent)

    team_stats = get_team_row(code, team_metrics)
    opponent_stats = get_team_row(opponent, team_metrics)

    if any(x is None for x in [
        team_row, opponent_row, team_stats, opponent_stats
    ]):
        st.warning("Unable to load matchup ratings.")
        return

    team_rating = float(team_row["overall_rating"])
    opponent_rating = float(opponent_row["overall_rating"])

    is_home = game["home"] == code

    win_probability = calculate_win_probability(
        team_rating,
        opponent_rating,
        is_home,
    )

    if win_probability >= 0.50:
        headline = "CONFIDENCE METER"
        outlook = "FAVORITE"
    else:
        headline = "UPSET ALERT"
        outlook = "UNDERDOG"

    game_date = datetime.strptime(
        game["date"], "%Y-%m-%d"
    ).strftime("%A, %B %d, %Y")

    location = "HOME" if is_home else "AWAY"

    st.markdown(
        f'<div style="background:linear-gradient(135deg,'
        f'{info["color"]}33,#111827);'
        f'border:1px solid {info["color"]};'
        f'border-radius:16px;padding:24px;margin-bottom:18px;'
        f'text-align:center">'

        f'<div style="font-size:12px;letter-spacing:3px;'
        f'font-weight:800;opacity:.8;margin-bottom:20px">'
        f'{html.escape(headline)}</div>'

        f'<div style="display:flex;align-items:center;'
        f'justify-content:center;gap:30px;flex-wrap:wrap">'

        f'<div style="display:flex;flex-direction:column;'
        f'align-items:center;gap:8px">'
        f'{logo(code, 100)}'
        f'<div style="font-size:17px;font-weight:800">'
        f'{html.escape(info["name"])}</div>'
        f'</div>'

        f'<div style="font-size:20px;font-weight:900;'
        f'opacity:.65">VS</div>'

        f'<div style="display:flex;flex-direction:column;'
        f'align-items:center;gap:8px">'
        f'{logo(opponent, 100)}'
        f'<div style="font-size:17px;font-weight:800">'
        f'{html.escape(opponent_info["name"])}</div>'
        f'</div>'

        f'</div>'

        f'<div style="font-size:13px;opacity:.8;margin-top:20px">'
        f'{game_date} &nbsp; | &nbsp; {game["kickoff"]} '
        f'&nbsp; | &nbsp; {location}</div>'

        f'<div style="margin-top:20px;font-weight:800;'
        f'color:{info["secondary"]}">{outlook}</div>'

        f'<div style="font-size:42px;font-weight:900;'
        f'margin-top:5px">{win_probability:.0%}</div>'

        f'<div style="font-size:11px;letter-spacing:2px;'
        f'opacity:.7">ESTIMATED WIN PROBABILITY</div>'

        f'</div>',
        unsafe_allow_html=True,
    )

    st.caption(
        f"Your team's overall rating: {team_rating:.1f} "
        f"| Opponent rating: {opponent_rating:.1f}"
    )
    advantages, concerns = build_matchup_analysis(
        team_stats,
        opponent_stats,
    )

    player_highlights = build_player_highlights(code, opponent)

    st.markdown("### PLAYER HIGHLIGHTS")
    if player_highlights:
        highlight_cards = [
            ("POSITIVE INDIVIDUAL MATCHUP", player_highlights["positive_player"], True, "player"),
            ("POSITIVE POSITION-GROUP MATCHUP", player_highlights["positive_group"], True, "group"),
            ("NEGATIVE INDIVIDUAL MATCHUP", player_highlights["negative_player"], False, "player"),
            ("NEGATIVE POSITION-GROUP MATCHUP", player_highlights["negative_group"], False, "group"),
        ]
        highlight_rows = [highlight_cards[:2], highlight_cards[2:]]
        for row_items in highlight_rows:
            highlight_cols = st.columns(2, gap="large")
            for col, (label, item, positive_flag, kind) in zip(highlight_cols, row_items):
                with col:
                    tone = "#39B879" if positive_flag else "#D46B6B"
                    bg = "#14251F" if positive_flag else "#261A1D"
                    name = item["name"] if kind == "player" else item["name"]
                    detail = (
                        f'{item["position"]} · {item["group"]}' if kind == "player"
                        else f'{item["volume"]:,} plays · {item["yards"]:,.0f} total yards'
                    )
                    stat = (
                        f'{item["yards"]:,.0f} yards · {item["volume"]:,} opportunities'
                        if kind == "player" and item.get("side") != "defense" else
                        f'{item["volume"]:,} defensive events · {item["efficiency"]:+.3f} impact index'
                        if kind == "player" else f'{item["efficiency"]:+.3f} efficiency index'
                    )
                    explanation = (
                        "A high-impact producer for this team, selected from a meaningful workload."
                        if positive_flag and kind == "player" else
                        "The lowest-efficiency player in the qualified workload sample; this is a performance flag, not a judgment of talent."
                        if kind == "player" else
                        "The strongest season-to-date position group by average play efficiency."
                        if positive_flag else
                        "The lowest season-to-date position-group efficiency among groups with a meaningful sample."
                    )
                    card = f"""
                    <div style="background:{bg};border:1px solid #344155;border-left:4px solid {tone};border-radius:14px;padding:17px 18px;min-height:174px;margin-bottom:14px;">
                      <div style="font-size:10px;letter-spacing:1.5px;font-weight:850;color:{tone};">{label}</div>
                      <div style="display:flex;align-items:center;gap:10px;margin-top:13px;">
                        {logo(code, 42)}
                        <div style="font-size:20px;font-weight:850;line-height:1.2;color:#F1F4F8;">{html.escape(str(name))}</div>
                      </div>
                      <div style="font-size:11px;color:#AAB6C5;margin-top:8px;">{html.escape(str(detail))}</div>
                      <div style="font-size:15px;font-weight:800;color:#E7EDF5;margin-top:7px;">{html.escape(str(stat))}</div>
                      <div style="font-size:11px;line-height:1.45;color:#9EABBC;margin-top:8px;">{html.escape(explanation)}</div>
                    </div>
                    """
                    st.markdown(card, unsafe_allow_html=True)
        st.caption(f"{player_highlights['sample_note']} Highlights use completed-week play-by-play and minimum workload thresholds; unavailable position groups are not invented.")
    else:
        st.info("Player and position-group highlights will appear when the cached play-by-play contains enough player-level production and roster-position data.")

TEAM_SLOGANS = {
    "ARI": "RISE UP RED SEA.", "ATL": "RISE UP.", "BAL": "PLAY LIKE A RAVEN.",
    "BUF": "LET'S GO BUFFALO.", "CAR": "KEEP POUNDING.", "CHI": "BEAR DOWN.",
    "CIN": "WHO DEY.", "CLE": "HERE WE GO BROWNIES.",
    "DAL": "HOW 'BOUT THEM COWBOYS.", "DEN": "BRONCOS COUNTRY. LET'S RIDE.",
    "DET": "ONE PRIDE.", "GB": "GO PACK GO.", "HOU": "HOUSTON, STAND UP.",
    "IND": "FOR THE SHOE.", "JAX": "DUUUUUUVAL.", "KC": "ARROWHEAD IS OURS.",
    "LV": "JUST WIN, BABY.", "LAC": "BOLT UP.", "LAR": "RAMS HOUSE.",
    "MIA": "FINS UP.", "MIN": "SKOL.", "NE": "DO YOUR JOB.",
    "NO": "WHO DAT.", "NYG": "BIG BLUE PRIDE.",
    "NYJ": "J-E-T-S. JETS! JETS! JETS!", "PHI": "FLY EAGLES FLY.",
    "PIT": "HERE WE GO, STEELERS.", "SF": "FAITHFUL TO THE BAY.",
    "SEA": "SEAHAWKS. SEAHAWKS.", "TB": "FIRE THE CANNONS.",
    "TEN": "TITAN UP.", "WAS": "HAIL TO THE COMMANDERS.",
}


WAR_ROOM_SUBSTATS = {
    "OFFENSE": [
        ("EPA per play", "off_epa_per_play", False, "EPA"),
        ("Success rate", "off_success_rate", False, "%"),
        ("Yards per play", "off_yards_per_play", False, "yds"),
        ("Pass EPA per play", "pass_epa_per_play", False, "EPA"),
        ("Rush EPA per play", "rush_epa_per_play", False, "EPA"),
        ("Third-down conversion", "third_down_conversion_rate", False, "%"),
        ("Fourth-down conversion", "fourth_down_conversion_rate", False, "%"),
        ("Red-zone TD rate", "red_zone_td_rate", False, "%"),
        ("Explosive-play rate", "overall_explosive_rate", False, "%"),
        ("Sack rate allowed", "sack_rate_allowed", True, "%"),
        ("Giveaways", "total_giveaways", True, "count"),
    ],
    "DEFENSE": [
        ("EPA allowed per play", "def_epa_allowed_per_play", True, "EPA"),
        ("Success rate allowed", "def_success_rate_allowed", True, "%"),
        ("Yards allowed per play", "def_yards_allowed_per_play", True, "yds"),
        ("Pass EPA allowed", "pass_epa_allowed_per_play", True, "EPA"),
        ("Rush EPA allowed", "rush_epa_allowed_per_play", True, "EPA"),
        ("Explosive-play rate allowed", "overall_explosive_rate_allowed", True, "%"),
        ("Interceptions", "interceptions", False, "count"),
        ("Sacks recorded", "sacks_recorded", False, "count"),
        ("QB hits generated", "qb_hits_generated", False, "count"),
    ],
    "SPECIAL TEAMS": [
        ("Field-goal make rate", "fg_make_rate", False, "%"),
        ("Extra-point success", "xp_success_rate", False, "%"),
        ("Punts inside 20 rate", "punt_inside_twenty_rate", False, "%"),
        ("Punt touchback rate", "punt_touchback_rate", True, "%"),
        ("Punt-return yards/opportunity", "punt_return_yards_per_opportunity", False, "yds"),
        ("Kick-return yards/opportunity", "kickoff_return_yards_per_opportunity", False, "yds"),
    ],
    "DISCIPLINE": [
        ("Penalty flags", "penalty_flags", True, "count"),
        ("Penalty yards", "penalty_yards", True, "yds"),
        ("First-down penalties", "first_down_penalties", True, "count"),
        ("Penalty yards per flag", "penalty_yards_per_flag", True, "yds"),
    ],
    "ON-FIELD": [
        ("Win percentage", "on_field_win_percentage", False, "%"),
        ("Points scored/game", "on_field_points_scored_per_game", False, "pts"),
        ("Points allowed/game", "on_field_points_allowed_per_game", True, "pts"),
        ("Average point differential", "on_field_avg_point_differential", False, "pts"),
        ("Strength of wins", "on_field_strength_of_wins", False, "score"),
        ("Quality wins", "on_field_quality_wins", False, "count"),
        ("Bad losses", "on_field_bad_losses", True, "count"),
    ],
}


def radar_svg(team_one, team_two, name_one, name_two):
    """Small dependency-free five-axis radar chart."""
    labels = ["OFF", "DEF", "ST", "DISC", "FIELD"]
    cx, cy, radius = 250, 190, 125
    angles = [-90, -18, 54, 126, 198]
    def points(values):
        coords = []
        for value, angle in zip(values, angles):
            r = radius * max(0, min(100, float(value))) / 100
            rad = math.radians(angle)
            coords.append((cx + r * math.cos(rad), cy + r * math.sin(rad)))
        return " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)
    grid = []
    for scale in (25, 50, 75, 100):
        coords = []
        for angle in angles:
            rad = math.radians(angle)
            coords.append((cx + radius * scale / 100 * math.cos(rad),
                           cy + radius * scale / 100 * math.sin(rad)))
        grid.append(f'<polygon points="{" ".join(f"{x:.1f},{y:.1f}" for x,y in coords)}" fill="none" stroke="#526071" stroke-width="1" opacity=".55"/>')
    axes = []
    label_nodes = []
    for label, angle in zip(labels, angles):
        rad = math.radians(angle)
        x2, y2 = cx + radius * math.cos(rad), cy + radius * math.sin(rad)
        axes.append(f'<line x1="{cx}" y1="{cy}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#526071" opacity=".7"/>')
        lx, ly = cx + (radius + 24) * math.cos(rad), cy + (radius + 24) * math.sin(rad)
        label_nodes.append(f'<text x="{lx:.1f}" y="{ly:.1f}" fill="#D7DEE8" font-size="11" text-anchor="middle" dominant-baseline="middle">{label}</text>')
    return (
        '<div style="width:100%;overflow:hidden"><svg viewBox="0 0 500 390" role="img" aria-label="Weighted five-pillar radar comparison" style="width:100%;max-width:620px;display:block;margin:auto">'
        + "".join(grid) + "".join(axes)
        + f'<polygon points="{points(team_one)}" fill="#55A6FF" fill-opacity=".20" stroke="#55A6FF" stroke-width="3"/>'
        + f'<polygon points="{points(team_two)}" fill="#E6B85C" fill-opacity=".18" stroke="#E6B85C" stroke-width="3"/>'
        + "".join(label_nodes)
        + f'<text x="135" y="365" fill="#55A6FF" font-size="12" text-anchor="middle">{html.escape(name_one)}</text>'
        + f'<text x="365" y="365" fill="#E6B85C" font-size="12" text-anchor="middle">{html.escape(name_two)}</text>'
        + '</svg></div>'
    )


def render_team_profile_storylines(code, info, record):
    """Render season storylines and the last-five-games section."""
    insights = build_team_profile_storylines(
        team_code=code,
        team_metrics=team_metrics,
        rankings=rankings,
        games=get_results(),
        teams=TEAMS,
        record=record,
    )

    storylines = insights["storylines"]
    section("STORYLINES")

    st.markdown(
        f'<div class="panel" style="border-color:{info["color"]};">'
        f'<div class="micro">SEASON HEADLINE</div>'
        f'<div style="font-size:24px;font-weight:950;line-height:1.25;margin:8px 0">'
        f'{html.escape(storylines["main_headline"])}</div>'
        f'<div style="font-size:15px;line-height:1.8;color:#E8E1D8">{html.escape(storylines["main_detail"])}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    supporting = storylines["supporting"]
    # Cozy, colorful 2x2 grid: two offense stories, then two defense stories.
    story_groups = [
        ("OFFENSE", "#F2A65A", "#332419", supporting.get("offense", []), "🏈"),
        ("DEFENSE", "#72C6B5", "#18302D", supporting.get("defense", []), "🛡️"),
    ]
    for label, accent, tint, items, emoji in story_groups:
        st.markdown(
            f'<div style="margin:18px 0 9px;font-size:17px;font-weight:950;letter-spacing:.4px;color:{accent}">'
            f'{emoji} {label} STORYLINES</div>', unsafe_allow_html=True
        )
        story_cols = st.columns(2)
        for column, item in zip(story_cols, items):
            with column:
                st.markdown(
                    f'<div style="background:linear-gradient(145deg,{tint},#1B2230);'
                    f'border:1px solid {accent}66;border-left:5px solid {accent};border-radius:18px;'
                    f'padding:18px 18px 20px;min-height:170px;box-shadow:0 5px 18px rgba(0,0,0,.18);margin-bottom:10px">'
                    f'<div style="font-size:11px;font-weight:900;letter-spacing:1.5px;color:{accent};margin-bottom:8px">'
                    f'{label} · FULL-SEASON STORY</div>'
                    f'<div style="font-size:19px;font-weight:950;line-height:1.35;margin:5px 0 10px;color:#FFF4E6">'
                    f'{html.escape(item["headline"])}</div>'
                    f'<div style="font-size:14px;line-height:1.75;color:#E6E2DC">'
                    f'{html.escape(item["description"])}</div></div>',
                    unsafe_allow_html=True,
                )

    section("RECENT")
    st.markdown(
        f'<div style="font-size:22px;font-weight:900;margin-bottom:5px">'
        f'{html.escape(insights["five_game_title"])}</div>'
        f'<div class="micro">LAST FIVE RECORD: {html.escape(insights["five_game_record"])}</div>'
        f'<div style="font-size:13px;line-height:1.7;margin:8px 0 15px">'
        f'{html.escape(insights["five_game_detail"])}</div>',
        unsafe_allow_html=True,
    )

    last_five = insights["last_five"]
    if not last_five:
        st.info("No completed games are available for the five-game results display.")
        return

    result_cols = st.columns(len(last_five))
    for column, game in zip(result_cols, last_five):
        result_color = {"W": "#42C879", "L": "#F06B6B", "T": "#D8B86D"}[game["result"]]
        result_label = {"W": "WIN", "L": "LOSS", "T": "TIE"}[game["result"]]
        with column:
            st.markdown(
                f'<div style="background:#171D27;border:1px solid #344155;border-radius:12px;'
                f'padding:12px;text-align:center;min-height:190px">'
                f'<div class="micro">WEEK {game["week"]}</div>'
                f'<div style="margin:8px 0">{logo(game["opponent"], 54)}</div>'
                f'<div style="font-size:12px;font-weight:800;min-height:32px">'
                f'{html.escape(game["opponent_name"])}</div>'
                f'<div style="font-size:12px;font-weight:900;color:{result_color};margin:7px 0">'
                f'{result_label}</div>'
                f'<div style="font-size:18px;font-weight:900">'
                f'{game["team_score"]} – {game["opponent_score"]}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
    if len(last_five) < 5:
        st.caption(f"Only {len(last_five)} completed game(s) are available; missing games are not fabricated.")


def render_profile():
    code = st.session_state.selected_team

    if code not in TEAMS:
        st.warning("Choose a team first.")
        go("TEAMS")
        return

    row = get_team_row(code)
    dna_row = get_team_row(code, team_metrics)

    if row is None:
        st.error(f"No ratings found for {code} in the CSV.")
        return

    if dna_row is None:
        st.error(f"No Team DNA metrics found for {code}.")
        return

    info = TEAMS[code]

    if st.session_state.play_entrance:
        effects = {
            "claws": ("THE HUNT IS ON.", "claws"),
            "fire": ("BRING THE HEAT.", "fx fx-fire"),
            "lightning": ("STRIKE FIRST.", "fx fx-lightning"),
            "storm": ("WEATHER THE STORM.", "fx fx-storm"),
            "wave": ("MAKE YOUR OWN WAVE.", "fx fx-wave"),
            "speed": ("TOO FAST TO CATCH.", "fx fx-speed"),
            "spotlight": ("THIS IS OUR STAGE.", "fx fx-spotlight"),
        }

        _, effect_class = effects[info["effect"]]
        tagline = TEAM_SLOGANS.get(code, "BUILT TO COMPETE.")

        claws = (
            '<div class="claw c1"></div><div class="claw c2"></div><div class="claw c3"></div>'
            if info["effect"] == "claws" else ""
        )

        st.markdown(
            f'<div class="cinematic {effect_class}" style="--team:{info["color"]};--team2:{info["secondary"]}">'
            f'{claws}<div class="intro-content"><div class="intro-kicker">NFL RATINGS / TEAM INTRODUCTION</div>'
            f'<img class="intro-logo" src="{info["logo"]}" alt="{html.escape(info["name"])}">'
            f'<div class="intro-team">{html.escape(info["name"])}</div>'
            f'<div class="intro-tag">{tagline}</div></div></div>',
            unsafe_allow_html=True,
        )

        st.session_state.play_entrance = False

    # --------------------------------------------------------
    # TEAM HEADER
    # --------------------------------------------------------

    rank = int(row["rank"])
    overall = float(row["overall_rating"])
    classification = grade_label(overall)

    st.markdown(
        f'<div class="profile-hero" style="--team:{info["color"]}">'
        f'<div class="micro">NFL RATINGS / TEAM PROFILE / {code} / {info["conf"]} {info["div"]}</div>'
        f'<div style="display:flex;align-items:center;justify-content:space-between;gap:25px;flex-wrap:wrap">'
        f'<div style="flex:1;min-width:240px"><div class="profile-name">{html.escape(info["name"])}</div>'
        f'<div class="micro" style="margin-top:18px">LEAGUE RANK #{rank:02d}</div>'
        f'<div class="big-rating">{overall:.1f}</div>'
        f'<div class="micro">OVERALL RATING</div>'
        f'<div class="tier">{html.escape(classification.upper())}</div></div>'
        f'<div style="text-align:center">{logo(code, 220)}</div></div></div>',
        unsafe_allow_html=True,
    )

    record = get_records()[code]

    st.markdown(
        f'<div class="micro" style="margin:15px 0">'
        f'CURRENT SEASON RECORD: '
        f'<span style="color:#E5D4AD;font-size:22px">'
        f'{record["W"]}-{record["L"]}-{record["T"]}'
        f'</span> &nbsp; / &nbsp; '
        f'WIN PERCENTAGE: {record["PCT"]:.3f} '
        f'&nbsp; / &nbsp; POINT DIFFERENTIAL: {record["DIFF"]:+d}'
        f'</div>',
        unsafe_allow_html=True,
    )


    values = [(label, float(row[col])) for label, col, _ in CATEGORIES]
    strongest = max(values, key=lambda item: item[1])
    weakest = min(values, key=lambda item: item[1])

    cols = st.columns(3)

    with cols[0]:
        metric("STRONGEST CATEGORY", strongest[0])

    with cols[1]:
        metric("WEAKEST CATEGORY", weakest[0])

    with cols[2]:
        metric("OVERALL RATING", f"{overall:.1f}")

    # --------------------------------------------------------
    # ATTRIBUTE BREAKDOWN
    # --------------------------------------------------------

    section("ATTRIBUTE BREAKDOWN")

    left, right = st.columns([3, 2])

    with left:
        for label, col, short in CATEGORIES:
            rating_bar(label, float(row[col]), info["color"])

    with right:
        st.markdown(
            '<div class="panel"><div class="micro">TEAM IDENTITY</div>'
            f'<b>{info["conf"]} {info["div"]}</b><br>'
            f'<b>League position:</b> #{rank} of {len(rankings)}<br>'
            f'<b>Overall rating:</b> {overall:.2f}<br>'
            f'<b>Above/below league average:</b> '
            f'{overall - rankings["overall_rating"].mean():+.2f}</div>',
            unsafe_allow_html=True,
        )

    # ========================================================
    # TEAM DNA
    # ========================================================

    section("TEAM DNA")

    # --------------------------------------------------------
    # OFFENSIVE IDENTITY
    # --------------------------------------------------------

    st.markdown("### OFFENSIVE IDENTITY")

    render_dna_heatmap(
        "PASSING PERFORMANCE — EPA PER PLAY",
        [
            ("Short Left", "dna_off_pass_epa_short_left",
             "dna_off_pass_plays_short_left"),
            ("Short Middle", "dna_off_pass_epa_short_middle",
             "dna_off_pass_plays_short_middle"),
            ("Short Right", "dna_off_pass_epa_short_right",
             "dna_off_pass_plays_short_right"),
            ("Deep Left", "dna_off_pass_epa_deep_left",
             "dna_off_pass_plays_deep_left"),
            ("Deep Middle", "dna_off_pass_epa_deep_middle",
             "dna_off_pass_plays_deep_middle"),
            ("Deep Right", "dna_off_pass_epa_deep_right",
             "dna_off_pass_plays_deep_right"),
        ],
        dna_row,
        team_metrics,
    )

    render_dna_heatmap(
        "RUSHING PERFORMANCE — EPA PER PLAY",
        [
            ("Left", "dna_off_rush_epa_left",
             "dna_off_rush_plays_left"),
            ("Middle", "dna_off_rush_epa_middle",
             "dna_off_rush_plays_middle"),
            ("Right", "dna_off_rush_epa_right",
             "dna_off_rush_plays_right"),
        ],
        dna_row,
        team_metrics,
    )

    # --------------------------------------------------------
    # DEFENSIVE IDENTITY
    # --------------------------------------------------------

    st.markdown("### DEFENSIVE IDENTITY")

    render_dna_heatmap(
        "PASSING DEFENSE — EPA ALLOWED PER PLAY",
        [
            ("Short Left", "dna_def_pass_epa_allowed_short_left",
             "dna_def_pass_plays_short_left"),
            ("Short Middle", "dna_def_pass_epa_allowed_short_middle",
             "dna_def_pass_plays_short_middle"),
            ("Short Right", "dna_def_pass_epa_allowed_short_right",
             "dna_def_pass_plays_short_right"),
            ("Deep Left", "dna_def_pass_epa_allowed_deep_left",
             "dna_def_pass_plays_deep_left"),
            ("Deep Middle", "dna_def_pass_epa_allowed_deep_middle",
             "dna_def_pass_plays_deep_middle"),
            ("Deep Right", "dna_def_pass_epa_allowed_deep_right",
             "dna_def_pass_plays_deep_right"),
        ],
        dna_row,
        team_metrics,
        defensive=True,
    )

    render_dna_heatmap(
        "RUSHING DEFENSE — EPA ALLOWED PER PLAY",
        [
            ("Left", "dna_def_rush_epa_allowed_left",
             "dna_def_rush_plays_left"),
            ("Middle", "dna_def_rush_epa_allowed_middle",
             "dna_def_rush_plays_middle"),
            ("Right", "dna_def_rush_epa_allowed_right",
             "dna_def_rush_plays_right"),
        ],
        dna_row,
        team_metrics,
        defensive=True,
    )

    # --------------------------------------------------------
    # SITUATIONAL PERFORMANCE
    # --------------------------------------------------------

    section("SITUATIONAL PERFORMANCE")

    situation_groups = [
        {
            "title": "SITUATIONAL OFFENSE",
            "stats": [
                ("Third Down", "dna_third_down_conversion_rate",
                 "dna_third_down_attempts"),
                ("Fourth Down", "dna_fourth_down_conversion_rate",
                 "dna_fourth_down_attempts"),
                ("Red Zone TD Rate", "dna_red_zone_td_rate",
                 "dna_red_zone_trips"),
                ("Red Zone Scoring", "dna_red_zone_scoring_rate",
                 "dna_red_zone_trips"),
            ],
        },
        {
            "title": "SITUATIONAL DEFENSE",
            "stats": [
                ("Third Down Allowed", "dna_third_down_conversion_rate_allowed",
                 "dna_third_down_attempts_allowed"),
                ("Fourth Down Allowed", "dna_fourth_down_conversion_rate_allowed",
                 "dna_fourth_down_attempts_allowed"),
                ("Red Zone TD Rate Allowed", "dna_red_zone_td_rate_allowed",
                 "dna_red_zone_trips_allowed"),
                ("Red Zone Scoring Allowed", "dna_red_zone_scoring_rate_allowed",
                 "dna_red_zone_trips_allowed"),
            ],
        },
    ]

    for group in situation_groups:
        st.markdown(f"### {group['title']}")

        cols = st.columns(4)

        for index, (label, rate_col, attempts_col) in enumerate(group["stats"]):
            rate = pd.to_numeric(
                pd.Series([dna_row[rate_col]]), errors="coerce"
            ).iloc[0]

            attempts = pd.to_numeric(
                pd.Series([dna_row[attempts_col]]), errors="coerce"
            ).iloc[0]

            with cols[index]:
                st.metric(
                    label,
                    f"{rate:.1%}" if pd.notna(rate) else "N/A",
                )

                st.caption(
                    f"{int(attempts)} attempts/trips"
                    if pd.notna(attempts) else "Sample unavailable"
                )

    # --------------------------------------------------------
    # STATISTICAL STRENGTHS AND WEAKNESSES
    # --------------------------------------------------------

    section("STATISTICAL STRENGTHS & WEAKNESSES")

    strengths, weaknesses = get_dna_strengths_weaknesses(
        dna_row, team_metrics
    )

    def format_dna_value(item):
        if "rate" in item["label"].lower() or "success" in item["label"].lower():
            return f"{item['value']:.1%}"

        return f"{item['value']:.2f}"

    left, right = st.columns(2)

    with left:
        st.markdown("### TOP STRENGTHS")

        for item in strengths:
            st.markdown(
                f"**{item['label']}**  \n"
                f"{format_dna_value(item)} · "
                f"{item['percentile']:.0f}th percentile"
            )

    with right:
        st.markdown("### AREAS TO IMPROVE")

        for item in weaknesses:
            st.markdown(
                f"**{item['label']}**  \n"
                f"{format_dna_value(item)} · "
                f"{item['percentile']:.0f}th percentile"
            )

    render_team_profile_storylines(code, info, record)


    render_up_next(code, info)

    # --------------------------------------------------------
    # LEADERSHIP & HOT SEATS — dedicated module, before Most Similar
    # --------------------------------------------------------

    render_team_profile_leadership(
        code, info, row, record, metrics_row=dna_row, league_metrics=team_metrics,
        recent_form=get_team_momentum(code).get("recent_form", [])
    )

    # --------------------------------------------------------
    # MOST SIMILAR TEAMS
    # --------------------------------------------------------

    section("MOST SIMILAR")

    similar_teams = get_most_similar_teams(
        code, team_metrics, limit=3
    )

    if similar_teams.empty:
        st.info("Similar team profiles are not available.")

    else:
        st.caption(
            "These teams have the closest statistical profiles "
            "across offensive tendencies, defensive tendencies, "
            "efficiency, and situational performance."
        )

        for _, similar in similar_teams.iterrows():
            near = get_team_row(similar["team"])

            if near is not None:
                rank_row(
                    near,
                    f"similar_{code}_{similar['team']}"
                )

    if st.button("← BACK TO ALL TEAMS", key="profile_back"):
        go("TEAMS")



# ============================================================
# WAR ROOM
# ============================================================

def render_war_room():
    hero("THE MATCHUP CENTER", "THE", "WAR ROOM.", "TWO TEAMS. FIVE PILLARS. A WEIGHTED HEAD-TO-HEAD.")
    if rankings is None:
        st.error("Rankings CSV could not be loaded.")
        return

    codes = list(TEAMS.keys())
    safe_one = st.session_state.war_one if st.session_state.war_one in codes else "SF"
    safe_two = st.session_state.war_two if st.session_state.war_two in codes else "KC"
    a, b = st.columns(2)
    with a:
        one = st.selectbox(
            "TEAM ONE", codes, index=codes.index(safe_one),
            format_func=lambda code: TEAMS[code]["name"], key="war_pick_one"
        )
    with b:
        two = st.selectbox(
            "TEAM TWO", codes, index=codes.index(safe_two),
            format_func=lambda code: TEAMS[code]["name"], key="war_pick_two"
        )
    st.session_state.war_one, st.session_state.war_two = one, two
    if one == two:
        st.warning("Choose two different teams.")
        return

    r1, r2 = get_team_row(one), get_team_row(two)
    m1, m2 = get_team_row(one, team_metrics), get_team_row(two, team_metrics)
    if r1 is None or r2 is None:
        st.error("One of the selected teams is missing from the ratings file.")
        return
    i1, i2 = TEAMS[one], TEAMS[two]

    c1, cv, c2 = st.columns([2, 1, 2])
    with c1:
        st.markdown(
            f'<div class="panel" style="text-align:center;border-top:5px solid {i1["color"]}">'
            f'{logo(one, 130)}<div class="profile-name" style="font-size:44px">{html.escape(i1["name"])}</div>'
            f'<div class="big-rating">{float(r1["overall_rating"]):.1f}</div>'
            f'<div class="micro">RANK #{int(r1["rank"])}</div></div>',
            unsafe_allow_html=True,
        )
    with cv:
        st.markdown(
            '<div style="font-family:Barlow Condensed;font-size:70px;font-weight:900;'
            'text-align:center;padding-top:70px;color:#B99A5A">VS</div>',
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f'<div class="panel" style="text-align:center;border-top:5px solid {i2["color"]}">'
            f'{logo(two, 130)}<div class="profile-name" style="font-size:44px">{html.escape(i2["name"])}</div>'
            f'<div class="big-rating">{float(r2["overall_rating"]):.1f}</div>'
            f'<div class="micro">RANK #{int(r2["rank"])}</div></div>',
            unsafe_allow_html=True,
        )

    section("PILLAR WEIGHTS")
    st.caption("Adjust the importance of each pillar. The weighted scores and radar chart update with your selections.")
    weight_cols = st.columns(5)
    weights = {}
    defaults = [20, 20, 20, 20, 20]
    for index, (label, _, _) in enumerate(CATEGORIES):
        with weight_cols[index]:
            weights[label] = st.slider(
                label, min_value=0, max_value=100, value=defaults[index],
                step=5, key=f"war_weight_{index}"
            )
    if sum(weights.values()) == 0:
        st.warning("Set at least one pillar weight above zero.")
        return

    weighted_one = 0.0
    weighted_two = 0.0
    weight_total = float(sum(weights.values()))
    radar_one, radar_two = [], []
    wins1 = wins2 = ties = 0
    section("CATEGORY SHOWDOWN")
    for label, col, _ in CATEGORIES:
        v1, v2 = float(r1[col]), float(r2[col])
        weight = weights[label]
        weighted_one += v1 * weight
        weighted_two += v2 * weight
        radar_one.append(v1 * weight / 100.0)
        radar_two.append(v2 * weight / 100.0)
        if v1 > v2:
            wins1 += 1
            edge = i1["name"]
        elif v2 > v1:
            wins2 += 1
            edge = i2["name"]
        else:
            ties += 1
            edge = "TIE"
        st.markdown(f"**{label}** · Weight {weight}%")
        x, y, z = st.columns([2, 1, 2])
        with x:
            st.metric(i1["name"], f"{v1:.1f}", delta=f"{v1-v2:+.1f}")
        with y:
            st.markdown(
                '<div style="text-align:center;padding-top:24px;font-family:Barlow Condensed;'
                'font-size:30px;color:#B99A5A">VS</div>',
                unsafe_allow_html=True,
            )
        with z:
            st.metric(i2["name"], f"{v2:.1f}", delta=f"{v2-v1:+.1f}")
        st.caption(
            f"Category edge: {edge} · Weighted contribution: "
            f"{v1 * weight / 100.0:.2f} vs {v2 * weight / 100.0:.2f}"
        )

    weighted_one /= weight_total
    weighted_two /= weight_total
    section("WEIGHTED SPIDER COMPARISON")
    st.markdown(radar_svg(radar_one, radar_two, i1["name"], i2["name"]), unsafe_allow_html=True)
    wc1, wc2 = st.columns(2)
    wc1.metric(f"{one} WEIGHTED PILLAR SCORE", f"{weighted_one:.2f}")
    wc2.metric(f"{two} WEIGHTED PILLAR SCORE", f"{weighted_two:.2f}")

    section("UNDERLYING STAT COMPARISON")
    if m1 is None or m2 is None:
        st.info("Underlying team metrics are unavailable for one or both teams.")
    else:
        for category, metrics in WAR_ROOM_SUBSTATS.items():
            available = [
                (label, col, lower_better, unit)
                for label, col, lower_better, unit in metrics
                if col in m1.index and col in m2.index
                and pd.notna(m1[col]) and pd.notna(m2[col])
            ]
            if not available:
                continue
            with st.expander(category, expanded=(category == "OFFENSE")):
                rows = []
                for label, col, lower_better, unit in available:
                    value_one, value_two = float(m1[col]), float(m2[col])
                    if math.isclose(value_one, value_two, rel_tol=1e-9, abs_tol=1e-9):
                        edge = "TIE"
                    else:
                        one_better = value_one < value_two if lower_better else value_one > value_two
                        edge = i1["name"] if one_better else i2["name"]
                    if unit == "%":
                        display_one, display_two = f"{value_one:.1%}", f"{value_two:.1%}"
                    elif unit == "EPA":
                        display_one, display_two = f"{value_one:+.3f}", f"{value_two:+.3f}"
                    else:
                        display_one, display_two = f"{value_one:,.2f}", f"{value_two:,.2f}"
                    rows.append({
                        "Metric": label, i1["name"]: display_one,
                        i2["name"]: display_two, "Edge": edge,
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    section("THE FINAL VERDICT")
    # Preserve the original verdict: it remains based on the official overall ratings.
    v1, v2 = float(r1["overall_rating"]), float(r2["overall_rating"])
    winner = i1["name"] if v1 > v2 else i2["name"] if v2 > v1 else "Neither team"
    left, mid, right = st.columns(3)
    with left:
        metric(f"{one} CATEGORY WINS", wins1)
    with mid:
        metric("TIES", ties)
    with right:
        metric(f"{two} CATEGORY WINS", wins2)
    if winner != "Neither team":
        st.markdown(f"### {winner} has the stronger overall rating by {abs(v1-v2):.2f} points.")
    else:
        st.markdown("### The overall ratings are tied.")
    st.caption("The weighted comparison is a user-adjustable analytical view. The Final Verdict remains based on the model's official overall ratings.")


# ============================================================
# HISTORY + MOVEMENT
# ============================================================

def render_history():
    hero("THE LONG GAME", "RATINGS", "HISTORY.", "THE TEAM MARKET — TRACKING REAL RATING MOVEMENT AND WEEKLY RESULTS.")
    history = read_history()
    results = get_results()
    latest_week = get_latest_completed_week()

    if latest_week is not None:
        week_games = []
        for game in results:
            try:
                game_week = int(game.get("week"))
                home_score = int(game.get("home_score"))
                away_score = int(game.get("away_score"))
            except (TypeError, ValueError):
                continue
            if game_week == latest_week:
                week_games.append((game, home_score, away_score))

        section(f"WEEK {latest_week} — WINNERS & LOSERS")
        if week_games:
            winners, losers = [], []
            for game, home_score, away_score in week_games:
                if home_score == away_score:
                    continue
                winner = game["home"] if home_score > away_score else game["away"]
                loser = game["away"] if home_score > away_score else game["home"]
                winners.append((winner, max(home_score, away_score), min(home_score, away_score)))
                losers.append((loser, min(home_score, away_score), max(home_score, away_score)))
            left, right = st.columns(2)
            with left:
                st.markdown("### WEEKLY WINNERS")
                for team, scored, allowed in winners:
                    st.markdown(f"**{TEAMS.get(team, {}).get('name', team)}** · {scored}–{allowed}")
            with right:
                st.markdown("### WEEKLY LOSERS")
                for team, scored, allowed in losers:
                    st.markdown(f"**{TEAMS.get(team, {}).get('name', team)}** · {scored}–{allowed}")
        else:
            st.info("No completed games are recorded for the latest completed week.")
    else:
        st.info("No completed game results are available yet.")

    section("THE TEAM MARKET")
    if not history:
        st.info("No rating snapshots exist yet. A snapshot is created automatically when the ratings CSV changes.")
        return

    st.markdown(f"**Recorded rating snapshots:** {len(history)}")
    st.caption(
        "Rating movement is calculated only from saved ratings snapshots. "
        "Weekly game results are shown separately and are not treated as rating movement."
    )
    required = {"team", "rank", "overall_rating"}
    weekly_by_number = {}
    for snapshot in history:
        try:
            snapshot_week = int(snapshot.get("week"))
        except (TypeError, ValueError):
            continue
        weekly_by_number[snapshot_week] = snapshot
    weekly_history = [weekly_by_number[week] for week in sorted(weekly_by_number)]

    if len(weekly_history) >= 2:
        previous, latest = weekly_history[-2], weekly_history[-1]
        old = pd.DataFrame(previous.get("teams", []))
        new = pd.DataFrame(latest.get("teams", []))
        if not required.issubset(old.columns) or not required.issubset(new.columns):
            st.warning("A saved weekly snapshot is missing the required team data.")
            return
        merged = old[["team", "rank", "overall_rating"]].merge(
            new[["team", "rank", "overall_rating"]], on="team", suffixes=("_previous", "_latest")
        )
        merged["rank_change"] = merged["rank_previous"] - merged["rank_latest"]
        merged["rating_change"] = merged["overall_rating_latest"] - merged["overall_rating_previous"]
        merged["name"] = merged["team"].map(lambda code: TEAMS.get(code, {}).get("name", code))
        left, right = st.columns(2)
        with left:
            section(f"BIGGEST RISERS — WEEK {previous.get('week')} TO {latest.get('week')}")
            for _, row in merged.sort_values("rank_change", ascending=False).head(5).iterrows():
                st.markdown(f"**{row['name']}** · {int(row['rank_change']):+d} places · {row['rating_change']:+.2f} rating")
        with right:
            section("BIGGEST FALLERS")
            for _, row in merged.sort_values("rank_change").head(5).iterrows():
                st.markdown(f"**{row['name']}** · {int(row['rank_change']):+d} places · {row['rating_change']:+.2f} rating")
        section("LATEST WEEKLY RATING MOVEMENT")
        movers = merged.sort_values("rating_change", ascending=False)
        st.dataframe(
            movers[["name", "rank_previous", "rank_latest", "rank_change",
                    "overall_rating_previous", "overall_rating_latest", "rating_change"]].rename(columns={
                "name": "Team", "rank_previous": "Previous rank", "rank_latest": "Latest rank",
                "rank_change": "Rank movement", "overall_rating_previous": "Previous rating",
                "overall_rating_latest": "Latest rating", "rating_change": "Rating change",
            }),
            use_container_width=True, hide_index=True,
        )
    else:
        st.info(
            "Weekly rating risers and fallers will appear after the project has saved ratings snapshots for at least two distinct completed weeks. "
            "The current history file does not contain enough week-tagged snapshots to calculate that movement."
        )
    team_choices = sorted(TEAMS, key=lambda code: TEAMS[code]["name"])
    selected = st.selectbox(
        "TEAM MARKET HISTORY", team_choices,
        format_func=lambda code: TEAMS[code]["name"], key="history_team_select",
    )
    series = []
    for snap in history:
        frame = pd.DataFrame(snap.get("teams", []))
        if not {"team", "overall_rating", "rank"}.issubset(frame.columns):
            continue
        match = frame[frame["team"] == selected]
        if not match.empty:
            series.append({
                "Snapshot": snap.get("date", snap.get("captured_at", "")),
                "Overall rating": float(match.iloc[0]["overall_rating"]),
                "Rank": int(match.iloc[0]["rank"]),
            })
    if series:
        chart_data = pd.DataFrame(series).set_index("Snapshot")
        section("RATING STOCK CHART")
        st.line_chart(chart_data[["Overall rating"]], height=300)
        st.line_chart(chart_data[["Rank"]], height=220)

    section("3-, 4- & 5-WEEK RATING TRENDS")
    trend_rows = []
    for span in (3, 4, 5):
        if len(weekly_history) < span + 1:
            trend_rows.append({
                "Window": f"{span}-week rating change",
                "Status": f"Need {span + 1} distinct weekly snapshots; {len(weekly_history)} available",
            })
            continue
        start_frame = pd.DataFrame(weekly_history[-(span + 1)].get("teams", []))
        end_frame = pd.DataFrame(weekly_history[-1].get("teams", []))
        if not required.issubset(start_frame.columns) or not required.issubset(end_frame.columns):
            continue
        joined = start_frame[["team", "overall_rating"]].merge(
            end_frame[["team", "overall_rating"]], on="team", suffixes=("_start", "_end")
        )
        joined["change"] = joined["overall_rating_end"] - joined["overall_rating_start"]
        best = joined.sort_values("change", ascending=False).iloc[0]
        worst = joined.sort_values("change").iloc[0]
        trend_rows.append({
            "Window": f"{span}-week rating change",
            "Hottest": f"{TEAMS.get(best['team'], {}).get('name', best['team'])} ({best['change']:+.2f})",
            "Coldest": f"{TEAMS.get(worst['team'], {}).get('name', worst['team'])} ({worst['change']:+.2f})",
        })
    st.dataframe(pd.DataFrame(trend_rows), use_container_width=True, hide_index=True)


# ============================================================
# METHODOLOGY
# ============================================================

def render_methodology():
    hero("SHOW YOUR WORK", "INSIDE THE", "RATINGS ENGINE.", "WHAT THE NUMBERS MEAN — AND WHAT THEY DO NOT.")
    section("THE FIVE RATING CATEGORIES")
    explanations = [
        ("OFFENSE", "Measures the team's offensive rating as supplied by the existing ratings engine."),
        ("DEFENSE", "Measures the team's defensive rating as supplied by the existing ratings engine."),
        ("SPECIAL TEAMS", "Represents the special-teams rating generated by the existing engine."),
        ("DISCIPLINE", "Represents the discipline rating generated by the existing engine."),
        ("ON-FIELD", "Represents the on-field rating generated by the existing engine."),
    ]
    for label, description in explanations:
        st.markdown(
            f'<div class="panel"><div class="micro">{label}</div><b>{description}</b></div>',
            unsafe_allow_html=True,
        )

    section("HOW TO READ THE OVERALL RATING")
    st.markdown(
        "The overall rating and team order are read directly from `nfl_rankings_2026.csv`. "
        "This website does not recalculate, normalize, or modify those values. "
        "The five category ratings are displayed as supporting attributes."
    )
    st.warning(
        "The exact weighting equation is intentionally not reproduced here because this website must not guess at the formula. "
        "The existing ratings engine remains the source of truth."
    )

    section("RATING SCALE")
    st.markdown(
        "- **Higher rating:** stronger result within this model.\n"
        "- **Lower rating:** weaker result within this model.\n"
        "- **Rank:** position among the 32 teams, based on the CSV.\n"
        "- **Category edge:** the team with the higher value in a specific category."
    )
    section("MODEL LIMITATIONS")
    st.markdown(
        "Ratings are model outputs, not a guarantee of future wins. A head-to-head category comparison is not a game simulation. "
        "The website does not invent game results, weekly movement, or historical values that are not present in its saved data."
    )
    section("DATA SOURCE")
    st.code(str(CSV_PATH), language="text")


# ============================================================
# DATABASE-POWERED NFL RECORDS
# ============================================================


# ============================================================
# WEEKLY CONTROL CENTER — RESULTS, RECORDS + SCHEDULE
# ============================================================


def get_storyline_team_data(code):
    """Gather the data used by the weekly storyline engine."""

    code = str(code).upper()
    metrics_code = {"LAR": "LA"}.get(code, code)

    # Team performance metrics
    metrics = None

    if not team_metrics.empty and "team" in team_metrics.columns:
        matching_metrics = team_metrics[
            team_metrics["team"].astype(str).str.upper()
            == metrics_code
            ]

        if not matching_metrics.empty:
            metrics = matching_metrics.iloc[0].to_dict()

    # Team ratings
    rating_row = get_team_row(code)

    ratings = {}

    if rating_row is not None:
        for column in (
                "rank",
                "overall_rating",
                "offensive_rating",
                "defensive_rating",
                "special_teams_rating",
                "discipline_rating",
                "on_field_rating",
        ):
            if column in rating_row.index:
                ratings[column] = rating_row[column]

    # Recent results and current streak
    momentum = get_team_momentum(code)

    return {
        "code": code,
        "metrics": metrics or {},
        "ratings": ratings,
        "momentum": momentum,
    }


def get_metric_percentile(metric, value, lower_is_better=False):
    """Compare a team's metric against all 32 teams."""

    if metric not in team_metrics.columns:
        return None

    values = pd.to_numeric(
        team_metrics[metric],
        errors="coerce",
    ).dropna()

    if values.empty or pd.isna(value):
        return None

    percentile = (values <= float(value)).mean()

    if lower_is_better:
        percentile = (values >= float(value)).mean()

    return round(float(percentile), 3)


def get_on_field_rating_percentile(value):
    """Compare a team's on-field rating against all 32 teams."""

    values = pd.to_numeric(
        rankings["on_field_rating"],
        errors="coerce",
    ).dropna()

    if values.empty or pd.isna(value):
        return None

    percentile = (values <= float(value)).mean()

    return round(float(percentile), 3)


def get_on_field_rating_level(percentile):
    """Classify on-field rating using league percentiles."""

    if percentile >= 0.80:
        return "ELITE"
    elif percentile >= 0.65:
        return "ABOVE AVERAGE"
    elif percentile <= 0.20:
        return "MAJOR WEAKNESS"
    elif percentile <= 0.35:
        return "BELOW AVERAGE"
    else:
        return "AVERAGE"


def get_record_level(wins, losses, ties):
    """Classify a team's record using winning percentage."""

    games_played = wins + losses + ties

    if games_played < 5:
        return None

    win_percentage = (
                             wins + (ties * 0.5)
                     ) / games_played

    if win_percentage >= 0.600:
        return "STRONG"
    elif win_percentage <= 0.400:
        return "WEAK"
    else:
        return "AVERAGE"


def classify_record_rating(record_level, rating_level):
    """Identify the relationship between record and on-field rating."""

    if record_level == "STRONG" and rating_level in (
            "ELITE", "ABOVE AVERAGE"
    ):
        return "LEGITIMATE_CONTENDER"

    elif record_level == "STRONG" and rating_level in (
            "BELOW AVERAGE", "MAJOR WEAKNESS"
    ):
        return "RECORD_MAY_BE_MISLEADING"

    elif record_level == "WEAK" and rating_level in (
            "ELITE", "ABOVE AVERAGE"
    ):
        return "MORE_DANGEROUS_THAN_RECORD"

    elif record_level == "WEAK" and rating_level in (
            "BELOW AVERAGE", "MAJOR WEAKNESS"
    ):
        return "SIGNIFICANT_IMPROVEMENTS_NEEDED"

    return None


def evaluate_on_field_rating(team, opponent):
    """Evaluate a team's on-field rating relative to its record."""

    metrics = team.get("metrics", {})
    ratings = team.get("ratings", {})

    team_name = team["name"]
    opponent_name = opponent["name"]

    wins = metrics.get("on_field_wins", 0)
    losses = metrics.get("on_field_losses", 0)
    ties = metrics.get("on_field_ties", 0)

    rating = ratings.get("on_field_rating")

    if rating is None or pd.isna(rating):
        return []

    percentile = get_on_field_rating_percentile(rating)

    if percentile is None:
        return []

    rating_level = get_on_field_rating_level(percentile)
    record_level = get_record_level(
        wins,
        losses,
        ties,
    )
    situation = classify_record_rating(
        record_level,
        rating_level,
    )

    return {
        "team": team_name,
        "opponent": opponent_name,
        "record": f"{wins}-{losses}-{ties}",
        "rating": float(rating),
        "percentile": percentile,
        "rating_level": rating_level,
        "record_level": record_level,
        "situation": situation,
    }


def generate_on_field_narrative(team_data):
    """Generate an on-field rating narrative when a meaningful gap exists."""

    situation = team_data.get("situation")

    narratives = {
        "LEGITIMATE_CONTENDER": {
            "headline": "BUILT TO CONTEND",
            "description": (
                "{team} enters this matchup with a record of {record}"
                " and an on-field rating in the {percentile}th "
                "percentile league-wide. Its performance backs up "
                "its winning record, establishing {team} as a "
                "legitimate contender."
            ),
            "score": 78,
        },
        "RECORD_MAY_BE_MISLEADING": {
            "headline": "RECORD DOESN'T TELL THE WHOLE STORY",
            "description": (
                "{team} has put together a record of {record}, but its "
                "on-field rating ranks in just the {percentile}th "
                "percentile league-wide. There may be more questions "
                "about how sustainable that success really is."
            ),
            "score": 82,
        },
        "MORE_DANGEROUS_THAN_RECORD": {
            "headline": "A TEAM THAT CAN'T BE OVERLOOKED",
            "description": (
                "Despite a record of {record}, {team}'s on-field rating "
                "ranks in the {percentile}th percentile league-wide. "
                "Its underlying performance suggests a team that "
                "could be more dangerous than its record indicates."
            ),
            "score": 82,
        },
        "SIGNIFICANT_IMPROVEMENTS_NEEDED": {
            "headline": "PLENTY OF WORK STILL TO DO",
            "description": (
                "{team} enters this matchup with a record of {record}, "
                "while its on-field rating sits in just the "
                "{percentile}th percentile league-wide. The team "
                "has significant areas to improve if it hopes to "
                "turn its season around."
            ),
            "score": 75,
        },
    }

    narrative = narratives.get(situation)

    if narrative is None:
        return None

    percentile = round(team_data["percentile"] * 100)

    return {
        "pillar": "rating",
        "headline": narrative["headline"],
        "description": narrative["description"].format(
            team=team_data["team"],
            record=team_data["record"],
            percentile=percentile,
        ),
        "score": narrative["score"],
    }


def get_team_storyline_candidates(
        team,
        opponent,
        team_record,
        opponent_record,
        context,
):
    """Collect storyline candidates from all four pillars."""

    candidates = []

    # 1. Record and standings
    record_candidates = evaluate_record_storylines(
        team_record,
        opponent_record,
        context,
    )
    candidates.extend(record_candidates)

    # 2. Team performance and statistical matchups
    performance_candidates = evaluate_performance_storylines(
        team,
        opponent,
    )
    candidates.extend(performance_candidates)

    # 3. Recent form and momentum
    momentum_candidates = evaluate_momentum_storylines(
        team,
        opponent,
    )
    candidates.extend(momentum_candidates)

    # 4. On-field rating compared with actual record
    rating_data = evaluate_on_field_rating(
        team,
        opponent,
    )

    if isinstance(rating_data, dict):
        rating_candidate = generate_on_field_narrative(
            rating_data
        )

        if rating_candidate is not None:
            candidates.append(rating_candidate)

    return candidates


def select_team_storyline(candidates):
    """Select the single strongest storyline for a team."""

    if not candidates:
        return None

    return max(
        candidates,
        key=lambda candidate: candidate.get("score", 0),
    )


def get_performance_level(percentile):
    """Classify a team's performance relative to the league."""

    if percentile is None:
        return None

    if percentile >= 0.80:
        return "ELITE"

    if percentile >= 0.65:
        return "ABOVE AVERAGE"

    if percentile <= 0.20:
        return "MAJOR WEAKNESS"

    if percentile <= 0.35:
        return "BELOW AVERAGE"

    return "AVERAGE"


PERFORMANCE_METRICS = {
    "offense": {
        "off_epa_per_play": {
            "label": "offensive efficiency",
        },
        "off_success_rate": {
            "label": "offensive consistency",
        },
        "pass_epa_per_play": {
            "label": "passing efficiency",
        },
        "rush_epa_per_play": {
            "label": "rushing efficiency",
        },
        "third_down_conversion_rate": {
            "label": "third-down offense",
        },
        "red_zone_td_rate": {
            "label": "red-zone offense",
        },
        "overall_explosive_rate": {
            "label": "explosive play production",
        },
    },
    "defense": {
        "def_epa_allowed_per_play": {
            "label": "defensive efficiency",
            "lower_is_better": True,
        },
        "def_success_rate_allowed": {
            "label": "defensive consistency",
            "lower_is_better": True,
        },
        "def_yards_allowed_per_play": {
            "label": "yards allowed per play",
            "lower_is_better": True,
        },
        "def_sack_rate": {
            "label": "pass rush",
        },
        "overall_explosive_rate_allowed": {
            "label": "explosive plays allowed",
            "lower_is_better": True,
        },
        "pass_epa_allowed_per_play": {
            "label": "pass defense",
            "lower_is_better": True,
        },
        "rush_epa_allowed_per_play": {
            "label": "run defense",
            "lower_is_better": True,
        },
    },
}


def evaluate_team_performance(team):
    """Identify a team's strongest and weakest statistical areas."""

    findings = []

    metrics = team.get("metrics", {})
    team_name = team["name"]

    for category, category_metrics in PERFORMANCE_METRICS.items():
        for metric, details in category_metrics.items():

            value = metrics.get(metric)

            if value is None or pd.isna(value):
                continue

            percentile = get_metric_percentile(
                metric,
                value,
                lower_is_better=details.get(
                    "lower_is_better", False
                ),
            )

            if percentile is None:
                continue

            level = get_performance_level(percentile)

            if level in ("ELITE", "MAJOR WEAKNESS"):
                findings.append({
                    "team": team_name,
                    "category": category,
                    "metric": metric,
                    "label": details["label"],
                    "value": float(value),
                    "percentile": percentile,
                    "level": level,
                })

    return findings


def evaluate_offensive_matchups(team, opponent):
    """Identify offensive strengths facing opposing defensive weaknesses."""

    candidates = []

    team_metrics_data = team.get("metrics", {})
    opponent_metrics_data = opponent.get("metrics", {})

    team_name = team["name"]
    opponent_name = opponent["name"]

    matchups = [
        {
            "offense_metric": "off_epa_per_play",
            "defense_metric": "def_epa_allowed_per_play",
            "label": "overall offense",
        },
        {
            "offense_metric": "pass_epa_per_play",
            "defense_metric": "pass_epa_allowed_per_play",
            "label": "passing game",
        },
        {
            "offense_metric": "rush_epa_per_play",
            "defense_metric": "rush_epa_allowed_per_play",
            "label": "rushing game",
        },
        {
            "offense_metric": "overall_explosive_rate",
            "defense_metric": "overall_explosive_rate_allowed",
            "label": "explosive play production",
        },
    ]

    for matchup in matchups:
        offense_value = team_metrics_data.get(
            matchup["offense_metric"]
        )

        defense_value = opponent_metrics_data.get(
            matchup["defense_metric"]
        )

        if (
                offense_value is None
                or defense_value is None
                or pd.isna(offense_value)
                or pd.isna(defense_value)
        ):
            continue

        offense_percentile = get_metric_percentile(
            matchup["offense_metric"],
            offense_value,
        )

        defense_percentile = get_metric_percentile(
            matchup["defense_metric"],
            defense_value,
            lower_is_better=True,
        )

        if offense_percentile is None or defense_percentile is None:
            continue

        # Look for a strong offense facing a weak defense.
        if offense_percentile >= 0.65 and defense_percentile <= 0.35:
            score = (
                    70
                    + round((offense_percentile - 0.65) * 30)
                    + round((0.35 - defense_percentile) * 30)
            )

            candidates.append({
                "pillar": "performance",
                "headline": (
                    f"{matchup['label'].upper()} "
                    "HAS A FAVORABLE MATCHUP"
                ),
                "description": (
                    f"{team_name} brings a strong "
                    f"{matchup['label']} into this matchup, "
                    f"while {opponent_name} has struggled "
                    f"in the corresponding defensive area. "
                    f"This could give {team_name} an important "
                    f"advantage."
                ),
                "matchup": matchup["label"],
                "offense_percentile": offense_percentile,
                "defense_percentile": defense_percentile,
                "score": score,
            })

    return candidates


def evaluate_defensive_matchups(team, opponent):
    """Identify defensive strengths facing opposing offensive weaknesses."""

    candidates = []

    team_metrics_data = team.get("metrics", {})
    opponent_metrics_data = opponent.get("metrics", {})

    team_name = team["name"]
    opponent_name = opponent["name"]

    matchups = [
        {
            "defense_metric": "def_epa_allowed_per_play",
            "offense_metric": "off_epa_per_play",
            "label": "overall defense",
        },
        {
            "defense_metric": "pass_epa_allowed_per_play",
            "offense_metric": "pass_epa_per_play",
            "label": "pass defense",
        },
        {
            "defense_metric": "rush_epa_allowed_per_play",
            "offense_metric": "rush_epa_per_play",
            "label": "run defense",
        },
        {
            "defense_metric": "overall_explosive_rate_allowed",
            "offense_metric": "overall_explosive_rate",
            "label": "explosive play prevention",
        },
    ]

    for matchup in matchups:
        defense_value = team_metrics_data.get(
            matchup["defense_metric"]
        )

        offense_value = opponent_metrics_data.get(
            matchup["offense_metric"]
        )

        if (
                defense_value is None
                or offense_value is None
                or pd.isna(defense_value)
                or pd.isna(offense_value)
        ):
            continue

        defense_percentile = get_metric_percentile(
            matchup["defense_metric"],
            defense_value,
            lower_is_better=True,
        )

        offense_percentile = get_metric_percentile(
            matchup["offense_metric"],
            offense_value,
        )

        if defense_percentile is None or offense_percentile is None:
            continue

        # Look for a strong defense facing a weak offense.
        if defense_percentile >= 0.65 and offense_percentile <= 0.35:
            score = (
                    70
                    + round((defense_percentile - 0.65) * 30)
                    + round((0.35 - offense_percentile) * 30)
            )

            candidates.append({
                "pillar": "performance",
                "headline": (
                    f"{matchup['label'].upper()} "
                    "HAS A FAVORABLE MATCHUP"
                ),
                "description": (
                    f"{team_name} brings a strong "
                    f"{matchup['label']} into this matchup, "
                    f"while {opponent_name} has struggled "
                    f"in the corresponding offensive area. "
                    f"This could give {team_name} an important "
                    f"advantage."
                ),
                "matchup": matchup["label"],
                "defense_percentile": defense_percentile,
                "offense_percentile": offense_percentile,
                "score": score,
            })

    return candidates


def evaluate_performance_storylines(team, opponent):
    """Combine individual performance findings and matchup advantages."""

    candidates = []

    # Individual team strengths and weaknesses
    team_findings = evaluate_team_performance(team)

    for finding in team_findings:
        if finding["level"] == "ELITE":
            headline = f"ELITE {finding['label'].upper()}"
            description = (
                f"{team['name']} has been one of the league's "
                f"strongest teams in {finding['label']}. "
                f"Entering this matchup, that strength could "
                f"play an important role against {opponent['name']}."
            )
            score = 65 + round(
                (finding["percentile"] - 0.80) * 50
            )

        else:
            headline = f"{finding['label'].upper()} NEEDS TO IMPROVE"
            description = (
                f"{team['name']} has struggled in "
                f"{finding['label']} this season. "
                f"That weakness could become important "
                f"against {opponent['name']}."
            )
            score = 65 + round(
                (0.20 - finding["percentile"]) * 50
            )

        candidates.append({
            "pillar": "performance",
            "headline": headline,
            "description": description,
            "score": score,
            "finding": finding,
        })

    # Offensive advantages
    candidates.extend(
        evaluate_offensive_matchups(team, opponent)
    )

    # Defensive advantages
    candidates.extend(
        evaluate_defensive_matchups(team, opponent)
    )

    return candidates


def evaluate_momentum_storylines(team, opponent):
    """Generate storyline candidates based on recent results and streaks."""

    candidates = []

    momentum = team.get("momentum", {})
    streak_type = momentum.get("streak_type")
    streak_length = momentum.get("streak_length", 0)

    team_name = team["name"]
    opponent_name = opponent["name"]

    # Winning streaks
    if streak_type == "W" and streak_length >= 2:

        if streak_length >= 3:
            headline = "KEEP THE WINNING STREAK ALIVE"
        else:
            headline = "LOOKING TO BUILD A WINNING RUN"

        score = min(85, 65 + (streak_length * 4))

        description = (
            f"{team_name} enters this matchup riding a "
            f"{streak_length}-game winning streak. "
            f"A victory over {opponent_name} would extend "
            f"that run and build even more momentum."
        )

        candidates.append({
            "pillar": "momentum",
            "headline": headline,
            "description": description,
            "score": score,
        })

    # Losing streaks
    elif streak_type == "L" and streak_length >= 2:

        if streak_length >= 3:
            headline = "LOSING STREAK MUST END"
        else:
            headline = "STOPPING THE SLIDE"

        score = min(85, 65 + (streak_length * 4))

        description = (
            f"{team_name} enters this matchup having lost "
            f"{streak_length} consecutive games. "
            f"A win against {opponent_name} would provide "
            f"a much-needed opportunity to stop the slide."
        )

        candidates.append({
            "pillar": "momentum",
            "headline": headline,
            "description": description,
            "score": score,
        })

    # Recent form over the last five games
    recent_form = momentum.get("recent_form", [])

    if len(recent_form) == 5 and streak_length < 2:
        wins = recent_form.count("W")
        losses = recent_form.count("L")

        last_result = momentum.get("last_result")

        # Strong recent form
        if wins >= 4:
            if last_result == "L":
                headline = "LOOKING TO BOUNCE BACK"
            else:
                headline = "KEEPING THE MOMENTUM GOING"

            candidates.append({
                "pillar": "momentum",
                "headline": headline,
                "description": (
                    f"{team_name} has won {wins} of its last "
                    f"five games. The team will look to carry "
                    f"that strong recent form into its matchup "
                    f"against {opponent_name}."
                ),
                "score": 75,
            })

        # Poor recent form
        elif losses >= 4:
            if last_result == "W":
                headline = "LOOKING TO BUILD ON A MUCH-NEEDED WIN"
            else:
                headline = "LOOKING TO BREAK OUT OF A SLUMP"

            candidates.append({
                "pillar": "momentum",
                "headline": headline,
                "description": (
                    f"{team_name} has lost {losses} of its last "
                    f"five games. The team needs to find a way "
                    f"to turn things around against "
                    f"{opponent_name}."
                ),
                "score": 75,
            })

    return candidates
