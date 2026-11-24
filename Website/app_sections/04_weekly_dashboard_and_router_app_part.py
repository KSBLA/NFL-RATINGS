

def render_weekly():
    # --------------------------------------------------------
    # PAGE HEADER + AUTOMATIC DATA STATUS
    # --------------------------------------------------------

    hero(
        "THE WEEKLY CONTROL CENTER",
        "GAME DAY",
        "HEADQUARTERS.",
        "LIVE NFL RESULTS. AUTOMATIC STANDINGS. COMPLETE SCHEDULE."
    )

    if NFL_DATA_STATUS["success"]:
        st.success(
            f'{NFL_DATA_STATUS["message"]} '
            f'Games: {NFL_DATA_STATUS["games"]} / '
            f'Completed: {NFL_DATA_STATUS["results"]}'
        )
    else:
        st.warning(NFL_DATA_STATUS["message"])

    if st.button("↻ REFRESH NFL DATA NOW", key="refresh_nfl_data"):
        load_espn_games.clear()
        sync_nfl_data()
        st.rerun()

    # --------------------------------------------------------
    # UPCOMING GAMES — WEEKLY MATCHUP SHOWCASE
    # --------------------------------------------------------

    section("UPCOMING GAMES")

    schedule = get_schedule()
    results = get_results()

    completed_ids = {
        str(game.get("schedule_id") or game.get("id"))
        for game in results
        if game.get("schedule_id") or game.get("id")
    }

    remaining_weeks = [
        int(game["week"])
        for game in schedule
        if game.get("week") is not None
           and str(game.get("id", "")) not in completed_ids
    ]

    current_week = min(remaining_weeks) if remaining_weeks else None

    upcoming_games = []

    if current_week is not None:

        now = datetime.now().astimezone().replace(tzinfo=None)

        for game in schedule:

            if int(game.get("week", 0)) != current_week:
                continue

            if str(game.get("id", "")) in completed_ids:
                continue

            # Exclude games that have already kicked off.
            try:
                kickoff_time = game.get("kickoff", "TBD")
                kickoff_clean = kickoff_time.rsplit(" ", 1)[0]

                game_datetime = datetime.strptime(
                    f'{game["date"]} {kickoff_clean}',
                    "%Y-%m-%d %I:%M %p"
                )

                if game_datetime <= now:
                    continue

            except (ValueError, TypeError, KeyError):
                pass

            upcoming_games.append(game)

    if upcoming_games:

        st.markdown(
            f'<div class="micro">WEEK {current_week} / '
            f'{len(upcoming_games)} UPCOMING MATCHUPS</div>',
            unsafe_allow_html=True
        )

        for game in upcoming_games:

            away = game["away"]
            home = game["home"]

            away_info = TEAMS[away]
            home_info = TEAMS[home]

            away_row = get_team_row(away)
            home_row = get_team_row(home)

            away_rank = (
                f'#{int(away_row["rank"])}'
                if away_row is not None else "—"
            )

            home_rank = (
                f'#{int(home_row["rank"])}'
                if home_row is not None else "—"
            )

            # Generate a basic matchup identity.
            if (
                    away_info.get("division")
                    and away_info.get("division") == home_info.get("division")
                    and away_info.get("conference") == home_info.get("conference")
            ):
                tagline = "DIVISION RIVALRY"

            elif away_row is not None and home_row is not None:

                if (
                        rankings is not None
                        and float(away_row["defensive_rating"]) >= rankings["defensive_rating"].nlargest(8).min()
                        and float(home_row["defensive_rating"]) >= rankings["defensive_rating"].nlargest(8).min()
                ):
                    tagline = "DEFENSIVE SHOWDOWN"

                elif (
                        rankings is not None
                        and float(away_row["offensive_rating"]) >= rankings["offensive_rating"].nlargest(8).min()
                        and float(home_row["offensive_rating"]) >= rankings["offensive_rating"].nlargest(8).min()
                ):
                    tagline = "POTENTIAL SHOOTOUT"

                else:
                    tagline = "WEEKLY MATCHUP"

            else:
                tagline = "WEEKLY MATCHUP"

            try:
                date_label = datetime.strptime(
                    game["date"], "%Y-%m-%d"
                ).strftime("%A, %B %d").replace(" 0", " ")
            except (ValueError, TypeError):
                date_label = game.get("date", "DATE TBD")

            kickoff_label = game.get("kickoff", "TIME TBD")

            away_name = html.escape(away_info["name"])
            home_name = html.escape(home_info["name"])

            away_color = away_info.get("color", "#333333")
            home_color = home_info.get("color", "#555555")

            game_id = str(game.get("id", f"{away}_{home}_{current_week}"))

            with st.container(key=f"upcoming_matchup_card_{game_id}"):

                st.html(f"""
                    <div class="upcoming-matchup"
                         style="--away-color:{away_color};
                                --home-color:{home_color};">

                        <div class="matchup-topline">
                            <span class="matchup-tagline">{tagline}</span>
                            <span class="matchup-week">WEEK {current_week}</span>
                        </div>

                        <div class="matchup-teams">

                            <div class="matchup-team">
                                <div class="matchup-rank">{away_rank}</div>
                                {logo(away, 76)}
                                <div class="matchup-team-name">{away_name}</div>
                                <div class="matchup-side">AWAY</div>
                            </div>

                            <div class="matchup-vs">VS</div>

                            <div class="matchup-team">
                                <div class="matchup-rank">{home_rank}</div>
                                {logo(home, 76)}
                                <div class="matchup-team-name">{home_name}</div>
                                <div class="matchup-side">HOME</div>
                            </div>

                        </div>

                        <div class="matchup-bottom">
                            <div>{date_label}</div>
                            <div>{kickoff_label}</div>
                        </div>

                    </div>
                """)

                if st.button(
                        "VIEW GAME PREVIEW  →",
                        key=f"preview_{game_id}",
                        use_container_width=True,
                        type="secondary",
                ):
                    st.session_state.selected_game_preview = game_id
                    st.rerun()

        st.html("""
            <style>
                .upcoming-matchup {
                    position: relative;
                    overflow: hidden;
                    padding: 22px;
                    margin-bottom: 18px;
                    border: 1px solid #b99a5a55;
                    border-radius: 13px;
                    background:
                        linear-gradient(
                            110deg,
                            color-mix(in srgb, var(--away-color) 23%, #101010),
                            #111111 50%,
                            color-mix(in srgb, var(--home-color) 23%, #101010)
                        );
                    box-shadow: 0 8px 25px #0007;
                }

                .matchup-topline,
                .matchup-bottom {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    gap: 10px;
                    color: #c6c0b2;
                    font-size: 11px;
                    letter-spacing: 1.5px;
                    font-weight: 800;
                }

                .matchup-tagline {
                    color: #d8b86d;
                }

                .matchup-teams {
                    display: grid;
                    grid-template-columns: 1fr auto 1fr;
                    align-items: center;
                    gap: 12px;
                    padding: 27px 0;
                }

                .matchup-team {
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    text-align: center;
                    min-width: 0;
                }

                .matchup-rank {
                    color: #d8b86d;
                    font-size: 21px;
                    font-weight: 900;
                    margin-bottom: 8px;
                }

                .matchup-team img {
                    max-width: 76px;
                    margin-bottom: 12px;
                }

                .matchup-team-name {
                    color: white;
                    font-size: 14px;
                    font-weight: 900;
                    letter-spacing: 1px;
                }

                .matchup-side {
                    color: #999;
                    font-size: 10px;
                    letter-spacing: 2px;
                    margin-top: 5px;
                }

                .matchup-vs {
                    color: #d8b86d;
                    font-size: 19px;
                    font-weight: 900;
                }

                .matchup-bottom {
                    border-top: 1px solid #ffffff20;
                    padding-top: 15px;
                    flex-wrap: wrap;
                }

                @media (max-width: 500px) {
                    .upcoming-matchup {
                        padding: 15px;
                    }

                    .matchup-team-name {
                        font-size: 11px;
                    }

                    .matchup-team img {
                        max-width: 58px;
                    }
                }
                            /* UPCOMING MATCHUP CARD BUTTON */

                div[class*="st-key-upcoming_matchup_card_"] {
                    gap: 0 !important;
                }

                div[class*="st-key-upcoming_matchup_card_"] button {
                    background: #111111;
                    color: #d8b86d;
                    border: 1px solid #b99a5a55;
                    border-radius: 0 0 13px 13px;
                    font-weight: 900;
                    letter-spacing: 2px;
                    min-height: 45px;
                }

                div[class*="st-key-upcoming_matchup_card_"] button:hover {
                    background: #292316;
                    color: white;
                    border-color: #d8b86d;
                }
            </style>
        """)

    # --------------------------------------------------------
    # GAME PREVIEW DIALOG
    # --------------------------------------------------------

    @st.dialog("GAME PREVIEW", width="large", dismissible=False)
    def render_game_preview(game):

        away = game["away"]
        home = game["home"]
        away_record = game.get("away_record", "N/A")
        home_record = game.get("home_record", "N/A")
        stadium = game.get("stadium", "Stadium TBD")

        # Game presentation
        try:
            game_date = datetime.strptime(
                game["date"], "%Y-%m-%d"
            ).date()
        except (ValueError, TypeError, KeyError):
            game_date = None

        broadcast = game.get("broadcast", "")
        st.write("BROADCAST:", broadcast)

        if game_date is not None:
            game_presentation = get_game_presentation(
                game_date,
                game.get("kickoff", ""),
            )

        else:
            game_presentation = {
                "theme": "standard",
                "holiday": None,
                "primetime": None,
            }
        theme_name = game_presentation["theme"]

        theme = GAME_THEMES.get(
            theme_name,
            GAME_THEMES["standard"],
        )

        away_info = TEAMS[away]
        home_info = TEAMS[home]

        away_row = get_team_row(away)
        home_row = get_team_row(home)
        away_stats = get_team_row(away, team_metrics)
        home_stats = get_team_row(home, team_metrics)
        standings = get_standings()
        playoff_picture = get_playoff_picture()

        away_division = get_standings(
            conference=away_info["conf"],
            division=away_info["div"],
        )

        home_division = get_standings(
            conference=home_info["conf"],
            division=home_info["div"],
        )

        away_division_position = (
                away_division.index[
                    away_division["Code"] == away
                    ].tolist()[0] + 1
        )

        home_division_position = (
                home_division.index[
                    home_division["Code"] == home
                    ].tolist()[0] + 1
        )

        is_division_game = (
                away_info["conf"] == home_info["conf"]
                and away_info["div"] == home_info["div"]
        )

        is_conference_game = (
                away_info["conf"] == home_info["conf"]
        )

        division_ordinals = ["1st", "2nd", "3rd", "4th"]

        away_division_label = division_ordinals[
            away_division_position - 1
            ]

        home_division_label = division_ordinals[
            home_division_position - 1
            ]

        away_standing = standings[
            standings["Code"] == away
            ].iloc[0]

        home_standing = standings[
            standings["Code"] == home
            ].iloc[0]

        away_standing_record = (
            f'{int(away_standing["W"])}-'
            f'{int(away_standing["L"])}-'
            f'{int(away_standing["T"])}'
        )

        home_standing_record = (
            f'{int(home_standing["W"])}-'
            f'{int(home_standing["L"])}-'
            f'{int(home_standing["T"])}'
        )

        away_playoff_status = "OUTSIDE PLAYOFF PICTURE"
        home_playoff_status = "OUTSIDE PLAYOFF PICTURE"

        for conference, picture in playoff_picture.items():
            for _, team in picture["playoff_teams"].iterrows():
                if team["Code"] == away:
                    away_playoff_status = f'SEED #{int(team["Seed"])}'
                if team["Code"] == home:
                    home_playoff_status = f'SEED #{int(team["Seed"])}'

            for _, team in picture["in_the_hunt"].iterrows():
                if team["Code"] == away:
                    away_playoff_status = "IN THE HUNT"
                if team["Code"] == home:
                    home_playoff_status = "IN THE HUNT"

        # Gather data for all four individual storyline pillars
        away_storyline_data = get_storyline_team_data(away)
        home_storyline_data = get_storyline_team_data(home)

        away_storyline_data["name"] = away_info["name"]
        home_storyline_data["name"] = home_info["name"]

        away_storyline_team = {
            "name": away_info["name"],
            "wins": int(away_standing["W"]),
            "losses": int(away_standing["L"]),
            "ties": int(away_standing["T"]),
            "win_percentage": float(away_standing["PCT"]),
            "playoff_status": away_playoff_status,
            "division_position": away_division_position,
            "ratings": away_storyline_data["ratings"],
            "momentum": away_storyline_data["momentum"],
        }

        home_storyline_team = {
            "name": home_info["name"],
            "wins": int(home_standing["W"]),
            "losses": int(home_standing["L"]),
            "ties": int(home_standing["T"]),
            "win_percentage": float(home_standing["PCT"]),
            "playoff_status": home_playoff_status,
            "division_position": home_division_position,
            "ratings": home_storyline_data["ratings"],
            "momentum": home_storyline_data["momentum"],
        }

        away_storyline = get_team_storyline_candidates(
            away_storyline_data,
            home_storyline_data,
            away_storyline_team,
            home_storyline_team,
            {"is_division_game": is_division_game},
        )

        home_storyline = get_team_storyline_candidates(
            home_storyline_data,
            away_storyline_data,
            home_storyline_team,
            away_storyline_team,
            {"is_division_game": is_division_game},
        )

        away_selected_storyline = select_team_storyline(
            away_storyline
        )

        home_selected_storyline = select_team_storyline(
            home_storyline
        )

        matchup_storyline = evaluate_matchup_storyline(
            away_storyline_team,
            home_storyline_team,
            is_division_game,
            is_conference_game,
        )

        storyline_title = matchup_storyline["headline"]
        storyline_context = matchup_storyline["description"]

        away_conference_standings = standings[
            standings["Conference"] == away_info["conf"]
            ].reset_index(drop=True)

        home_conference_standings = standings[
            standings["Conference"] == home_info["conf"]
            ].reset_index(drop=True)

        away_conference_position = (
                away_conference_standings.index[
                    away_conference_standings["Code"] == away
                    ].tolist()[0] + 1
        )

        home_conference_position = (
                home_conference_standings.index[
                    home_conference_standings["Code"] == home
                    ].tolist()[0] + 1
        )

        away_advantages, away_concerns = ([], [])
        home_advantages, home_concerns = ([], [])
        away_battles = []
        home_battles = []

        if away_stats is not None and home_stats is not None:
            away_advantages, away_concerns = build_matchup_analysis(
                away_stats, home_stats
            )

            home_advantages, home_concerns = build_matchup_analysis(
                home_stats, away_stats
            )

            away_battles = build_key_statistical_battles(
                away_stats, home_stats
            )

            home_battles = build_key_statistical_battles(
                home_stats, away_stats
            )

        away_probability = None
        home_probability = None
        underdog_advantages = []

        if away_row is not None and home_row is not None:
            home_probability = calculate_win_probability(
                float(home_row["overall_rating"]),
                float(away_row["overall_rating"]),
                True,
            )

            away_probability = 1 - home_probability

            if away_probability < home_probability:
                underdog_advantages = away_advantages
            else:
                underdog_advantages = home_advantages

            upset_alert = (
                    away_probability is not None
                    and home_probability is not None
                    and min(away_probability, home_probability) >= 0.30
                    and len(underdog_advantages) >= 2
                    and max(
                (
                    advantage["strength"]
                    for advantage in underdog_advantages
                ),
                default=0,
            ) >= 0.15
            )

        else:
            upset_alert = False

        away_rank = (
            f'#{int(away_row["rank"])}'
            if away_row is not None else "—"
        )

        home_rank = (
            f'#{int(home_row["rank"])}'
            if home_row is not None else "—"
        )

        try:
            date_label = datetime.strptime(
                game["date"], "%Y-%m-%d"
            ).strftime("%A, %B %d, %Y")
        except (ValueError, TypeError, KeyError):
            date_label = game.get("date", "DATE TBD")

        kickoff_label = game.get("kickoff", "TIME TBD")

        if theme_name == "halloween":
            render_halloween_hero(
                away=html.escape(away_info["name"]),
                home=html.escape(home_info["name"]),
                away_record=html.escape(away_record),
                home_record=html.escape(home_record),
                stadium=html.escape(stadium),
                away_rank=away_rank,
                home_rank=home_rank,
                week=game.get("week", "N/A"),
                date_label=html.escape(date_label),
                kickoff_label=html.escape(kickoff_label),
                away_logo=html.escape(away_info["logo"], quote=True),
                home_logo=html.escape(home_info["logo"], quote=True),
            )
        elif theme_name in {"thanksgiving", "christmas_eve", "christmas_day", "tnf", "snf", "mnf"}:
            render_themed_hero(
                theme_name=theme_name,
                away=html.escape(away_info["name"]),
                home=html.escape(home_info["name"]),
                away_record=html.escape(away_record),
                home_record=html.escape(home_record),
                stadium=html.escape(stadium),
                away_rank=away_rank,
                home_rank=home_rank,
                week=game.get("week", "N/A"),
                date_label=html.escape(date_label),
                kickoff_label=html.escape(kickoff_label),
                away_logo=html.escape(away_info["logo"], quote=True),
                home_logo=html.escape(home_info["logo"], quote=True),
                theme=theme,
            )
        else:

            st.html(f"""
                <div style="
                    padding: 25px;
                    border: 1px solid {theme['accent']}88;
                    border-radius: 15px;
                    position: relative;
                    overflow: hidden;
                    box-shadow: 0 0 25px {theme['accent']}22;
                    background: linear-gradient(
                        110deg,
                        {away_info.get('color', '#333333')}44,
                        {theme['background']} 50%,
                        {home_info.get('color', '#333333')}44
                    );
                    text-align: center;
                ">
                    <div style="
                        color: {theme['accent']};
                        grid-column: 1 / -1;
                        font-size: 12px;
                        font-weight: 900;
                        letter-spacing: 3px;
                    ">
                        WEEK {game.get("week", "N/A")}
                        {f'<div style="color: {theme["secondary"]}; font-size: 11px; font-weight: 900; letter-spacing: 2px; margin-top: 8px;">{html.escape(theme["label"])}</div>' if theme["label"] else ""}
                    </div>

                    <div style="
                        display: grid;
                        grid-template-columns: 1fr auto 1fr;
                        align-items: center;
                        gap: 25px;
                        padding: 25px 0;
                    ">
                        <div>
                            <div style="
                                color: {theme['accent']};
                                font-size: 11px;
                                font-weight: 900;
                                letter-spacing: 2px;
                                margin-bottom: 8px;
                            ">
                                AWAY
                            </div>

                            {logo(away, 105)}

                            <div style="
                                color: white;
                                font-size: 18px;
                                font-weight: 900;
                                margin-top: 12px;
                            ">
                                {html.escape(away_info["name"])}
                            </div>

                            <div style="
                                color: #d0c9b9;
                                font-size: 13px;
                                font-weight: 700;
                                margin-top: 5px;
                            ">
                                {html.escape(away_record)}
                            </div>

                            <div style="
                                color: {theme['accent']};
                                font-size: 22px;
                                font-weight: 900;
                            ">
                                {away_rank}
                            </div>
                        </div>

                        <div style="
                            color: {theme['accent']};
                            font-size: 24px;
                            font-weight: 900;
                        ">
                            VS
                        </div>

                        <div>
                            <div style="
                                color: {theme['accent']};
                                font-size: 11px;
                                font-weight: 900;
                                letter-spacing: 2px;
                                margin-bottom: 8px;
                            ">
                                HOME
                            </div>

                            {logo(home, 105)}

                            <div style="
                                color: white;
                                font-size: 18px;
                                font-weight: 900;
                                margin-top: 12px;
                            ">
                                {html.escape(home_info["name"])}
                            </div>

                            <div style="
                                color: #d0c9b9;
                                font-size: 13px;
                                font-weight: 700;
                                margin-top: 5px;
                            ">
                                {html.escape(home_record)}
                            </div>

                            <div style="
                                color: {theme['accent']};
                                font-size: 22px;
                                font-weight: 900;
                            ">
                                {home_rank}
                            </div>
                        </div>

                        <div style="
                            color: {theme['accent']};
                            grid-column: 1 / -1;
                            font-size: 14px;
                            font-weight: 900;
                            letter-spacing: 1px;
                            margin-top: 12px;
                            text-align: center;
                        ">
                            {html.escape(stadium)}
                        </div>

                        <div style="
                            color: #d0c9b9;
                            font-size: 12px;
                            grid-column: 1 / -1;
                            font-weight: 700;
                            letter-spacing: 0.5px;
                            margin-top: 6px;
                            text-align: center;
                        ">
                            {date_label} &nbsp; | &nbsp; {kickoff_label}
                        </div>
                    </div>
                </div>
            """)

        st.markdown("### Confidence Meter")

        if away_probability is not None and home_probability is not None:
            away_percentage = away_probability * 100
            home_percentage = home_probability * 100

            favorite = (
                away_info["name"]
                if away_probability >= 0.50
                else home_info["name"]
            )

            underdog = (
                home_info["name"]
                if away_probability >= 0.50
                else away_info["name"]
            )

            st.html(f"""
                <div style="
                    background: #171717;
                    border: 1px solid #b99a5a66;
                    border-radius: 14px;
                    padding: 22px;
                    margin: 10px 0 25px 0;
                ">
                    <div style="
                        display: flex;
                        justify-content: space-between;
                        align-items: center;
                        gap: 15px;
                        margin-bottom: 15px;
                    ">
                        <div style="text-align: left;">
                            <div style="
                                color: #d8b86d;
                                font-size: 11px;
                                font-weight: 900;
                                letter-spacing: 1px;
                            ">AWAY</div>
                            <div style="
                                color: white;
                                font-size: 25px;
                                font-weight: 900;
                            ">{away_percentage:.1f}%</div>
                            <div style="
                                color: #bdb6a7;
                                font-size: 12px;
                            ">{html.escape(away_info["name"])}</div>
                        </div>

                        <div style="text-align: right;">
                            <div style="
                                color: #d8b86d;
                                font-size: 11px;
                                font-weight: 900;
                                letter-spacing: 1px;
                            ">HOME</div>
                            <div style="
                                color: white;
                                font-size: 25px;
                                font-weight: 900;
                            ">{home_percentage:.1f}%</div>
                            <div style="
                                color: #bdb6a7;
                                font-size: 12px;
                            ">{html.escape(home_info["name"])}</div>
                        </div>
                    </div>

                    <div style="
                        display: flex;
                        width: 100%;
                        height: 17px;
                        overflow: hidden;
                        border-radius: 20px;
                        background: #333;
                    ">
                        <div style="
                            width: {away_percentage:.2f}%;
                            background: {away_info.get('color', '#777777')};
                        "></div>
                        <div style="
                            width: {home_percentage:.2f}%;
                            background: {home_info.get('color', '#777777')};
                        "></div>
                    </div>

                    <div style="
                        display: flex;
                        justify-content: space-between;
                        margin-top: 14px;
                        color: #d8b86d;
                        font-size: 11px;
                        font-weight: 900;
                        letter-spacing: 1px;
                    ">
                        <span>MODEL FAVORITE: {html.escape(favorite.upper())}</span>
                        <span>UNDERDOG: {html.escape(underdog.upper())}</span>
                    </div>
                </div>
            """)

        if upset_alert:
            st.html(f"""
                <div style="
                    background: linear-gradient(110deg, #3b2410, #171717);
                    border: 1px solid #d8a34a;
                    border-left: 5px solid #e0a33e;
                    border-radius: 10px;
                    padding: 17px 20px;
                    margin: 0 0 25px 0;
                ">
                    <div style="
                        color: #f0b653;
                        font-size: 13px;
                        font-weight: 900;
                        letter-spacing: 2px;
                        margin-bottom: 7px;
                    ">
                        ⚠ UPSET ALERT
                    </div>
                    <div style="
                        color: white;
                        font-size: 16px;
                        font-weight: 800;
                        margin-bottom: 6px;
                    ">
                        {html.escape(underdog)} HAS A REALISTIC PATH TO AN UPSET
                    </div>
                    <div style="
                        color: #d0c9b9;
                        font-size: 13px;
                        line-height: 1.5;
                    ">
                        Despite being the underdog, this team has
                        {len(underdog_advantages)} meaningful statistical
                        matchup advantages that could help them pull off
                        the upset.
                    </div>
                </div>
            """)

        st.markdown("### Matchup Intelligence")

        def matchup_items_html(items, color, label):
            if not items:
                return (
                    '<div style="color:#999;font-size:12px;'
                    'padding:8px 0;">No significant findings</div>'
                )

            rows = ""

            for item in items[:3]:
                side_symbol = "Ⓞ" if item["side"] == "OFFENSE" else "Ⓧ"

                rows += f"""
                    <div style="
                        display:flex;
                        justify-content:space-between;
                        align-items:center;
                        gap:10px;
                        padding:10px 0;
                        border-bottom:1px solid #ffffff12;
                    ">
                        <div style="
                            color:#f2f0e9;
                            font-size:13px;
                            font-weight:700;
                        ">
                            {html.escape(item['category'])}
                        </div>
                        <span style="
                            background:{color}18;
                            color:{color};
                            border:1px solid {color}55;
                            border-radius:20px;
                            padding:4px 8px;
                            font-size:12px;
                            font-weight:900;
                            letter-spacing:0.7px;
                            white-space:nowrap;
                        ">
                            {side_symbol} {html.escape(item['side'])}
                        </span>
                    </div>
                """

            return rows

        away_advantage_html = matchup_items_html(
            away_advantages, "#65c98b", "ADVANTAGES"
        )
        away_concern_html = matchup_items_html(
            away_concerns, "#e47777", "CONCERNS"
        )
        home_advantage_html = matchup_items_html(
            home_advantages, "#65c98b", "ADVANTAGES"
        )
        home_concern_html = matchup_items_html(
            home_concerns, "#e47777", "CONCERNS"
        )

        st.html(f"""
            <div style="
                display:grid;
                grid-template-columns:repeat(2,minmax(0,1fr));
                gap:16px;
                margin:10px 0 28px 0;
            ">
                <div style="
                    background:linear-gradient(145deg,#202020,#151515);
                    border:1px solid #b99a5a66;
                    border-radius:14px;
                    padding:18px;
                    min-width:0;
                ">
                    <div style="
                        color:#d8b86d;
                        font-size:15px;
                        font-weight:900;
                        letter-spacing:1.5px;
                        margin-bottom:5px;
                    ">AWAY TEAM</div>

                    <div style="
                        color:white;
                        font-size:18px;
                        font-weight:900;
                        margin-bottom:18px;
                    ">{html.escape(away_info['name'])}</div>

                    <div style="
                        color:#65c98b;
                        font-size:14px;
                        font-weight:900;
                        letter-spacing:1px;
                        margin-bottom:5px;
                    ">▲ MATCHUP ADVANTAGES</div>

                    {away_advantage_html}

                    <div style="
                        color:#e47777;
                        font-size:14px;
                        font-weight:900;
                        letter-spacing:1px;
                        margin-top:20px;
                        margin-bottom:5px;
                    ">▼ AREAS OF CONCERN</div>

                    {away_concern_html}
                </div>

                <div style="
                    background:linear-gradient(145deg,#202020,#151515);
                    border:1px solid #b99a5a66;
                    border-radius:14px;
                    padding:18px;
                    min-width:0;
                ">
                    <div style="
                        color:#d8b86d;
                        font-size:15px;
                        font-weight:900;
                        letter-spacing:1.5px;
                        margin-bottom:5px;
                    ">HOME TEAM</div>

                    <div style="
                        color:white;
                        font-size:18px;
                        font-weight:900;
                        margin-bottom:18px;
                    ">{html.escape(home_info['name'])}</div>

                    <div style="
                        color:#65c98b;
                        font-size:14px;
                        font-weight:900;
                        letter-spacing:1px;
                        margin-bottom:5px;
                    ">▲ MATCHUP ADVANTAGES</div>

                    {home_advantage_html}

                    <div style="
                        color:#e47777;
                        font-size:14px;
                        font-weight:900;
                        letter-spacing:1px;
                        margin-top:20px;
                        margin-bottom:5px;
                    ">▼ AREAS OF CONCERN</div>

                    {home_concern_html}
                </div>
            </div>
        """)

        away_key = build_game_preview_key(
            away_advantages,
            away_concerns,
        )

        home_key = build_game_preview_key(
            home_advantages,
            home_concerns,
        )

        st.markdown("### Key to Victory")

        def key_card_html(team_name, key, color):
            stat_line = key["stat_line"] or ""

            return f"""
                <div style="
                    background:linear-gradient(145deg,#202020,#151515);
                    border:1px solid {color}66;
                    border-radius:14px;
                    padding:20px;
                    height:100%;
                ">
                    <div style="
                        color:{color};
                        font-size:10px;
                        font-weight:900;
                        letter-spacing:1.5px;
                        margin-bottom:7px;
                    ">KEY TO VICTORY</div>

                    <div style="
                        color:white;
                        font-size:18px;
                        font-weight:900;
                        margin-bottom:12px;
                    ">{html.escape(team_name)}</div>

                    <div style="
                        color:{color};
                        font-size:17px;
                        font-weight:900;
                        margin-bottom:10px;
                    ">{html.escape(key["title"])}</div>

                    <div style="
                        color:#aaa;
                        font-size:10px;
                        font-weight:800;
                        letter-spacing:1px;
                        margin-bottom:12px;
                    ">{html.escape(key["category"])} · {html.escape(key["side"])}</div>

                    <div style="
                        color:#e5e5e5;
                        font-size:13px;
                        line-height:1.6;
                    ">{html.escape(key["explanation"])}</div>

                    {f'''
                    <div style="
                        border-top:1px solid #ffffff20;
                        margin-top:16px;
                        padding-top:12px;
                        color:#d8b86d;
                        font-size:11px;
                        font-weight:700;
                        line-height:1.5;
                    ">{html.escape(stat_line)}</div>
                    ''' if stat_line else ""}
                </div>
            """

        away_key_html = key_card_html(
            away_info["name"], away_key, "#65a9e8"
        )

        home_key_html = key_card_html(
            home_info["name"], home_key, "#e47777"
        )

        st.html(f"""
            <div style="
                display:grid;
                grid-template-columns:repeat(2,minmax(0,1fr));
                gap:16px;
                margin:10px 0 28px 0;
            ">
                {away_key_html}
                {home_key_html}
            </div>
        """)

        st.markdown("### Key Stituational Battles")

        def format_battle_value(category, value):
            if category in ("Pass Protection", "Fourth Down"):
                return f"{value:.1%}"

            return f"{value:.2f}"

        def battle_card_html(team_name, battles, color):
            battle_rows = ""

            for battle in battles:
                team_value = format_battle_value(
                    battle["category"], battle["team_value"]
                )

                thresholds = {
                    "Turnover Battle": 0.15,
                    "Pass Protection": 0.01,
                    "Fourth Down": 0.03,
                    "Penalty Discipline": 5.0,
                }

                edge = battle["edge"]
                threshold = thresholds[battle["category"]]

                if edge > threshold:
                    team_value_color = "#35c979"
                elif edge < -threshold:
                    team_value_color = "#ef6262"
                else:
                    team_value_color = "#b0b0b0"

                battle_rows += f"""
                    <div style="
                        border-top:1px solid #ffffff20;
                        padding:14px 0;
                    ">
                        <div style="
                            color:#e0e0e0;
                            font-size:14px;
                            font-weight:900;
                            margin-bottom:8px;
                        ">{html.escape(battle["category"])}</div>

                        <div style="
                            display:flex;
                            justify-content:space-between;
                            gap:12px;
                            color:{team_value_color};
                            font-size:12px;
                            margin-bottom:8px;
                        ">
                            <span>{html.escape(battle["team_label"])}</span>
                            <strong>{team_value}</strong>
                        </div>

                        <div style="
                            color:#aaa;
                            font-size:11px;
                            line-height:1.5;
                        ">{html.escape(battle["description"])}</div>
                    </div>
                """

            if not battle_rows:
                battle_rows = """
                    <div style="color:#aaa;font-size:12px;">
                        Not enough statistical data available.
                    </div>
                """

            return f"""
                <div style="
                    background:linear-gradient(145deg,#202020,#151515);
                    border:1px solid #444444;
                    border-radius:14px;
                    padding:20px;
                    height:100%;
                ">
                    <div style="
                        color:white;
                        font-size:17px;
                        font-weight:900;
                        margin-bottom:14px;
                    ">{html.escape(team_name)}</div>

                    {battle_rows}
                </div>
            """

        away_battle_html = battle_card_html(
            away_info["name"], away_battles, "#65a9e8"
        )

        home_battle_html = battle_card_html(
            home_info["name"], home_battles, "#e47777"
        )

        st.html(f"""
            <div style="
                display:grid;
                grid-template-columns:repeat(2,minmax(0,1fr));
                gap:16px;
                margin:10px 0 28px 0;
            ">
                {away_battle_html}
                {home_battle_html}
            </div>
        """)

        st.markdown("### Game Storyline & Implications")

        # Unified Storylines Section
        with st.container(border=True):

            st.markdown(
                '<div style="color:#d8b86d;font-size:13px;'
                'font-weight:900;letter-spacing:4px;margin-bottom:15px;">'
                '✦ THE STORYLINES ✦'
                '</div>',
                unsafe_allow_html=True
            )

            st.html(f"""
                <div style="
                    background:linear-gradient(135deg,#30291f,#191816);
                    border:1px solid #b99a5a66;
                    border-radius:15px;
                    padding:24px;
                    margin-bottom:20px;
                ">
                    <div style="
                        color:#d8b86d;
                        font-size:11px;
                        font-weight:900;
                        letter-spacing:3px;
                        margin-bottom:12px;
                    ">
                        THE STORY OF THIS MATCHUP
                    </div>

                    <div style="
                        color:#fff4dc;
                        font-size:27px;
                        font-weight:900;
                        margin-bottom:12px;
                    ">
                        {html.escape(storyline_title)}
                    </div>

                    <div style="
                        color:#d5cbbb;
                        font-size:14px;
                        line-height:1.8;
                    ">
                        {html.escape(storyline_context)}
                    </div>
                </div>
            """)

            st.markdown(
                '<div style="color:#d8b86d;font-size:11px;'
                'font-weight:900;letter-spacing:3px;margin:20px 0 12px;">'
                'THE TEAMS'
                '</div>',
                unsafe_allow_html=True
            )

            team_columns = st.columns(2)

            team_display = [
                {
                    "column": team_columns[0],
                    "info": away_info,
                    "record": away_standing_record,
                    "division": away_division_label,
                    "conference": away_conference_position,
                    "status": away_playoff_status,
                    "storyline": away_selected_storyline,
                },
                {
                    "column": team_columns[1],
                    "info": home_info,
                    "record": home_standing_record,
                    "division": home_division_label,
                    "conference": home_conference_position,
                    "status": home_playoff_status,
                    "storyline": home_selected_storyline,
                },
            ]

            for team in team_display:

                with team["column"]:

                    st.image(
                        team["info"]["logo"],
                        width=85,
                    )

                    storyline = team["storyline"]

                    if storyline is not None:
                        headline = html.escape(storyline["headline"])
                        description = html.escape(storyline["description"])
                    else:
                        headline = "NO INDIVIDUAL STORYLINE"
                        description = (
                            "This team has no standout individual storyline "
                            "for this matchup."
                        )

                    st.html(f"""
                        <div style="
                            background:linear-gradient(145deg,#292720,#1d1c19);
                            border:1px solid #b99a5a55;
                            border-radius:13px;
                            padding:18px;
                            margin-bottom:15px;
                        ">
                            <div style="
                                color:#d8b86d;
                                font-size:12px;
                                font-weight:900;
                                letter-spacing:2px;
                                margin-bottom:10px;
                            ">
                                {html.escape(team["info"]["name"].upper())}
                            </div>

                            <div style="
                                color:#fff4dc;
                                font-size:23px;
                                font-weight:900;
                                margin-bottom:10px;
                            ">
                                {team["record"]}
                            </div>

                            <div style="
                                color:#c9c1b3;
                                font-size:12px;
                                line-height:1.8;
                                margin-bottom:18px;
                            ">
                                {team["division"]} in Division<br>
                                {team["conference"]} in Conference<br>
                                {html.escape(team["status"])}
                            </div>

                            <div style="
                                border-top:1px solid #b99a5a55;
                                padding-top:15px;
                            ">
                                <div style="
                                    color:#d8b86d;
                                    font-size:10px;
                                    font-weight:900;
                                    letter-spacing:2px;
                                    margin-bottom:8px;
                                ">
                                    TEAM STORYLINE
                                </div>

                                <div style="
                                    color:white;
                                    font-size:17px;
                                    font-weight:900;
                                    margin-bottom:9px;
                                ">
                                    {headline}
                                </div>

                                <div style="
                                    color:#d0c9bd;
                                    font-size:13px;
                                    line-height:1.7;
                                ">
                                    {description}
                                </div>
                            </div>
                        </div>
                    """)

        if st.button("CLOSE PREVIEW", use_container_width=True):
            st.session_state.selected_game_preview = None
            st.rerun()

    selected_game_id = st.session_state.selected_game_preview

    selected_game = next(
        (
            game for game in upcoming_games
            if str(game.get("id")) == str(selected_game_id)
        ),
        None
    )

    if selected_game is not None:
        render_game_preview(selected_game)

    else:
        st.info("No upcoming games found for the current NFL week.")

    # --------------------------------------------------------
    # DIVISION RACE
    # --------------------------------------------------------

    section("DIVISION RACE")

    def render_division_card(conference, division):

        division_data = get_standings(
            conference=conference,
            division=division,
        )

        rows_html = ""

        for position, (_, team) in enumerate(division_data.iterrows()):
            code = team["Code"]
            name = html.escape(str(team["Team"]))
            record = (
                f'{int(team["W"])}-'
                f'{int(team["L"])}-'
                f'{int(team["T"])}'
            )
            pct = f'{float(team["PCT"]):.3f}'

            is_leader = position == 0

            row_background = (
                "linear-gradient(90deg,#B99A5A22,#B99A5A08)"
                if is_leader else "#FFFFFF05"
            )

            border_color = (
                "#B99A5A" if is_leader else "#35332D"
            )

            leader_label = (
                '<div style="font-size:9px;color:#D8B86D;'
                'font-weight:800;letter-spacing:1px;">'
                'DIVISION LEADER</div>'
                if is_leader else ""
            )

            rows_html += f"""
                <div style="
                    display:flex;
                    align-items:center;
                    gap:11px;
                    padding:10px 9px;
                    margin-top:7px;
                    border-radius:9px;
                    background:{row_background};
                    border-left:3px solid {border_color};
                ">
                    <div style="
                        width:22px;
                        color:#B99A5A;
                        font-size:12px;
                        font-weight:800;
                        text-align:center;
                    ">
                        {position + 1}
                    </div>

                    <div style="
                        width:64px;
                        height:64px;
                        display:flex;
                        align-items:center;
                        justify-content:center;
                        flex-shrink:0;
                    ">
                        {logo(code, width=60)}
                    </div>

                    <div style="flex:1;min-width:0;">
                        <div style="
                            color:#F4F0E7;
                            font-size:19px;
                            font-weight:900;
                            letter-spacing:1px;
                        ">
                            {code}
                        </div>
                        <div style="
                            color:#AAA69C;
                            font-size:15px;
                        ">
                            {name}
                        </div>
                        {leader_label}
                    </div>

                    <div style="text-align:right;">
                        <div style="
                            color:#F4F0E7;
                            font-size:20px;
                            font-weight:900;
                            font-variant-numeric:tabular-nums;
                        ">
                            {record}
                        </div>
                        <div style="
                            color:#B99A5A;
                            font-size:14px;
                            font-weight:700;
                        ">
                            {pct}
                        </div>
                    </div>
                </div>
            """

        st.html(f"""
            <div style="
                background:linear-gradient(145deg,#201F1B,#111110);
                border:1px solid #39362E;
                border-radius:14px;
                padding:15px;
                margin-bottom:14px;
                box-shadow:0 8px 22px #0005;
            ">
                <div style="
                    display:flex;
                    justify-content:space-between;
                    align-items:center;
                    padding-bottom:10px;
                    border-bottom:1px solid #39362E;
                ">
                    <div style="
                        color:#D8B86D;
                        font-size:20px;
                        font-weight:900;
                        letter-spacing:2px;
                    ">
                        {conference} {division.upper()}
                    </div>
                    <div style="
                        color:#77736A;
                        font-size:10px;
                        letter-spacing:1px;
                    ">
                        DIVISION
                    </div>
                </div>

                {rows_html}
            </div>
        """)

    def render_conference_header(abbreviation, full_name):

        st.html(f"""
            <div style="
                text-align:center;
                padding:24px 10px 18px;
                margin-top:12px;
            ">
                <div style="
                    color:#B99A5A;
                    font-size:11px;
                    font-weight:800;
                    letter-spacing:5px;
                    margin-bottom:5px;
                ">
                    {full_name}
                </div>

                <div style="
                    color:#F4F0E7;
                    font-size:36px;
                    font-weight:1000;
                    letter-spacing:7px;
                    text-shadow:0 0 22px #B99A5A55;
                ">
                    {abbreviation}
                </div>

                <div style="
                    width:100px;
                    height:2px;
                    margin:12px auto 0;
                    background:linear-gradient(
                        90deg,transparent,#B99A5A,transparent
                    );
                "></div>
            </div>
        """)

    # AFC

    render_conference_header(
        "AFC",
        "AMERICAN FOOTBALL CONFERENCE",
    )

    afc_left, afc_right = st.columns(2)

    with afc_left:
        render_division_card("AFC", "North")
        render_division_card("AFC", "South")

    with afc_right:
        render_division_card("AFC", "East")
        render_division_card("AFC", "West")

    # NFC

    render_conference_header(
        "NFC",
        "NATIONAL FOOTBALL CONFERENCE",
    )

    nfc_left, nfc_right = st.columns(2)

    with nfc_left:
        render_division_card("NFC", "North")
        render_division_card("NFC", "South")

    with nfc_right:
        render_division_card("NFC", "East")
        render_division_card("NFC", "West")

    # --------------------------------------------------------
    # PLAYOFF PICTURE
    # --------------------------------------------------------

    section("PLAYOFF PICTURE")

    playoff_picture = get_playoff_picture()

    def render_playoff_conference(conference):

        data = playoff_picture[conference]
        playoff_teams = data["playoff_teams"]
        in_the_hunt = data["in_the_hunt"]

        rows_html = ""

        for _, team in playoff_teams.iterrows():

            code = team["Code"]
            name = team["Team"]
            seed = int(team["Seed"])
            record = f'{team["W"]}-{team["L"]}'

            if team["T"] > 0:
                record += f'-{team["T"]}'

            team_type = team["Type"]

            if team_type == "DIVISION WINNER":
                label = "DIVISION WINNER"
                label_color = "#D8B86D"
            else:
                label = "WILD CARD"
                label_color = "#8CADD1"

            rows_html += f"""
                <div style="
                    display:flex;
                    align-items:center;
                    gap:12px;
                    padding:11px 10px;
                    border-bottom:1px solid #39362E;
                ">
                    <div style="
                        color:#D8B86D;
                        font-size:19px;
                        font-weight:900;
                        width:25px;
                        text-align:center;
                    ">
                        {seed}
                    </div>

                    {logo(code, width=42)}

                    <div style="flex:1;min-width:0;">
                        <div style="
                            color:#F4F0E7;
                            font-size:15px;
                            font-weight:800;
                        ">
                            {name}
                        </div>
                        <div style="
                            color:{label_color};
                            font-size:9px;
                            font-weight:800;
                            letter-spacing:1px;
                        ">
                            {label}
                        </div>
                    </div>

                    <div style="
                        color:#F4F0E7;
                        font-size:16px;
                        font-weight:900;
                        font-variant-numeric:tabular-nums;
                    ">
                        {record}
                    </div>
                </div>
            """

        hunt_html = ""

        for _, team in in_the_hunt.iterrows():

            code = team["Code"]
            name = team["Team"]
            record = f'{team["W"]}-{team["L"]}'
            games_back = team["Games Back"]

            if team["T"] > 0:
                record += f'-{team["T"]}'

            hunt_html += f"""
                <div style="
                    display:flex;
                    align-items:center;
                    gap:10px;
                    padding:9px 10px;
                    border-bottom:1px solid #302E29;
                ">
                    {logo(code, width=32)}

                    <div style="
                        flex:1;
                        color:#D8D3C8;
                        font-size:13px;
                        font-weight:700;
                    ">
                        {name}
                    </div>

                    <div style="
                        color:#AAA69C;
                        font-size:12px;
                        font-weight:700;
                    ">
                        {record}
                    </div>

                    <div style="
                        color:#D8B86D;
                        font-size:12px;
                        font-weight:900;
                        min-width:48px;
                        text-align:right;
                    ">
                        {games_back:.1f} GB
                    </div>
                </div>
            """

        if not hunt_html:
            hunt_html = """
                <div style="
                    color:#77736A;
                    padding:12px;
                    font-size:12px;
                ">
                    No teams currently within 2 games.
                </div>
            """

        st.html(f"""
            <div style="
                background:linear-gradient(145deg,#201F1B,#111110);
                border:1px solid #39362E;
                border-radius:14px;
                padding:14px;
                margin-bottom:16px;
                box-shadow:0 8px 22px #0005;
            ">
                <div style="
                    color:#D8B86D;
                    font-size:19px;
                    font-weight:900;
                    letter-spacing:2px;
                    padding:5px 8px 13px;
                    border-bottom:1px solid #39362E;
                ">
                    {conference}
                </div>

                {rows_html}

                <div style="
                    color:#D8B86D;
                    font-size:12px;
                    font-weight:900;
                    letter-spacing:2px;
                    padding:18px 8px 5px;
                ">
                    IN THE HUNT
                </div>

                {hunt_html}
            </div>
        """)

    playoff_left, playoff_right = st.columns(2)

    with playoff_left:
        render_playoff_conference("AFC")

    with playoff_right:
        render_playoff_conference("NFC")

    # --------------------------------------------------------
    # PLAYOFF SIMULATOR — VISUAL BRACKET
    # --------------------------------------------------------

    section("PLAYOFF SIMULATOR")

    simulator = st.session_state.playoff_simulator

    for conference in ("AFC", "NFC"):
        if conference not in simulator:
            simulator[conference] = build_playoff_bracket(
                playoff_picture[conference]["playoff_teams"],
                conference,
            )

    # --------------------------------------------------------
    # BRACKET STYLING
    # --------------------------------------------------------

    st.html("""
        <style>
            .bracket-heading {
                color: #D8B86D;
                font-size: 13px;
                font-weight: 900;
                letter-spacing: 2px;
                text-align: center;
                padding: 10px 2px;
                border-bottom: 2px solid #B99A5A;
                margin-bottom: 12px;
            }

            .bracket-game {
                background: linear-gradient(145deg,#201F1B,#111110);
                border: 1px solid #39362E;
                border-radius: 10px;
                padding: 9px 7px;
                margin-bottom: 12px;
                box-shadow: 0 5px 14px #0004;
            }

            .bracket-game-title {
                color: #B99A5A;
                font-size: 9px;
                font-weight: 900;
                letter-spacing: 1px;
                text-align: center;
                padding-bottom: 7px;
                border-bottom: 1px solid #39362E;
                margin-bottom: 7px;
            }

            .bracket-team {
                display: flex;
                align-items: center;
                gap: 5px;
                color: #F4F0E7;
                font-size: 11px;
                font-weight: 800;
                min-height: 40px;
                padding: 3px;
            }

            .bracket-team.winner {
                color: #D8B86D;
                background: #B99A5A18;
                border-radius: 6px;
            }

            .bracket-placeholder {
                color: #77736A;
                font-size: 10px;
                font-weight: 700;
                text-align: center;
                padding: 13px 3px;
                border: 1px dashed #39362E;
                border-radius: 7px;
                margin-bottom: 7px;
            }

            .bracket-vs {
                color: #77736A;
                font-size: 9px;
                font-weight: 900;
                text-align: center;
                padding: 3px;
            }

            .bracket-center {
                text-align: center;
                color: #D8B86D;
                font-weight: 900;
                letter-spacing: 2px;
            }
        </style>
    """)

    # --------------------------------------------------------
    # BRACKET HELPER FUNCTIONS
    # --------------------------------------------------------

    def resolve_bracket_team(bracket, value):
        if value is None:
            return None

        if isinstance(value, int):
            return bracket["teams"].get(value)

        return value

    def get_team_seed(bracket, code):
        if not code:
            return None

        for seed, team_code in bracket["teams"].items():
            if team_code == code:
                return seed

        return None

    def render_bracket_team(
            conference,
            bracket,
            round_name,
            matchup_index,
            code,
            selected_winner,
    ):
        if not code:
            st.html("""
                <div class="bracket-placeholder">
                    AWAITING WINNER
                </div>
            """)
            return

        info = TEAMS[code]
        seed = get_team_seed(bracket, code)
        is_winner = selected_winner == code

        # Unique container lets us style each team's button
        container_key = (
            f"team_{conference}_{round_name}_{matchup_index}_{code}"
        )

        logo_url = html.escape(info["logo"], quote=True)
        team_color = info["color"]
        secondary_color = info["secondary"]

        st.html(f"""
            <style>
                .st-key-{container_key} button {{
                    min-height: 48px;
                    height: 48px;
                    width: 100%;
                    border: 1px solid {team_color};
                    border-left: 4px solid {secondary_color};
                    border-radius: 6px;
                    background-color: {team_color}22;
                    background-image: url("{logo_url}");
                    background-repeat: no-repeat;
                    background-position: 10px center;
                    background-size: 32px 32px;
                    color: white;
                    font-size: 13px;
                    font-weight: 800;
                    text-align: right;
                    padding: 0 12px 0 48px;
                    box-shadow: {"0 0 10px " + team_color + "66" if is_winner else "none"};
                }}

                .st-key-{container_key} button:hover {{
                    border: 1px solid {secondary_color};
                    border-left: 4px solid {secondary_color};
                    background-color: {team_color}55;
                    color: white;
                }}
            </style>
        """)

        with st.container(key=container_key):
            if st.button(
                    f"#{seed}" if seed else "—",
                    key=f"bracket_{conference}_{round_name}_{matchup_index}_{code}",
                    use_container_width=True,
            ):
                simulator[conference] = advance_playoff_bracket(
                    bracket,
                    round_name,
                    matchup_index,
                    code,
                )
                st.rerun()

    def render_bracket_game(
            conference,
            bracket,
            round_name,
            matchup_index,
            team_one,
            team_two,
            game_title,
    ):
        team_one = resolve_bracket_team(bracket, team_one)
        team_two = resolve_bracket_team(bracket, team_two)

        selected_winner = bracket.get("winners", {}).get(
            f"{round_name}_{matchup_index}"
        )

        st.html(f"""
            <div class="bracket-game">
                <div class="bracket-game-title">
                    {game_title}
                </div>
            </div>
        """)

        render_bracket_team(
            conference,
            bracket,
            round_name,
            matchup_index,
            team_one,
            selected_winner,
        )

        st.html('<div class="bracket-vs">VS</div>')

        render_bracket_team(
            conference,
            bracket,
            round_name,
            matchup_index,
            team_two,
            selected_winner,
        )

    # --------------------------------------------------------
    # PREPARE BRACKET DATA
    # --------------------------------------------------------

    afc_bracket = simulator["AFC"]
    nfc_bracket = simulator["NFC"]

    # --------------------------------------------------------
    # SEVEN-COLUMN BRACKET
    # --------------------------------------------------------

    (
        nfc_wc_col,
        nfc_div_col,
        nfc_champ_col,
        super_bowl_col,
        afc_champ_col,
        afc_div_col,
        afc_wc_col,
    ) = st.columns([1.2, 1.15, 1.1, 1.3, 1.1, 1.15, 1.2])

    # ========================================================
    # NFC WILD CARD — LEFT EDGE
    # ========================================================

    with nfc_wc_col:

        st.html('<div class="bracket-heading">NFC<br>WILD CARD</div>')

        for i, (seed_one, seed_two) in enumerate(
                nfc_bracket["wild_card"]
        ):
            render_bracket_game(
                "NFC",
                nfc_bracket,
                "wild_card",
                i,
                nfc_bracket["teams"].get(seed_one),
                nfc_bracket["teams"].get(seed_two),
                f"GAME {i + 1}",
            )

    # ========================================================
    # NFC DIVISIONAL
    # ========================================================

    with nfc_div_col:

        st.html('<div class="bracket-heading">NFC<br>DIVISIONAL</div>')

        nfc_wc_winners = [
            nfc_bracket.get("winners", {}).get(f"wild_card_{i}")
            for i in range(3)
        ]

        st.html('<div style="height:65px;"></div>')

        if all(nfc_wc_winners):
            divisional_matchups = nfc_bracket["divisional"]
        else:
            # Show the available teams while Wild Card games remain.
            available_teams = [
                nfc_bracket["teams"].get(1),
                *[winner for winner in nfc_wc_winners if winner],
            ]

            available_teams.sort(
                key=lambda code: next(
                    seed for seed, team in nfc_bracket["teams"].items()
                    if team == code
                )
            )

            divisional_matchups = [
                (available_teams[0] if len(available_teams) > 0 else None,
                 available_teams[3] if len(available_teams) > 3 else None),
                (available_teams[1] if len(available_teams) > 1 else None,
                 available_teams[2] if len(available_teams) > 2 else None),
            ]

        for i, matchup in enumerate(divisional_matchups):
            render_bracket_game(
                "NFC",
                nfc_bracket,
                "divisional",
                i,
                matchup[0],
                matchup[1],
                f"GAME {i + 1}",
            )

            if i == 0:
                st.html('<div style="height:85px;"></div>')

    # ========================================================
    # NFC CHAMPIONSHIP
    # ========================================================

    with nfc_champ_col:

        st.html('<div class="bracket-heading">NFC<br>CHAMPIONSHIP</div>')
        st.html('<div style="height:190px;"></div>')

        nfc_div_winners = [
            nfc_bracket.get("winners", {}).get(f"divisional_{i}")
            for i in range(2)
        ]

        if all(nfc_div_winners):
            render_bracket_game(
                "NFC",
                nfc_bracket,
                "championship",
                0,
                nfc_div_winners[0],
                nfc_div_winners[1],
                "NFC TITLE GAME",
            )
        else:
            for code in nfc_div_winners:
                if code:
                    info = TEAMS[code]
                    seed = get_team_seed(nfc_bracket, code)

                    st.html(f"""
                        <div style="
                            display:flex;
                            align-items:center;
                            gap:8px;
                            padding:9px;
                            margin-bottom:8px;
                            border-left:4px solid {info['color']};
                            background:{info['color']}22;
                            border-radius:5px;
                        ">
                            {logo(code, width=34)}
                            <span style="color:white;font-weight:800;">
                                #{seed} {info['name']}
                            </span>
                        </div>
                    """)
                else:
                    st.html("""
                        <div class="bracket-placeholder">
                            AWAITING DIVISIONAL WINNER
                        </div>
                    """)

        nfc_champion = nfc_bracket.get("conference_champion")

        if nfc_champion:
            st.success(f"NFC: {TEAMS[nfc_champion]['name']}")

    # ========================================================
    # SUPER BOWL — CENTER
    # ========================================================

    afc_champion = afc_bracket.get("conference_champion")
    nfc_champion = nfc_bracket.get("conference_champion")

    current_super_bowl_matchup = (
        (afc_champion, nfc_champion)
        if afc_champion and nfc_champion
        else None
    )

    if current_super_bowl_matchup != st.session_state.super_bowl_matchup:
        st.session_state.super_bowl_matchup = current_super_bowl_matchup
        st.session_state.super_bowl_winner = None

    with super_bowl_col:

        st.html("""
            <div class="bracket-heading">
                SUPER<br>BOWL
            </div>
            <div style="height:130px;"></div>
        """)

        for conference, code, bracket in (
                ("NFC", nfc_champion, nfc_bracket),
                ("AFC", afc_champion, afc_bracket),
        ):

            if code:
                info = TEAMS[code]
                seed = get_team_seed(bracket, code)
                is_selected = st.session_state.super_bowl_winner == code

                st.html(f"""
                    <div style="
                        display:flex;
                        align-items:center;
                        gap:8px;
                        padding:10px 6px;
                        margin-bottom:8px;
                        border:1px solid {info['color']};
                        border-left:4px solid {info['secondary']};
                        border-radius:6px;
                        background:{info['color']}22;
                        box-shadow:{"0 0 12px " + info['color'] + "66" if is_selected else "none"};
                    ">
                        {logo(code, width=48)}
                        <div style="min-width:0;">
                            <div style="color:white;font-weight:900;font-size:11px;">
                                #{seed} {info['name']}
                            </div>
                            <div style="color:#D8B86D;font-size:9px;">
                                {conference} CHAMPION
                            </div>
                        </div>
                    </div>
                """)

                if current_super_bowl_matchup:
                    if st.button(
                            f"🏆 {info['name']}",
                            key=f"super_bowl_{code}",
                            use_container_width=True,
                    ):
                        st.session_state.super_bowl_winner = code
                        st.rerun()

            else:
                st.html(f"""
                    <div class="bracket-placeholder">
                        {conference} CHAMPION<br>
                        AWAITING WINNER
                    </div>
                """)

        if current_super_bowl_matchup:
            st.html("""
                <div style="
                    text-align:center;
                    color:#D8B86D;
                    font-size:24px;
                    font-weight:1000;
                    padding:10px;
                ">
                    VS
                </div>
            """)

    # ========================================================
    # AFC CHAMPIONSHIP
    # ========================================================

    with afc_champ_col:

        st.html('<div class="bracket-heading">AFC<br>CHAMPIONSHIP</div>')
        st.html('<div style="height:190px;"></div>')

        afc_div_winners = [
            afc_bracket.get("winners", {}).get(f"divisional_{i}")
            for i in range(2)
        ]

        if all(afc_div_winners):
            render_bracket_game(
                "AFC",
                afc_bracket,
                "championship",
                0,
                afc_div_winners[0],
                afc_div_winners[1],
                "AFC TITLE GAME",
            )
        else:
            for code in afc_div_winners:
                if code:
                    info = TEAMS[code]
                    seed = get_team_seed(afc_bracket, code)

                    st.html(f"""
                        <div style="
                            display:flex;
                            align-items:center;
                            gap:8px;
                            padding:9px;
                            margin-bottom:8px;
                            border-left:4px solid {info['color']};
                            background:{info['color']}22;
                            border-radius:5px;
                        ">
                            {logo(code, width=34)}
                            <span style="color:white;font-weight:800;">
                                #{seed} {info['name']}
                            </span>
                        </div>
                    """)
                else:
                    st.html("""
                        <div class="bracket-placeholder">
                            AWAITING DIVISIONAL WINNER
                        </div>
                    """)

        if afc_champion:
            st.success(f"AFC: {TEAMS[afc_champion]['name']}")

    # ========================================================
    # AFC DIVISIONAL
    # ========================================================

    with afc_div_col:

        st.html('<div class="bracket-heading">AFC<br>DIVISIONAL</div>')
        st.html('<div style="height:65px;"></div>')

        afc_wc_winners = [
            afc_bracket.get("winners", {}).get(f"wild_card_{i}")
            for i in range(3)
        ]

        if all(afc_wc_winners):
            divisional_matchups = afc_bracket["divisional"]
        else:
            available_teams = [
                afc_bracket["teams"].get(1),
                *[winner for winner in afc_wc_winners if winner],
            ]

            available_teams.sort(
                key=lambda code: next(
                    seed for seed, team in afc_bracket["teams"].items()
                    if team == code
                )
            )

            divisional_matchups = [
                (available_teams[0] if len(available_teams) > 0 else None,
                 available_teams[3] if len(available_teams) > 3 else None),
                (available_teams[1] if len(available_teams) > 1 else None,
                 available_teams[2] if len(available_teams) > 2 else None),
            ]

        for i, matchup in enumerate(divisional_matchups):
            render_bracket_game(
                "AFC",
                afc_bracket,
                "divisional",
                i,
                matchup[0],
                matchup[1],
                f"GAME {i + 1}",
            )

            if i == 0:
                st.html('<div style="height:85px;"></div>')

    # ========================================================
    # AFC WILD CARD — RIGHT EDGE
    # ========================================================

    with afc_wc_col:

        st.html('<div class="bracket-heading">AFC<br>WILD CARD</div>')

        for i, (seed_one, seed_two) in enumerate(
                afc_bracket["wild_card"]
        ):
            render_bracket_game(
                "AFC",
                afc_bracket,
                "wild_card",
                i,
                afc_bracket["teams"].get(seed_one),
                afc_bracket["teams"].get(seed_two),
                f"GAME {i + 1}",
            )

    # --------------------------------------------------------
    # SUPER BOWL CHAMPION CELEBRATION
    # --------------------------------------------------------

    winner = st.session_state.super_bowl_winner

    if winner and current_super_bowl_matchup:

        winner_name = TEAMS[winner]["name"]

        nfc_color = TEAMS[nfc_champion]["color"]
        afc_color = TEAMS[afc_champion]["color"]

        nfc_secondary = TEAMS[nfc_champion]["secondary"]
        afc_secondary = TEAMS[afc_champion]["secondary"]

        confetti_colors = [
            "#D8B86D",
            "#FFFFFF",
            "#E74C3C",
            "#4DA6FF",
            "#72D572",
        ]

        confetti = "".join(
            f"""
            <span class="sb-confetti" style="
                left:{(i * 37) % 100}%;
                background:{confetti_colors[i % len(confetti_colors)]};
                animation-delay:{-(i % 12) * 0.3}s;
                animation-duration:{3 + (i % 5) * 0.45}s;
            "></span>
            """
            for i in range(45)
        )

        st.html(f"""
            <style>
                                @keyframes sb-confetti-fall {{
                    0% {{
                        transform:translateY(-10vh) rotate(0deg);
                        opacity:1;
                    }}
                    100% {{
                        transform:translateY(110vh) rotate(720deg);
                        opacity:0;
                    }}
                }}

                @keyframes sb-celebration-dismiss {{
                    0%, 75% {{
                        opacity:1;
                        visibility:visible;
                    }}
                    100% {{
                        opacity:0;
                        visibility:hidden;
                    }}
                }}
                    100% {{
                        opacity:0;
                        max-height:0;
                        min-height:0;
                        padding:0;
                        margin:0;
                        border-width:0;
                    }}
                }}

                @keyframes sb-champion-glow {{
                    0%,100% {{
                        text-shadow:0 0 15px #D8B86D55;
                    }}
                    50% {{
                        text-shadow:0 0 35px #D8B86D;
                    }}
                }}

                .sb-celebration {{
                    position:fixed;
                    top:0;
                    left:0;
                    right:0;
                    bottom:0;
                    z-index:9999999;
                    overflow:hidden;
                    height:100vh;
                    width:100vw;    
                    max-width:none;
                    min-height:100vh;
                    box-sizing:border-box;
                    display:flex;
                    flex-direction:column;
                    align-items:center;
                    justify-content:center;
                    text-align:center;
                    padding:45px 15px;
                    margin:0;
                    border:2px solid #D8B86D;
                    border-radius:0;
                    background:
                        radial-gradient(
                            circle at 50% 30%,
                            {TEAMS[winner]["secondary"]} 0%,
                            {TEAMS[winner]["color"]} 55%,
                            #080808 100%
                        );

                    animation:sb-celebration-dismiss 5s ease forwards;
                }}

                .sb-confetti {{
                    position:absolute;
                    top:-25px;
                    width:9px;
                    height:17px;
                    border-radius:20px;
                    animation:sb-confetti-fall linear infinite;
                    pointer-events:none;
                }}

                .sb-champion-title {{
                    color:#D8B86D;
                    font-size:clamp(28px,5vw,52px);
                    font-weight:1000;
                    letter-spacing:3px;
                    animation:sb-champion-glow 2s ease-in-out infinite;
                    margin:20px 0 10px;
                }}
            </style>

            <div class="sb-celebration">
                {confetti}

                <div style="
                    position:relative;
                    z-index:2;
                    font-size:15px;
                    color:#D8B86D;
                    font-weight:900;
                    letter-spacing:6px;
                ">
                    THE SEASON ENDS HERE
                </div>

                <div style="position:relative;z-index:2;margin:20px 0;">
                    {logo(winner, width=170)}
                </div>

                <div class="sb-champion-title"
                     style="position:relative;z-index:2;">
                    SUPER BOWL CHAMPIONS!
                </div>

                <div style="
                    position:relative;
                    z-index:2;
                    color:#F4F0E7;
                    font-size:22px;
                    font-weight:800;
                ">
                    Congratulations to the
                </div>

                <div style="
                    position:relative;
                    z-index:2;
                    color:#D8B86D;
                    font-size:30px;
                    font-weight:1000;
                    margin-top:10px;
                ">
                    {winner_name}!
                </div>

                <div style="
                    position:relative;
                    z-index:2;
                    color:#AAA69C;
                    font-size:12px;
                    letter-spacing:3px;
                    margin-top:25px;
                ">
                    YOUR SUPER BOWL WINNER
                </div>
            </div>
        """)

        if st.button(
                "↻ RESET SUPER BOWL",
                key="reset_super_bowl",
                use_container_width=True,
        ):
            st.session_state.super_bowl_winner = None
            st.rerun()


