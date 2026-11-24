"""
Weekly insights for the NFL Ratings site (no Streamlit dependency).

1. top_weekly_winners()   - the most CONSEQUENTIAL wins of a week (History page)
2. build_distinctions()   - consolidated Weekly Distinctions (Report page)
3. render_*_html()        - graphical HTML for both sections

"Most consequential" is NOT the biggest margin. Each win is scored on:
  * playoff positioning  (entering the field, seed climbs, taking a division
                          lead, knocking a team out of the field)  up to ~48
  * upset size           (current ratings gap, loser rated higher)  up to 25
  * division / conference game                                       10 / 4
  * quality of opponent  (opponent's record before the game)         up to 8
  * season outlook       (win streaks, snapped losing streaks,
                          back to .500)                              up to 5
  * margin of victory    (small tie-breaker, capped at 21 pts)       up to 5
Playoff-positioning points are phased in over weeks 4-10, because standings
in the first few weeks say very little about the playoff race.
"""

import html as _html
from collections import defaultdict

import pandas as pd

try:
    from tiebreakers import SeedingContext
except ImportError:  # pragma: no cover
    from Website.tiebreakers import SeedingContext


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def normalize_games(results):
    """Raw result dicts -> [{week, home, away, hs, as}] for games with scores."""
    games = []
    for game in results or []:
        try:
            games.append({
                "week": int(game["week"]),
                "home": game["home"],
                "away": game["away"],
                "hs": int(game["home_score"]),
                "as": int(game["away_score"]),
            })
        except (KeyError, TypeError, ValueError):
            continue
    return games


def _norm(code):
    code = str(code).upper()
    return {"LA": "LAR"}.get(code, code)


def _esc(value):
    return _html.escape(str(value), quote=True)


def _name(teams, code):
    return teams.get(code, {}).get("name", code)


def _color(teams, code, default="#B99A5A"):
    return teams.get(code, {}).get("color", default)


def _logo(teams, code, size=64):
    info = teams.get(code, {})
    url = info.get("logo")
    if url:
        return (
            f'<img class="wk-logo" src="{_esc(url)}" alt="{_esc(info.get("name", code))}" '
            f'style="width:{size}px;height:{size}px">'
        )
    return (
        f'<div class="wk-logo wk-logo-fallback" style="width:{size}px;height:{size}px;'
        f'line-height:{size}px;background:{_esc(_color(teams, code))}">{_esc(code)}</div>'
    )


def _record_text(w, l, t):
    return f"{w}-{l}" + (f"-{t}" if t else "")


def _team_results(games, code, before_week=None, upto_week=None):
    """Chronological [(week, opp, pf, pa)] for a team."""
    rows = []
    for g in games:
        if before_week is not None and g["week"] >= before_week:
            continue
        if upto_week is not None and g["week"] > upto_week:
            continue
        if g["home"] == code:
            rows.append((g["week"], g["away"], g["hs"], g["as"]))
        elif g["away"] == code:
            rows.append((g["week"], g["home"], g["as"], g["hs"]))
    rows.sort(key=lambda r: r[0])
    return rows


def _wlt(rows):
    w = sum(1 for _, _, pf, pa in rows if pf > pa)
    l = sum(1 for _, _, pf, pa in rows if pf < pa)
    t = sum(1 for _, _, pf, pa in rows if pf == pa)
    return w, l, t


def _streak(rows):
    """Current streak at the end of the rows: ('W'|'L'|'T'|None, length)."""
    kind, length = None, 0
    for _, _, pf, pa in reversed(rows):
        result = "W" if pf > pa else "L" if pf < pa else "T"
        if kind is None:
            kind = result
        if result != kind:
            break
        length += 1
    return kind, length


