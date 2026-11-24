import html

import streamlit as st


def render_rankings(rankings, TEAMS, hero, section, grade_label, logo, go):
    hero("THE LEAGUE TABLE", "POWER", "RANKINGS.", "32 TEAMS. ONE ORDER. BUILT BY THE RATINGS ENGINE.")

    if rankings is None:
        st.error("Rankings CSV could not be loaded.")
        return

    sort_options = {
        "Overall Rating": "overall_rating",
        "Offense": "offensive_rating",
        "Defense": "defensive_rating",
        "Special Teams": "special_teams_rating",
        "Discipline": "discipline_rating",
        "On-Field": "on_field_rating",
    }

    f1, f2, f3, f4 = st.columns([2, 1, 1, 1.5])

    with f1:
        search = st.text_input(
            "SEARCH TEAM",
            placeholder="Type a team name or abbreviation..."
        )

    with f2:
        conference = st.selectbox(
            "CONFERENCE", ["ALL", "AFC", "NFC"]
        )

    with f3:
        division = st.selectbox(
            "DIVISION", ["ALL", "East", "North", "South", "West"]
        )

    with f4:
        sort_by = st.selectbox(
            "SORT RANKINGS BY",
            list(sort_options.keys())
        )

    data = rankings.copy()

    data["conference"] = data["team"].map(
        lambda code: TEAMS.get(code, {}).get("conf", "")
    )
    data["division"] = data["team"].map(
        lambda code: TEAMS.get(code, {}).get("div", "")
    )
    data["team_name"] = data["team"].map(
        lambda code: TEAMS.get(code, {}).get("name", code)
    )

    # Sort the full league before applying filters so ranks
    # always represent each team's position across all 32 teams.
    sort_column = sort_options[sort_by]

    data = data.sort_values(
        sort_column,
        ascending=False,
        na_position="last"
    ).reset_index(drop=True)

    data["display_rank"] = range(1, len(data) + 1)

    if conference != "ALL":
        data = data[data["conference"] == conference]

    if division != "ALL":
        data = data[data["division"] == division]

    if search.strip():
        needle = search.strip().lower()
        data = data[
            data.apply(
                lambda row: needle in str(row["team"]).lower()
                            or needle in str(row["team_name"]).lower(),
                axis=1,
            )
        ]

    section(f"RANKED TEAMS / {len(data)} RESULTS")

    if data.empty:
        st.info("No teams match those filters.")
        return

    for _, row in data.iterrows():
        rating = float(row[sort_column])

        # Always classify teams using their OVERALL rating,
        # even when the user sorts by a different category.
        overall_rating = float(row["overall_rating"])
        tier = grade_label(overall_rating)

        code = str(row["team"])
        info = TEAMS.get(code)

        if not info:
            continue

        st.markdown(
            f'<div class="rank-row" style="border-left-color:{info["color"]}">'
            f'<div class="rank-num">#{int(row["display_rank"]):02d}</div>{logo(code, 56)}'
            f'<div class="rank-name">{html.escape(info["name"].upper())}'
            f'<div class="micro">{info["conf"]} {info["div"]} / '
            f'<span class="tier">{html.escape(tier.upper())}</span></div></div>'
            f'<div class="rank-score">{rating:.1f}</div></div>',
            unsafe_allow_html=True,
        )

        if st.button(f"OPEN {code} PROFILE →", key=f"ranking_open_{code}"):
            go("PROFILE", code, True)