# ============================================================
# APP ROUTER
# ============================================================

header()
reset_page_scroll()

if rankings is None:
    st.error("The NFL ratings CSV is unavailable or missing required columns.")
    st.code(str(CSV_PATH), language="text")
else:
    current_page = st.session_state.page
    if current_page == "HOME":
        render_home()
    elif current_page == "TEAMS":
        render_teams()
    elif current_page == "PROFILE":
        render_profile()
    elif current_page == "RANKINGS":
        render_rankings(
            rankings=rankings,
            TEAMS=TEAMS,
            hero=hero,
            section=section,
            grade_label=grade_label,
            logo=logo,
            go=go,
        )
    elif current_page == "WAR":
        render_war_room()
    elif current_page == "WEEKLY":
        render_weekly()
    elif current_page == "HISTORY":
        render_history()
    elif current_page == "REPORT":
        render_report(
            rankings=rankings,
            TEAMS=TEAMS,
            CACHE_DIR=CACHE_DIR,
            NFL_SEASON=NFL_SEASON,
            get_results=get_results,
            get_weekly_team_stats=get_weekly_team_stats,
            get_team_row=get_team_row,
            get_team_week_row=get_team_week_row,
            load_weekly_award_play_by_play=load_weekly_award_play_by_play,
            get_weekly_rosters=get_weekly_rosters,
            hero=hero,
            section=section,
            logo=logo,
        )
    elif current_page == "METHOD":
        render_methodology()
    else:
        render_home()

footer()

# Save a changed ratings snapshot, or one checkpoint for a newly completed week.
# The history layer deduplicates repeated reruns within the same week.
if rankings is not None:
    save_snapshot(rankings)