def conference_positions(games, teams, upto_week):
    """Playoff-order position (1-16 per conference) using the real tiebreakers."""
    ctx = SeedingContext(
        [
            {"home": g["home"], "away": g["away"],
             "home_score": g["hs"], "away_score": g["as"]}
            for g in games if g["week"] <= upto_week
        ],
        teams,
    )
    positions = {}
    for conference in ("AFC", "NFC"):
        division_seeds, ranked_rest = ctx.seed_conference(conference)
        order = [code for code, _ in division_seeds] + [code for code, _ in ranked_rest]
        for index, code in enumerate(order, start=1):
            positions[code] = {
                "pos": index,
                "in_field": index <= 7,
                "div_leader": index <= 4,
            }
    return positions


# ---------------------------------------------------------------------------
# 1. MOST CONSEQUENTIAL WINNERS
# ---------------------------------------------------------------------------

def top_weekly_winners(results, teams, week, rating_by_team=None, top_n=3):
    rating_by_team = rating_by_team or {}
    games = normalize_games(results)
    week_games = [g for g in games if g["week"] == week and g["hs"] != g["as"]]
    if not week_games:
        return []

    before = conference_positions(games, teams, week - 1)
    after = conference_positions(games, teams, week)
    progress = min(1.0, max(0.0, (week - 3) / 7))

    scored = []
    for g in week_games:
        home_won = g["hs"] > g["as"]
        winner = g["home"] if home_won else g["away"]
        loser = g["away"] if home_won else g["home"]
        if winner not in teams or loser not in teams:
            continue

        win_score, lose_score = (g["hs"], g["as"]) if home_won else (g["as"], g["hs"])
        margin = win_score - lose_score
        reasons = []  # (points, text)

        # --- playoff positioning ---------------------------------------
        pb, pa = before[winner], after[winner]
        playoff_pts = 0.0
        if not pb["in_field"] and pa["in_field"]:
            playoff_pts += 25
            reasons.append((25 * progress, f"Moved into the playoff field as the #{pa['pos']} seed"))
        elif pa["pos"] < pb["pos"]:
            climbed = pb["pos"] - pa["pos"]
            if pa["in_field"]:
                bump = min(12, 3 * climbed)
                reasons.append((bump * progress, f"Climbed to the #{pa['pos']} seed"))
            else:
                bump = min(6, climbed)
                reasons.append((bump * progress, "Closed in on the playoff field"))
            playoff_pts += bump
        if not pb["div_leader"] and pa["div_leader"]:
            playoff_pts += 15
            reasons.append((15 * progress, "Took over the division lead"))
        playoff_pts *= progress

        knock_pts = 0.0
        if before[loser]["in_field"] and not after[loser]["in_field"]:
            knock_pts = 8 * progress
            reasons.append((knock_pts, f"Knocked {_name(teams, loser)} out of the playoff field"))

        # --- upset ------------------------------------------------------
        upset_pts = 0.0
        rating_w, rating_l = rating_by_team.get(winner), rating_by_team.get(loser)
        if rating_w is not None and rating_l is not None:
            gap = rating_l - rating_w
            if gap > 0:
                upset_pts = min(1.0, gap / 15.0) * 25
                if gap >= 3:
                    reasons.append((upset_pts, f"Upset a team rated {gap:.0f} points higher"))

        # --- division / conference -------------------------------------
        same_conf = teams[winner].get("conf") == teams[loser].get("conf")
        same_div = same_conf and teams[winner].get("div") == teams[loser].get("div")
        context_pts = 0.0
        if same_div:
            context_pts = 10
            reasons.append((10, "Division win"))
        elif same_conf:
            context_pts = 4
            reasons.append((4, "Conference win"))

        # --- opponent quality ------------------------------------------
        quality_pts = 0.0
        opp_rows = _team_results(games, loser, before_week=week)
        ow, ol, ot = _wlt(opp_rows)
        if len(opp_rows) >= 3:
            opp_pct = (ow + 0.5 * ot) / len(opp_rows)
            quality_pts = 8 * opp_pct
            if opp_pct >= 0.6:
                reasons.append((quality_pts, f"Beat a {_record_text(ow, ol, ot)} team"))

        # --- season outlook ---------------------------------------------
        outlook_pts = 0.0
        prior = _team_results(games, winner, before_week=week)
        kind, length = _streak(prior)
        if kind == "L" and length >= 3:
            outlook_pts += 5
            reasons.append((5, f"Snapped a {length}-game losing streak"))
        elif kind == "L" and length == 2:
            outlook_pts += 2
            reasons.append((2, "Snapped a two-game skid"))
        elif kind == "W" and length >= 2:
            new_len = length + 1
            bonus = min(5, new_len)
            outlook_pts += bonus
            reasons.append((bonus, f"Won {new_len} straight"))
        pw, pl_, pt = _wlt(prior)
        if len(prior) >= 4 and pw < pl_ and (pw + 1) == pl_:
            outlook_pts += 2
            reasons.append((2, "Pulled back to .500"))

        # --- margin -------------------------------------------------------
        margin_pts = min(margin, 21) / 21 * 5
        if margin >= 17:
            reasons.append((margin_pts, f"Dominant {margin}-point win"))

        total = (playoff_pts + knock_pts + upset_pts + context_pts
                 + quality_pts + outlook_pts + margin_pts)

        after_rows = _team_results(games, winner, upto_week=week)
        aw, al, at = _wlt(after_rows)

        reasons = [item for item in reasons if item[0] > 0.5]
        reasons.sort(key=lambda item: item[0], reverse=True)
        scored.append({
            "team": winner,
            "opponent": loser,
            "team_score": win_score,
            "opp_score": lose_score,
            "home": home_won,
            "margin": margin,
            "score": round(total, 1),
            "reasons": [text for _, text in reasons[:3]],
            "record_after": _record_text(aw, al, at),
            "seed_after": pa["pos"] if pa["in_field"] else None,
            "seed_before": pb["pos"] if pb["in_field"] else None,
        })

    scored.sort(key=lambda item: (-item["score"], -item["margin"], item["team"]))
    return scored[:top_n]


