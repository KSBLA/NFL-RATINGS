"""Weekly NFL report rendering: winners/losers, distinctions, awards, and game breakdowns."""

import html

import pandas as pd
import streamlit as st


def render_report(
    *,
    rankings,
    TEAMS,
    CACHE_DIR,
    NFL_SEASON,
    get_results,
    get_weekly_team_stats,
    get_team_row,
    get_team_week_row,
    load_weekly_award_play_by_play,
    hero,
    section,
    logo,
):
    hero("THE NFL RATINGS DESK", "THE WEEKLY", "REPORT.", "THE WEEK'S BIGGEST MOVERS, MOMENTS, AWARDS AND MATCHUPS.")
    if rankings is None:
        st.error("Rankings CSV could not be loaded.")
        return

    results = get_results()
    weeks = sorted({
        int(game.get("week")) for game in results
        if str(game.get("week", "")).isdigit()
    })
    if not weeks:
        st.info("No completed games are available for a weekly report yet.")
        return

    selected_week = st.selectbox(
        "REPORT WEEK", weeks, index=len(weeks) - 1,
        format_func=lambda value: f"WEEK {value}", key="weekly_report_week",
    )
    games = []
    for game in results:
        try:
            if int(game.get("week")) != int(selected_week):
                continue
            home_score, away_score = int(game.get("home_score")), int(game.get("away_score"))
            home, away = str(game.get("home", "")).upper(), str(game.get("away", "")).upper()
            if home not in TEAMS or away not in TEAMS:
                continue
            games.append((game, home_score, away_score))
        except (TypeError, ValueError):
            continue

    stats = get_weekly_team_stats()
    stats_ready = isinstance(stats, pd.DataFrame) and not stats.empty and {"team", "week"}.issubset(stats.columns)
    week_stats = pd.DataFrame()
    if stats_ready:
        week_stats = stats[pd.to_numeric(stats["week"], errors="coerce") == int(selected_week)].copy()
        week_stats["team_code"] = week_stats["team"].astype(str).str.upper().replace({"LA": "LAR"})

    def team_name(code):
        return TEAMS.get(code, {}).get("name", code)

    def team_logo(code, width=68):
        return logo(code, width) if code in TEAMS else ""

    def card_shell(kicker, headline, subline, visual, accent="#C6A96B", foot=""):
        award_class = " weekly-award-card" if "OF THE WEEK" in str(kicker) else ""
        return (
            f'<div class="weekly-feature-card{award_class}" style="--feature-accent:{accent}">'
            f'<div class="weekly-feature-kicker">{html.escape(str(kicker))}</div>'
            f'<div class="weekly-feature-visual">{visual}</div>'
            f'<div class="weekly-feature-head">{html.escape(str(headline))}</div>'
            f'<div class="weekly-feature-sub">{html.escape(str(subline))}</div>'
            f'{f"<div class=weekly-feature-foot>{html.escape(str(foot))}</div>" if foot else ""}'
            '</div>'
        )

    st.markdown("""
    <style>
    .weekly-feature-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:15px;margin:14px 0 28px}
    .weekly-feature-grid.two{grid-template-columns:repeat(2,minmax(0,1fr))}
    .weekly-feature-grid.four{grid-template-columns:repeat(4,minmax(0,1fr));gap:13px;align-items:stretch}
    .weekly-feature-card{position:relative;overflow:hidden;min-height:210px;padding:18px 17px 16px;border:1px solid #ffffff1b;border-radius:17px;background:linear-gradient(145deg,#202a37 0%,#151c27 72%);box-shadow:0 9px 24px #0003;font-family:inherit}
    .weekly-feature-grid.four .weekly-feature-card{display:flex;flex-direction:column;min-height:236px;padding:17px 14px 15px}
    .weekly-feature-grid.four .weekly-feature-kicker{display:flex;align-items:center;justify-content:center;min-height:28px;font-size:11px;line-height:1.25;letter-spacing:1.35px}
    .weekly-feature-grid.four .weekly-feature-visual{min-height:76px;margin:7px 0}
    .weekly-feature-grid.four .weekly-feature-visual img{max-width:66px;max-height:66px}
    .weekly-feature-grid.four .weekly-feature-head{min-height:40px;font-size:17px;line-height:1.2;margin-top:4px;display:flex;align-items:center;justify-content:center}
    .weekly-feature-grid.four .weekly-feature-sub{font-size:11px;line-height:1.45;margin-top:7px}
    .weekly-feature-grid.four .weekly-feature-foot{font-size:9px;line-height:1.35;margin-top:auto;padding-top:8px;text-align:center}
    .weekly-feature-card:before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;background:var(--feature-accent)}
    .weekly-feature-kicker{font-size:12px;font-weight:950;letter-spacing:1.6px;color:var(--feature-accent);text-transform:uppercase;text-align:center;line-height:1.2}
    .weekly-feature-visual{display:flex;align-items:center;justify-content:center;gap:13px;min-height:84px;margin:8px 0}
    .weekly-feature-visual img{max-width:76px;max-height:76px;object-fit:contain;filter:drop-shadow(0 6px 9px #0008)}
    .weekly-feature-visual .versus{font-size:13px;font-weight:900;letter-spacing:2px;color:#aeb8c6}
    .weekly-feature-head{font-size:19px;line-height:1.15;font-weight:900;color:#f4f0e7;margin-top:6px;text-align:center}
    .weekly-feature-sub{font-size:12px;line-height:1.45;color:#c2cbd5;margin-top:7px;text-align:center}
    .weekly-feature-foot{font-size:10px;color:#9da9b7;margin-top:10px;letter-spacing:.4px}
    .weekly-outcome-group{border-radius:19px;padding:15px 15px 2px;margin:15px 0 20px;border:1px solid #ffffff20}
    .weekly-outcome-group.winners{background:linear-gradient(135deg,#122a24 0%,#17231f 100%);border-color:#3c9b704d}
    .weekly-outcome-group.losers{background:linear-gradient(135deg,#301d22 0%,#241b22 100%);border-color:#c76b704d}
    .weekly-outcome-title{font-size:17px;font-weight:950;letter-spacing:2.5px;text-align:center;margin:0 0 3px;color:#8cddb0}
    .weekly-outcome-group.losers .weekly-outcome-title{color:#f09a9a}
    .weekly-outcome-note{text-align:center;font-size:11px;color:#bdc7d1;margin:0 0 9px}
    .weekly-feature-grid.awards{grid-template-columns:repeat(3,minmax(0,1fr));gap:11px}
    .weekly-award-card{min-height:166px;padding:13px 12px 12px}
    .weekly-award-card .weekly-feature-visual{min-height:57px;margin:4px 0}
    .weekly-award-card .weekly-feature-visual img{max-width:52px;max-height:52px}
    .weekly-award-card .weekly-feature-kicker{font-size:11px;letter-spacing:1.2px}.weekly-award-card .weekly-feature-head{font-size:16px;margin-top:3px}
    .weekly-award-card .weekly-feature-sub{font-size:11px;margin-top:5px}
    .weekly-award-card .weekly-feature-foot{font-size:9px;margin-top:6px}
    @media(max-width:900px){.weekly-feature-grid.four{grid-template-columns:repeat(2,minmax(0,1fr))}.weekly-feature-grid.awards{grid-template-columns:repeat(2,minmax(0,1fr))}}
    @media(max-width:650px){.weekly-feature-grid,.weekly-feature-grid.two,.weekly-feature-grid.four,.weekly-feature-grid.awards{grid-template-columns:1fr}.weekly-feature-card{min-height:0}}
    </style>
    """, unsafe_allow_html=True)

    if not games:
        st.info("There are no completed games recorded for this week.")

    # Build standings only through the selected week so a historical report never
    # borrows results from weeks that had not happened yet.
    records_to_date = {code: {"W": 0, "L": 0, "T": 0, "PF": 0, "PA": 0} for code in TEAMS}
    for result in results:
        try:
            if int(result.get("week")) > int(selected_week):
                continue
            h, a = str(result.get("home", "")).upper(), str(result.get("away", "")).upper()
            hs, aws = int(result.get("home_score")), int(result.get("away_score"))
            if h not in records_to_date or a not in records_to_date:
                continue
            records_to_date[h]["PF"] += hs; records_to_date[h]["PA"] += aws
            records_to_date[a]["PF"] += aws; records_to_date[a]["PA"] += hs
            if hs > aws:
                records_to_date[h]["W"] += 1; records_to_date[a]["L"] += 1
            elif aws > hs:
                records_to_date[a]["W"] += 1; records_to_date[h]["L"] += 1
            else:
                records_to_date[h]["T"] += 1; records_to_date[a]["T"] += 1
        except (TypeError, ValueError):
            continue

    standings_rows = []
    for code, rec in records_to_date.items():
        gp = rec["W"] + rec["L"] + rec["T"]
        standings_rows.append({
            "code": code, "conf": TEAMS[code].get("conf"), "div": TEAMS[code].get("div"),
            "wins": rec["W"], "losses": rec["L"], "ties": rec["T"],
            "pct": (rec["W"] + .5 * rec["T"]) / gp if gp else 0.0,
            "diff": rec["PF"] - rec["PA"],
        })
    def ranked_rows(rows):
        return sorted(rows, key=lambda r: (r["pct"], r["wins"], r["diff"]), reverse=True)
    conf_ranks, div_ranks = {}, {}
    for conf in ("AFC", "NFC"):
        conf_ranks[conf] = {r["code"]: i + 1 for i, r in enumerate(ranked_rows([x for x in standings_rows if x["conf"] == conf]))}
    for conf in ("AFC", "NFC"):
        for div in ("East", "North", "South", "West"):
            rows = ranked_rows([x for x in standings_rows if x["conf"] == conf and x["div"] == div])
            div_ranks.update({r["code"]: i + 1 for i, r in enumerate(rows)})
    draft_order = {r["code"]: i + 1 for i, r in enumerate(sorted(standings_rows, key=lambda r: (r["pct"], r["wins"], r["diff"])))}

    # Outcome impact score: performance and standings leverage are combined.
    # A poor team's late win can be a negative because it costs draft position.
    week_number = int(selected_week)
    def impact_for(code, opponent, score, opp_score, game):
        margin = score - opp_score
        rec = next(x for x in standings_rows if x["code"] == code)
        opp = next(x for x in standings_rows if x["code"] == opponent)
        win = margin > 0
        tie = margin == 0
        rating = get_team_row(code)
        opp_rating = get_team_row(opponent)
        rating_value = float(rating["overall_rating"]) if rating is not None and pd.notna(rating.get("overall_rating")) else 50.0
        opp_rating_value = float(opp_rating["overall_rating"]) if opp_rating is not None and pd.notna(opp_rating.get("overall_rating")) else 50.0
        expected_edge = (rating_value - opp_rating_value) / 12.0
        performance = (15 if win else -15 if not tie else 0) + max(-14, min(14, margin * .55)) - expected_edge * 2.5
        division_game = TEAMS[code].get("div") == TEAMS[opponent].get("div") and TEAMS[code].get("conf") == TEAMS[opponent].get("conf")
        conference_game = TEAMS[code].get("conf") == TEAMS[opponent].get("conf")
        # Closer races carry more leverage; ranks are based only on results through this week.
        conf_rank = conf_ranks[rec["conf"]][code]
        div_rank = div_ranks[code]
        conf_pressure = max(0, 9 - conf_rank) / 8
        div_pressure = max(0, 4 - div_rank) / 3
        importance = (5 if division_game else 0) + (2.5 if conference_game else 0) + conf_pressure * 5 + div_pressure * 4
        if win:
            performance += importance
        elif not tie:
            performance -= importance
        # Bottom teams are increasingly draft-sensitive as the season progresses.
        draft_slot = draft_order[code]
        draft_relevance = max(0, (draft_slot - 20) / 12) * min(1.0, week_number / 10)
        if win and draft_relevance:
            performance -= 8 * draft_relevance
        elif not win and draft_relevance:
            performance += 2.5 * draft_relevance
        return performance, {
            "win": win, "tie": tie, "margin": margin, "division": division_game,
            "conf_rank": conf_rank, "div_rank": div_rank, "draft_slot": draft_slot,
            "importance": importance, "draft_relevance": draft_relevance,
        }

    team_impacts = {}
    for game, hs, aws in games:
        home, away = str(game["home"]).upper(), str(game["away"]).upper()
        home_score, home_context = impact_for(home, away, hs, aws, game)
        away_score, away_context = impact_for(away, home, aws, hs, game)
        team_impacts[home] = (home_score, home_context, away, hs, aws)
        team_impacts[away] = (away_score, away_context, home, aws, hs)

    section("WINNERS & LOSERS")
    st.caption("A weekly impact read — not simply a list of teams that won or lost. Game performance is weighed alongside division and conference races, playoff positioning and late-season draft consequences.")
    if team_impacts:
        winner_codes = [code for code, item in sorted(team_impacts.items(), key=lambda kv: kv[1][0], reverse=True)[:3]]
        loser_codes = [code for code, item in sorted(team_impacts.items(), key=lambda kv: kv[1][0])[:3]]
        winner_cards, loser_cards = [], []
        for code in winner_codes:
            impact, ctx, opponent, score, opp_score = team_impacts[code]
            rec = next(x for x in standings_rows if x["code"] == code)
            if ctx["win"]:
                reason = f"Beat {team_name(opponent)} by {abs(ctx['margin'])}; "
            elif ctx["tie"]:
                reason = f"Tied {team_name(opponent)}; "
            else:
                reason = f"Limited the damage against {team_name(opponent)}; "
            stakes = "division-race result" if ctx["division"] else ("conference-race result" if ctx["importance"] >= 6 else "strong weekly impact")
            foot = f"{rec['wins']}-{rec['losses']}-{rec['ties']} through Week {selected_week} · {stakes}"
            winner_cards.append(card_shell("WEEKLY WINNER", team_name(code), f"{reason}{stakes.title()}.", team_logo(code, 74), TEAMS[code]["color"], foot))
        for code in loser_codes:
            impact, ctx, opponent, score, opp_score = team_impacts[code]
            rec = next(x for x in standings_rows if x["code"] == code)
            if ctx["win"] and ctx["draft_relevance"] > .15:
                reason = f"Won against {team_name(opponent)}, but the result cost valuable draft position."
            elif not ctx["win"]:
                reason = f"Lost to {team_name(opponent)} by {abs(ctx['margin'])}; the result carries standings damage."
            else:
                reason = f"The result fell short of what the team needed against {team_name(opponent)}."
            foot = f"{rec['wins']}-{rec['losses']}-{rec['ties']} through Week {selected_week} · impact score {impact:+.1f}"
            loser_cards.append(card_shell("WEEKLY LOSER", team_name(code), reason, team_logo(code, 74), "#C97870", foot))
        st.markdown(
            '<div class="weekly-outcome-group winners">'
            '<div class="weekly-outcome-title">THE WEEK’S BIGGEST WINNERS</div>'
            '<div class="weekly-outcome-note">Teams whose results delivered the biggest positive impact</div>'
            '<div class="weekly-feature-grid">' + ''.join(winner_cards) + '</div></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="weekly-outcome-group losers">'
            '<div class="weekly-outcome-title">THE WEEK’S BIGGEST LOSERS</div>'
            '<div class="weekly-outcome-note">Teams whose results carried the biggest negative impact</div>'
            '<div class="weekly-feature-grid">' + ''.join(loser_cards) + '</div></div>',
            unsafe_allow_html=True,
        )
    else:
        st.info("Winners and losers will appear when completed game results are available.")

    section("WEEKLY DISTINCTIONS")
    distinction_cards = []
    if games:
        blowout = max(games, key=lambda item: abs(item[1] - item[2]))
        bg, bhs, bas = blowout
        bh, ba = str(bg["home"]).upper(), str(bg["away"]).upper()
        margin = abs(bhs - bas)
        blowout_visual = team_logo(ba, 58) + '<span class="versus">VS</span>' + team_logo(bh, 58)
        blowout_winner = bh if bhs > bas else ba if bas > bhs else None
        blowout_loser = ba if blowout_winner == bh else bh if blowout_winner == ba else None
        blowout_headline = (
            f"{team_name(blowout_winner)} over {team_name(blowout_loser)}"
            if blowout_winner else f"{team_name(ba)} and {team_name(bh)} tied"
        )
        blowout_winner_score = max(bas, bhs)
        blowout_loser_score = min(bas, bhs)
        blowout_score_text = (
            f"Won {blowout_winner_score}–{blowout_loser_score} · {margin}-point margin"
            if blowout_winner else f"Tied {bhs}–{bas} · no margin"
        )
        distinction_cards.append(card_shell("BIGGEST BLOWOUT", blowout_headline, blowout_score_text, blowout_visual, "#D3A64F"))

        shootout = max(games, key=lambda item: item[1] + item[2])
        sg, shs, sas = shootout
        sh, sa = str(sg["home"]).upper(), str(sg["away"]).upper()
        distinction_cards.append(card_shell("SHOOTOUT OF THE WEEK", f"{team_name(sa)} at {team_name(sh)}", f"{sas}–{shs} · {sas + shs} combined points", team_logo(sa, 56) + '<span class="versus">VS</span>' + team_logo(sh, 56), "#D77C55"))

        defensive = min(games, key=lambda item: item[1] + item[2])
        dg, dhs, das = defensive
        dh, da = str(dg["home"]).upper(), str(dg["away"]).upper()
        distinction_cards.append(card_shell("DEFENSIVE BATTLE", f"{team_name(da)} at {team_name(dh)}", f"{das}–{dhs} · {das + dhs} combined points", team_logo(da, 56) + '<span class="versus">VS</span>' + team_logo(dh, 56), "#6D9C9A"))

        upset_candidates = []
        for game, hs, aws in games:
            home, away = str(game["home"]).upper(), str(game["away"]).upper()
            winner = home if hs > aws else away if aws > hs else None
            loser = away if winner == home else home if winner else None
            if not winner:
                continue
            win_row, lose_row = get_team_row(winner), get_team_row(loser)
            if win_row is not None and lose_row is not None:
                gap = float(lose_row["overall_rating"]) - float(win_row["overall_rating"])
                if gap > 0:
                    winner_score, loser_score = (hs, aws) if winner == home else (aws, hs)
                    upset_candidates.append((gap, winner, loser, winner_score, loser_score))
        if upset_candidates:
            gap, uw, ul, winner_score, loser_score = max(upset_candidates, key=lambda item: item[0])
            upset_visual = team_logo(uw, 62) + '<span class="versus">UPSET</span>' + team_logo(ul, 62)
            distinction_cards.insert(0, card_shell("BIGGEST RATING UPSET", f"{team_name(uw)} over {team_name(ul)}", f"Won {winner_score}–{loser_score} despite a {gap:.1f}-point deficit in current overall ratings", upset_visual, "#B69AE0", "Current ratings comparison, not historical pregame odds."))
        else:
            distinction_cards.insert(0, card_shell("BIGGEST RATING UPSET", "No qualifying upset", "No lower-rated team defeated a higher-rated team this week.", '<div class="versus">RATINGS</div>', "#B69AE0"))
    if distinction_cards:
        st.markdown('<div class="weekly-feature-grid four">' + ''.join(distinction_cards) + '</div>', unsafe_allow_html=True)
    else:
        st.info("Weekly distinctions will appear when completed game results are available.")

    section("WEEKLY AWARDS")
    st.caption("Six conference awards are selected from the selected week's player-level play-by-play. Stat lines show the production behind each selection; missing metrics are not invented.")
    award_pbp_path = CACHE_DIR / f"play_by_play_{NFL_SEASON}.parquet"
    pbp = (
        load_weekly_award_play_by_play(
            str(award_pbp_path),
            award_pbp_path.stat().st_mtime_ns,
            int(selected_week),
            int(NFL_SEASON),
        )
        if award_pbp_path.exists()
        else pd.DataFrame()
    )
    award_results = {"AFC": [], "NFC": []}

    def numeric_sum(frame, column):
        if column not in frame.columns:
            return 0.0
        return float(pd.to_numeric(frame[column], errors="coerce").fillna(0).sum())

    def event_sum(frame, preferred_columns):
        """Use the first available representation of an event, avoiding double counts."""
        for column in preferred_columns:
            if column in frame.columns:
                return numeric_sum(frame, column)
        return 0.0

    if isinstance(pbp, pd.DataFrame) and not pbp.empty and "week" in pbp.columns:
        # The cached loader has already narrowed this to the selected week/season.
        # Keep only the small weekly frame and normalize team codes once.
        pbp_data = pbp.copy()
        team_aliases = {"LA": "LAR", "WSH": "WAS", "JAC": "JAX"}
        played_codes = {
            team_aliases.get(str(g[0].get(side, "")).upper(), str(g[0].get(side, "")).upper())
            for g in games for side in ("home", "away")
        }
        if "posteam" in pbp_data.columns:
            pbp_data["team_code"] = pbp_data["posteam"].astype(str).str.upper().replace(team_aliases)
            pbp_data = pbp_data[pbp_data["team_code"].isin(played_codes)].copy()
        else:
            pbp_data = pd.DataFrame()

        def top_player(position, conference):
            if pbp_data.empty:
                return None
            role_columns = {
                "QB": ("passer_player_name", "rusher_player_name"),
                "RB": ("rusher_player_name", "receiver_player_name"),
                "WR": ("receiver_player_name",),
            }[position]
            available_roles = [column for column in role_columns if column in pbp_data.columns]
            if not available_roles:
                return None

            candidates = []
            for team, team_frame in pbp_data.groupby("team_code"):
                if team not in TEAMS or TEAMS[team].get("conf") != conference:
                    continue
                names = set()
                for name_col in available_roles:
                    names.update(
                        team_frame.loc[
                            team_frame[name_col].notna()
                            & (team_frame[name_col].astype(str).str.strip() != ""), name_col
                        ].astype(str).str.strip().tolist()
                    )
                for name in names:
                    pass_rows = (
                        team_frame[team_frame["passer_player_name"].astype(str).str.strip() == name]
                        if "passer_player_name" in team_frame.columns else team_frame.iloc[0:0]
                    )
                    rush_rows = (
                        team_frame[team_frame["rusher_player_name"].astype(str).str.strip() == name]
                        if "rusher_player_name" in team_frame.columns else team_frame.iloc[0:0]
                    )
                    receive_rows = (
                        team_frame[team_frame["receiver_player_name"].astype(str).str.strip() == name]
                        if "receiver_player_name" in team_frame.columns else team_frame.iloc[0:0]
                    )

                    pass_yards = numeric_sum(pass_rows, "passing_yards")
                    pass_tds = event_sum(pass_rows, ("passing_tds", "pass_touchdown"))
                    completions = event_sum(pass_rows, ("complete_pass",))
                    attempts = event_sum(pass_rows, ("pass_attempt",))
                    rush_yards = numeric_sum(rush_rows, "rushing_yards")
                    rush_attempts = event_sum(rush_rows, ("rush_attempt",))
                    rush_tds = event_sum(rush_rows, ("rushing_tds", "rush_touchdown"))
                    catches = event_sum(receive_rows, ("complete_pass",))
                    receiving_yards = numeric_sum(receive_rows, "receiving_yards")
                    receiving_tds = event_sum(receive_rows, ("receiving_tds", "pass_touchdown"))

                    if position == "QB":
                        volume = attempts
                        score = pass_yards / 25 + pass_tds * 7 + rush_yards / 15 + rush_tds * 7 + completions * .10
                        stat_line = (
                            f"{completions:.0f}/{attempts:.0f} · {pass_yards:,.0f} pass yds · "
                            f"{pass_tds:.0f} pass TD · {rush_yards:,.0f} rush yds · {rush_tds:.0f} rush TD"
                        )
                    elif position == "RB":
                        volume = rush_attempts + catches
                        score = (rush_yards + receiving_yards) / 20 + rush_tds * 7 + receiving_tds * 7 + rush_attempts * .12 + catches * .45
                        stat_line = (
                            f"{rush_attempts:.0f} carries · {rush_yards:,.0f} rush yds · {rush_tds:.0f} rush TD · "
                            f"{catches:.0f} catches · {receiving_yards:,.0f} rec yds · {receiving_tds:.0f} rec TD"
                        )
                    else:
                        volume = catches
                        score = receiving_yards / 18 + receiving_tds * 7 + catches * .55
                        stat_line = f"{catches:.0f} catches · {receiving_yards:,.0f} rec yds · {receiving_tds:.0f} rec TD"

                    # EPA is supplemental only; the award remains usable when EPA is absent.
                    relevant_rows = pass_rows if position == "QB" else rush_rows if position == "RB" else receive_rows
                    if position == "RB" and not receive_rows.empty:
                        relevant_rows = pd.concat([rush_rows, receive_rows], axis=0)
                    epa = numeric_sum(relevant_rows, "epa") if "epa" in relevant_rows.columns else 0.0
                    score += epa * 1.5
                    if volume <= 0:
                        continue
                    candidates.append({
                        "name": name, "team": team, "score": score,
                        "stat_line": stat_line, "epa": epa, "position": position,
                    })
            return max(candidates, key=lambda item: item["score"]) if candidates else None

        for conference in ("AFC", "NFC"):
            for position, label in (("QB", "QUARTERBACK"), ("RB", "RUNNING BACK"), ("WR", "RECEIVER")):
                best = top_player(position, conference)
                if best:
                    foot = f"{team_name(best['team'])} · production-based selection"
                    if "epa" in pbp_data.columns:
                        foot += f" · EPA {best['epa']:+.1f}"
                    award_results[conference].append(card_shell(
                        f"{conference} {label} OF THE WEEK", best["name"], best["stat_line"],
                        team_logo(best["team"], 54), TEAMS[best["team"]]["color"], foot,
                    ))
                else:
                    award_results[conference].append(card_shell(
                        f"{conference} {label} OF THE WEEK", "Not available",
                        "No qualifying player-level statistics were found for this week.",
                        '<div class="versus">—</div>', "#7B8794",
                    ))
    else:
        for conference in ("AFC", "NFC"):
            for label in ("QUARTERBACK", "RUNNING BACK", "RECEIVER"):
                award_results[conference].append(card_shell(
                    f"{conference} {label} OF THE WEEK", "Not available",
                    "Weekly play-by-play data is missing for this season.",
                    '<div class="versus">—</div>', "#7B8794",
                ))

    st.markdown('<div class="weekly-outcome-title" style="color:#9ec8f0;margin-top:12px">AFC HONORS</div>', unsafe_allow_html=True)
    st.markdown('<div class="weekly-feature-grid awards">' + ''.join(award_results["AFC"]) + '</div>', unsafe_allow_html=True)
    st.markdown('<div class="weekly-outcome-title" style="color:#f0b6a0;margin-top:18px">NFC HONORS</div>', unsafe_allow_html=True)
    st.markdown('<div class="weekly-feature-grid awards">' + ''.join(award_results["NFC"]) + '</div>', unsafe_allow_html=True)

    # Existing matchup-by-matchup breakdown is intentionally preserved at the bottom.
    section(f"WEEK {selected_week} — GAME BREAKDOWNS")
    if not games:
        st.info("There are no completed games recorded for this week.")
    else:
        for game, home_score, away_score in games:
            home, away = str(game.get("home")).upper(), str(game.get("away")).upper()
            home_name, away_name = team_name(home), team_name(away)
            margin = abs(home_score - away_score)
            winner = home if home_score > away_score else away if away_score > home_score else None
            winner_name = team_name(winner) if winner else "TIE"
            with st.expander(f"{away_name} {away_score}  —  {home_score} {home_name}  ·  {winner_name}", expanded=True):
                top = st.columns([2, 1, 2])
                with top[0]:
                    st.markdown(team_logo(away, 76), unsafe_allow_html=True)
                    st.markdown(f"### {away_name}")
                    st.markdown(f"## {away_score}")
                with top[1]:
                    st.markdown("### FINAL")
                    st.caption(f"{margin}-point margin")
                with top[2]:
                    st.markdown(team_logo(home, 76), unsafe_allow_html=True)
                    st.markdown(f"### {home_name}")
                    st.markdown(f"## {home_score}")

                away_stats = get_team_week_row(away, selected_week, stats) if stats_ready else None
                home_stats = get_team_week_row(home, selected_week, stats) if stats_ready else None
                if away_stats and home_stats:
                    metric_rows = [
                        ("Passing yards", "passing_yards"), ("Rushing yards", "rushing_yards"),
                        ("Receiving yards", "receiving_yards"), ("Sacks recorded", "def_sacks"),
                        ("Interceptions", "def_interceptions"), ("Forced fumbles", "def_fumbles_forced"),
                        ("Tackles for loss", "def_tackles_for_loss"),
                    ]
                    table = []
                    for label, column in metric_rows:
                        if column not in away_stats or column not in home_stats:
                            continue
                        av, hv = pd.to_numeric(away_stats[column], errors="coerce"), pd.to_numeric(home_stats[column], errors="coerce")
                        if pd.notna(av) and pd.notna(hv):
                            table.append({"Statistic": label, away_name: f"{float(av):,.0f}", home_name: f"{float(hv):,.0f}"})
                    if table:
                        st.dataframe(pd.DataFrame(table), use_container_width=True, hide_index=True)
                    else:
                        st.caption("The cached weekly file does not contain the expected box-score fields for this game.")
                else:
                    st.info("Verified final score is available. Detailed team statistics are not available for this matchup in the cached weekly statistics file.")
                if winner:
                    st.markdown(f"**Game read:** {winner_name} finished with a {margin}-point win. The score is verified from the saved game results.")
                else:
                    st.markdown("**Game read:** The teams finished level on the scoreboard.")

    st.caption("Game results come from the saved schedule/results feed. Winners and losers use standings through the selected week plus game impact and draft-position context. Distinctions use verified scores and current ratings. Player awards use cached weekly play-by-play; team awards and game breakdowns use cached weekly team statistics. Missing fields are not guessed.")


# ============================================================