# ---------------------------------------------------------------------------
# 2. WEEKLY DISTINCTIONS
# ---------------------------------------------------------------------------

def build_weekly_team_table(stats, week, week_games):
    """One row per team that played: scoring + yardage for and against."""
    if stats is None or stats.empty or not {"team", "week"}.issubset(stats.columns):
        return pd.DataFrame()

    week_stats = stats[pd.to_numeric(stats["week"], errors="coerce") == int(week)].copy()
    if week_stats.empty:
        return pd.DataFrame()

    week_stats["team_code"] = week_stats["team"].map(_norm)
    points_for, points_against, opponent = {}, {}, {}
    for g in week_games:
        home, away = _norm(g["home"]), _norm(g["away"])
        points_for[home], points_for[away] = g["hs"], g["as"]
        points_against[home], points_against[away] = g["as"], g["hs"]
        opponent[home], opponent[away] = away, home

    week_stats = week_stats[week_stats["team_code"].isin(opponent)].drop_duplicates("team_code")
    week_stats = week_stats.set_index("team_code", drop=False)

    def col(name):
        if name in week_stats.columns:
            return pd.to_numeric(week_stats[name], errors="coerce")
        return pd.Series(float("nan"), index=week_stats.index)

    table = pd.DataFrame(index=week_stats.index)
    table["team"] = week_stats["team_code"]
    table["points_scored"] = [points_for.get(c) for c in table.index]
    table["points_allowed"] = [points_against.get(c) for c in table.index]
    table["passing_yards"] = col("passing_yards")
    table["rushing_yards"] = col("rushing_yards")
    table["passing_yards_allowed"] = [
        col("passing_yards").get(opponent.get(c)) for c in table.index
    ]
    table["rushing_yards_allowed"] = [
        col("rushing_yards").get(opponent.get(c)) for c in table.index
    ]
    table["def_sacks"] = col("def_sacks")
    table["def_interceptions"] = col("def_interceptions")
    table["def_fumbles_forced"] = col("def_fumbles_forced")
    for column in table.columns:
        if column != "team":
            table[column] = pd.to_numeric(table[column], errors="coerce")
    return table


def _rank_performances(table, specs, tie_break):
    """specs: [(label, column, ascending)] -> top teams by average rank (lowest wins)."""
    needed = [column for _, column, _ in specs]
    frame = table.dropna(subset=needed).copy()
    if frame.empty:
        return []
    count = len(frame)
    rank_columns = []
    for _, column, ascending in specs:
        name = f"rank_{column}"
        frame[name] = frame[column].rank(ascending=ascending, method="min")
        rank_columns.append(name)
    frame["avg_rank"] = frame[rank_columns].mean(axis=1)
    sort_cols = ["avg_rank"] + [c for c, _ in tie_break]
    sort_asc = [True] + [a for _, a in tie_break]
    frame = frame.sort_values(sort_cols, ascending=sort_asc)

    top = []
    for code, row in frame.head(3).iterrows():
        top.append({
            "team": code,
            "avg_rank": float(row["avg_rank"]),
            "count": count,
            "parts": [
                {"label": label, "value": float(row[column]), "rank": int(row[f"rank_{column}"])}
                for label, column, _ in specs
            ],
        })
    return top


LEADER_SPECS = [
    # (label, column, high_is_leader, unit)
    ("MOST POINTS", "points_scored", True, "pts"),
    ("MOST PASSING YARDS", "passing_yards", True, "yds"),
    ("MOST RUSHING YARDS", "rushing_yards", True, "yds"),
    ("FEWEST POINTS ALLOWED", "points_allowed", False, "pts"),
    ("MOST SACKS", "def_sacks", True, "sacks"),
    ("MOST INTERCEPTIONS", "def_interceptions", True, "INT"),
    ("MOST FORCED FUMBLES", "def_fumbles_forced", True, "FF"),
]


def _leaders(table):
    cards = []
    for label, column, high, unit in LEADER_SPECS:
        if column not in table.columns:
            continue
        values = table[column].dropna()
        if values.empty:
            continue
        target = values.max() if high else values.min()
        winners = table[table[column] == target]["team"].tolist()
        cards.append({
            "label": label, "unit": unit, "high": high,
            "value": float(target), "average": float(values.mean()),
            "teams": winners,
        })
    return cards


def build_distinctions(stats, results, teams, week, rating_by_team=None):
    rating_by_team = rating_by_team or {}
    games = [g for g in normalize_games(results) if g["week"] == week]

    out = {
        "week": week, "games": len(games),
        "offense": [], "defense": [], "leaders": [],
        "blowout": None, "upset": None,
    }

    table = build_weekly_team_table(stats, week, games)
    if not table.empty:
        out["offense"] = _rank_performances(
            table,
            [("POINTS", "points_scored", False),
             ("PASS YDS", "passing_yards", False),
             ("RUSH YDS", "rushing_yards", False)],
            tie_break=[("points_scored", False)],
        )
        out["defense"] = _rank_performances(
            table,
            [("PTS ALLOWED", "points_allowed", True),
             ("PASS YDS ALLOWED", "passing_yards_allowed", True),
             ("RUSH YDS ALLOWED", "rushing_yards_allowed", True)],
            tie_break=[("points_allowed", True)],
        )
        out["leaders"] = _leaders(table)

    decided = [g for g in games if g["hs"] != g["as"]]
    if decided:
        big = max(decided, key=lambda g: abs(g["hs"] - g["as"]))
        out["blowout"] = {
            "home": big["home"], "away": big["away"],
            "home_score": big["hs"], "away_score": big["as"],
            "margin": abs(big["hs"] - big["as"]),
        }

        best = None
        for g in decided:
            home_won = g["hs"] > g["as"]
            winner = g["home"] if home_won else g["away"]
            loser = g["away"] if home_won else g["home"]
            rw, rl = rating_by_team.get(winner), rating_by_team.get(loser)
            if rw is None or rl is None or rl - rw <= 0:
                continue
            if best is None or rl - rw > best["gap"]:
                best = {
                    "winner": winner, "loser": loser, "gap": rl - rw,
                    "winner_score": g["hs"] if home_won else g["as"],
                    "loser_score": g["as"] if home_won else g["hs"],
                }
        out["upset"] = best
    return out


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

CSS = """
<style>
.wk-wrap{font-family:'Rajdhani',sans-serif;color:#F2EDE0;margin:6px 0 18px}
.wk-h{font-family:'Barlow Condensed',sans-serif;font-weight:900;letter-spacing:2px;
 font-size:24px;color:#D8B86D;margin:22px 0 10px;text-transform:uppercase}
.wk-grid{display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(270px,1fr))}
.wk-grid-sm{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(230px,1fr))}
.wk-card{position:relative;overflow:hidden;background:linear-gradient(145deg,#201F1B,#111110);
 border:1px solid rgba(185,154,90,.35);border-top:4px solid var(--c,#B99A5A);padding:16px}
.wk-hero{background:linear-gradient(135deg,color-mix(in srgb,var(--c,#B99A5A) 38%,#111110),#111110 62%)}
.wk-logo{object-fit:contain;filter:drop-shadow(0 5px 9px #0009);flex:0 0 auto}
.wk-logo-fallback{border-radius:50%;text-align:center;font-weight:900;color:#fff;font-size:15px}
.wk-row{display:flex;align-items:center;gap:14px}
.wk-badge{position:absolute;top:8px;right:12px;font-family:'Barlow Condensed',sans-serif;
 font-weight:900;font-size:54px;line-height:1;color:#ffffff1c}
.wk-kicker{font-weight:700;letter-spacing:3px;font-size:13px;color:#B99A5A;text-transform:uppercase}
.wk-name{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:27px;line-height:1.05;
 text-transform:uppercase}
.wk-sub{font-size:16px;color:#C9C1B1;font-weight:600}
.wk-big{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:44px;line-height:1;color:#F2EDE0}
.wk-big small{font-size:16px;color:#C9C1B1;letter-spacing:1px;margin-left:4px}
.wk-meter{display:flex;justify-content:space-between;font-weight:700;letter-spacing:2px;
 font-size:13px;color:#B99A5A;margin:14px 0 5px}
.wk-meter b{color:#F2EDE0;font-size:16px}
.wk-bar{height:8px;background:#ffffff14;border-radius:4px;overflow:hidden}
.wk-bar i{display:block;height:100%;border-radius:4px;background:linear-gradient(90deg,var(--c,#B99A5A),#D8B86D)}
.wk-bar-dim i{background:#ffffff38}
.wk-chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:12px}
.wk-chip{font-size:14px;font-weight:700;padding:3px 9px;border:1px solid rgba(216,184,109,.5);
 background:#ffffff0d;color:#F2EDE0}
.wk-parts{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:14px}
.wk-part{background:#ffffff0a;padding:8px 9px}
.wk-part .l{font-size:11px;letter-spacing:1.5px;color:#B99A5A;font-weight:700}
.wk-part .v{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:25px;line-height:1.1}
.wk-part .r{font-size:13px;color:#D8B86D;font-weight:700;margin-bottom:5px}
.wk-runner{display:flex;align-items:center;gap:10px;margin-top:10px;padding-top:10px;
 border-top:1px solid #ffffff14;font-size:17px;font-weight:600}
.wk-runner span.n{margin-left:auto;color:#D8B86D;font-weight:800}
.wk-vs{display:flex;align-items:center;justify-content:center;gap:16px;flex-wrap:wrap}
.wk-score{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:46px;line-height:1}
.wk-mid{text-align:center}
.wk-note{font-size:14px;color:#9d9585;margin-top:8px}
.wk-twin{display:flex;gap:6px;align-items:center}
.wk-lbl{display:flex;justify-content:space-between;font-size:12px;letter-spacing:1px;
 font-weight:700;color:#C9C1B1;margin:8px 0 3px}
</style>
"""


def _bar(pct, dim=False):
    pct = max(0, min(100, pct))
    return f'<div class="wk-bar{" wk-bar-dim" if dim else ""}"><i style="width:{pct:.0f}%"></i></div>'


def render_winners_html(winners, teams, week):
    cards = []
    for index, win in enumerate(winners, start=1):
        code, opp = win["team"], win["opponent"]
        site = "vs" if win["home"] else "at"
        chips = "".join(f'<span class="wk-chip">{_esc(r)}</span>' for r in win["reasons"])
        if not chips:
            chips = f'<span class="wk-chip">Won by {win["margin"]}</span>'
        seed_txt = ""
        if win["seed_after"]:
            seed_txt = f' · #{win["seed_after"]} seed'
        impact = min(100, win["score"])
        cards.append(
            f'<div class="wk-card wk-hero" style="--c:{_esc(_color(teams, code))}">'
            f'<div class="wk-badge">#{index}</div>'
            f'<div class="wk-row">{_logo(teams, code, 84)}'
            f'<div><div class="wk-kicker">Week {week} winner</div>'
            f'<div class="wk-name">{_esc(_name(teams, code))}</div>'
            f'<div class="wk-sub">W {win["team_score"]}–{win["opp_score"]} {site} '
            f'{_esc(_name(teams, opp))}</div>'
            f'<div class="wk-sub">Now {_esc(win["record_after"])}{_esc(seed_txt)}</div>'
            f'</div></div>'
            f'<div class="wk-meter"><span>WEEK IMPACT</span><b>{impact:.0f}</b></div>'
            f'{_bar(impact)}'
            f'<div class="wk-chips">{chips}</div>'
            f'</div>'
        )
    return (
        CSS + '<div class="wk-wrap"><div class="wk-grid">' + "".join(cards) + "</div>"
        '<div class="wk-note">Ranked by impact, not margin: playoff positioning, upsets, '
        'division/conference stakes, opponent quality, and season outlook. '
        'Upset size uses the current ratings, not pregame odds.</div></div>'
    )


def _performance_card(teams, entry, title, week):
    code = entry["team"]
    parts = "".join(
        f'<div class="wk-part"><div class="l">{_esc(p["label"])}</div>'
        f'<div class="v">{p["value"]:,.0f}</div>'
        f'<div class="r">#{p["rank"]} of {entry["count"]}</div>'
        f'{_bar((entry["count"] - p["rank"] + 1) / entry["count"] * 100)}</div>'
        for p in entry["parts"]
    )
    return (
        f'<div class="wk-card wk-hero" style="--c:{_esc(_color(teams, code))}">'
        f'<div class="wk-row">{_logo(teams, code, 84)}'
        f'<div><div class="wk-kicker">{_esc(title)}</div>'
        f'<div class="wk-name">{_esc(_name(teams, code))}</div>'
        f'<div class="wk-big">{entry["avg_rank"]:.1f}<small>AVG RANK</small></div></div></div>'
        f'<div class="wk-parts">{parts}</div></div>'
    )


def _runner_rows(teams, entries):
    rows = []
    for place, entry in enumerate(entries[1:], start=2):
        rows.append(
            f'<div class="wk-runner"><b>#{place}</b>{_logo(teams, entry["team"], 30)}'
            f'<span>{_esc(_name(teams, entry["team"]))}</span>'
            f'<span class="n">{entry["avg_rank"]:.1f} avg</span></div>'
        )
    return "".join(rows)


def _leader_card(teams, card):
    codes = card["teams"]
    lead = codes[0]
    logos = '<div class="wk-twin">' + "".join(_logo(teams, c, 52) for c in codes[:2]) + "</div>"
    names = " / ".join(_name(teams, c) for c in codes[:3])
    if len(codes) > 3:
        names += f" +{len(codes) - 3}"
    value, avg = card["value"], card["average"]
    if card["high"]:
        lead_pct = 100
        avg_pct = (avg / value * 100) if value else 0
    else:
        lead_pct = (value / avg * 100) if avg else 0
        avg_pct = 100
    return (
        f'<div class="wk-card" style="--c:{_esc(_color(teams, lead))}">'
        f'<div class="wk-kicker">{_esc(card["label"])}</div>'
        f'<div class="wk-row" style="margin-top:8px">{logos}'
        f'<div><div class="wk-big">{value:,.0f}<small>{_esc(card["unit"])}</small></div>'
        f'<div class="wk-sub">{_esc(names)}</div></div></div>'
        f'<div class="wk-lbl"><span>LEADER</span><span>{value:,.0f}</span></div>{_bar(lead_pct)}'
        f'<div class="wk-lbl"><span>WEEK AVERAGE</span><span>{avg:,.1f}</span></div>{_bar(avg_pct, dim=True)}'
        f'</div>'
    )


def render_distinctions_html(data, teams):
    parts = [CSS, '<div class="wk-wrap">']

    if data["offense"] or data["defense"]:
        parts.append('<div class="wk-h">Best performances of the week</div><div class="wk-grid">')
        if data["offense"]:
            parts.append(
                '<div>' + _performance_card(teams, data["offense"][0], "Best offensive performance", data["week"])
                + _runner_rows(teams, data["offense"]) + "</div>"
            )
        if data["defense"]:
            parts.append(
                '<div>' + _performance_card(teams, data["defense"][0], "Best defensive performance", data["week"])
                + _runner_rows(teams, data["defense"]) + "</div>"
            )
        parts.append("</div>")
        parts.append(
            '<div class="wk-note">Offense: average rank across points scored, passing yards and rushing '
            'yards. Defense: average rank across points allowed, passing yards allowed and rushing yards '
            'allowed. Rank 1 is best; the lowest average wins.</div>'
        )

    game_cards = []
    blow = data["blowout"]
    if blow:
        game_cards.append(
            '<div class="wk-card"><div class="wk-kicker">Biggest blowout</div>'
            '<div class="wk-vs" style="margin-top:10px">'
            f'{_logo(teams, blow["away"], 60)}'
            f'<div class="wk-mid"><div class="wk-score">{blow["away_score"]} – {blow["home_score"]}</div>'
            f'<div class="wk-sub">{blow["margin"]}-point margin</div></div>'
            f'{_logo(teams, blow["home"], 60)}</div>'
            f'<div class="wk-sub" style="text-align:center;margin-top:8px">'
            f'{_esc(_name(teams, blow["away"]))} at {_esc(_name(teams, blow["home"]))}</div></div>'
        )
    up = data["upset"]
    if up:
        game_cards.append(
            f'<div class="wk-card" style="--c:{_esc(_color(teams, up["winner"]))}">'
            '<div class="wk-kicker">Biggest rating-gap upset</div>'
            '<div class="wk-vs" style="margin-top:10px">'
            f'{_logo(teams, up["winner"], 60)}'
            f'<div class="wk-mid"><div class="wk-score">{up["winner_score"]} – {up["loser_score"]}</div>'
            f'<div class="wk-sub">{up["gap"]:.1f} rating points</div></div>'
            f'{_logo(teams, up["loser"], 60)}</div>'
            f'<div class="wk-sub" style="text-align:center;margin-top:8px">'
            f'{_esc(_name(teams, up["winner"]))} beat {_esc(_name(teams, up["loser"]))}</div>'
            '<div class="wk-note" style="text-align:center">Current ratings, not pregame odds.</div></div>'
        )
    if game_cards:
        parts.append('<div class="wk-h">Game distinctions</div><div class="wk-grid">')
        parts.extend(game_cards)
        parts.append("</div>")

    if data["leaders"]:
        parts.append('<div class="wk-h">Statistical leaders</div><div class="wk-grid-sm">')
        parts.extend(_leader_card(teams, card) for card in data["leaders"])
        parts.append("</div>")

    parts.append("</div>")
    return "".join(parts)