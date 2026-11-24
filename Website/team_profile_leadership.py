"""NFL Team Profile leadership cards and explainable hot-seat ratings."""
from __future__ import annotations
import html
import json
import math
import re
import urllib.request
from datetime import datetime, timezone
import streamlit as st

ESPN_TEAM_IDS = {
    "ARI":22,"ATL":1,"BAL":33,"BUF":2,"CAR":29,"CHI":3,"CIN":4,"CLE":5,
    "DAL":6,"DEN":7,"DET":8,"GB":9,"HOU":34,"IND":11,"JAX":30,"KC":12,
    "LV":13,"LAC":24,"LAR":14,"MIA":15,"MIN":16,"NE":17,"NO":18,"NYG":19,
    "NYJ":20,"PHI":21,"PIT":23,"SEA":26,"SF":25,"TB":27,"TEN":10,"WAS":28
}

# Season-opening 2026 personnel baseline; live staff feed supersedes these names.
# This is a fallback only and is intentionally not presented as live-verified.
STAFF_FALLBACK_2026 = {
    "ARI": {"head_coach":"Mike LaFleur","offensive_coordinator":"Nathaniel Hackett","defensive_coordinator":"Nick Rallis","general_manager":"Monti Ossenfort"},
    "ATL": {"head_coach":"Kevin Stefanski","offensive_coordinator":"Tommy Rees","defensive_coordinator":"Jeff Ulbrich","general_manager":"Ian Cunningham"},
    "BAL": {"head_coach":"Jesse Minter","offensive_coordinator":"Declan Doyle","defensive_coordinator":"Anthony Weaver","general_manager":"Eric DeCosta"},
    "BUF": {"head_coach":"Joe Brady","offensive_coordinator":"Pete Carmichael Jr.","defensive_coordinator":"Jim Leonhard","general_manager":"Brandon Beane"},
    "CAR": {"head_coach":"Dave Canales","offensive_coordinator":"Brad Idzik","defensive_coordinator":"Ejiro Evero","general_manager":"Dan Morgan"},
    "CHI": {"head_coach":"Ben Johnson","offensive_coordinator":"Press Taylor","defensive_coordinator":"Dennis Allen","general_manager":"Ryan Poles"},
    "CIN": {"head_coach":"Zac Taylor","offensive_coordinator":"Dan Pitcher","defensive_coordinator":"Al Golden","general_manager":"Duke Tobin"},
    "CLE": {"head_coach":"Todd Monken","offensive_coordinator":"Travis Switzer","defensive_coordinator":"Mike Rutenberg","general_manager":"Andrew Berry"},
    "DAL": {"head_coach":"Brian Schottenheimer","offensive_coordinator":"Klayton Adams","defensive_coordinator":"Christian Parker","general_manager":"Jerry Jones"},
    "DEN": {"head_coach":"Sean Payton","offensive_coordinator":"Davis Webb","defensive_coordinator":"Vance Joseph","general_manager":"George Paton"},
    "DET": {"head_coach":"Dan Campbell","offensive_coordinator":"Drew Petzing","defensive_coordinator":"Kelvin Sheppard","general_manager":"Brad Holmes"},
    "GB": {"head_coach":"Matt LaFleur","offensive_coordinator":"Adam Stenavich","defensive_coordinator":"Jonathan Gannon","general_manager":"Brian Gutekunst"},
    "HOU": {"head_coach":"DeMeco Ryans","offensive_coordinator":"Nick Caley","defensive_coordinator":"Matt Burke","general_manager":"Nick Caserio"},
    "IND": {"head_coach":"Shane Steichen","offensive_coordinator":"Jim Bob Cooter","defensive_coordinator":"Lou Anarumo","general_manager":"Chris Ballard"},
    "JAX": {"head_coach":"Liam Coen","offensive_coordinator":"Grant Udinski","defensive_coordinator":"Anthony Campanile","general_manager":"James Gladstone"},
    "KC": {"head_coach":"Andy Reid","offensive_coordinator":"Eric Bieniemy","defensive_coordinator":"Steve Spagnuolo","general_manager":"Brett Veach"},
    "LAC": {"head_coach":"Jim Harbaugh","offensive_coordinator":"Mike McDaniel","defensive_coordinator":"Chris O'Leary","general_manager":"Joe Hortiz"},
    "LAR": {"head_coach":"Sean McVay","offensive_coordinator":"Nate Scheelhaase","defensive_coordinator":"Chris Shula","general_manager":"Les Snead"},
    "LV": {"head_coach":"Klint Kubiak","offensive_coordinator":"Andrew Janocko","defensive_coordinator":"Rob Leonard","general_manager":"John Spytek"},
    "MIA": {"head_coach":"Jeff Hafley","offensive_coordinator":"Bobby Slowik","defensive_coordinator":"Sean Duggan","general_manager":"Jon-Eric Sullivan"},
    "MIN": {"head_coach":"Kevin O'Connell","offensive_coordinator":"Wes Phillips","defensive_coordinator":"Brian Flores"},
    "NE": {"head_coach":"Mike Vrabel","offensive_coordinator":"Josh McDaniels","defensive_coordinator":"Zak Kuhr","general_manager":"Eliot Wolf"},
    "NO": {"head_coach":"Kellen Moore","offensive_coordinator":"Doug Nussmeier","defensive_coordinator":"Brandon Staley","general_manager":"Mickey Loomis"},
    "NYG": {"head_coach":"John Harbaugh","offensive_coordinator":"Matt Nagy","defensive_coordinator":"Dennard Wilson","general_manager":"Joe Schoen"},
    "NYJ": {"head_coach":"Aaron Glenn","offensive_coordinator":"Frank Reich","defensive_coordinator":"Brian Duker","general_manager":"Darren Mougey"},
    "PHI": {"head_coach":"Nick Sirianni","offensive_coordinator":"Sean Mannion","defensive_coordinator":"Vic Fangio","general_manager":"Howie Roseman"},
    "PIT": {"head_coach":"Mike McCarthy","offensive_coordinator":"Brian Angelichio","defensive_coordinator":"Patrick Graham","general_manager":"Omar Khan"},
    "SEA": {"head_coach":"Mike Macdonald","offensive_coordinator":"Brian Fleury","defensive_coordinator":"Aden Durde","general_manager":"John Schneider"},
    "SF": {"head_coach":"Kyle Shanahan","offensive_coordinator":"Klay Kubiak","defensive_coordinator":"Raheem Morris","general_manager":"John Lynch"},
    "TB": {"head_coach":"Todd Bowles","offensive_coordinator":"Zac Robinson","defensive_coordinator":"Todd Bowles","general_manager":"Jason Licht"},
    "TEN": {"head_coach":"Robert Saleh","offensive_coordinator":"Brian Daboll","defensive_coordinator":"Gus Bradley","general_manager":"Mike Borgonzi"},
    "WAS": {"head_coach":"Dan Quinn","offensive_coordinator":"David Blough","defensive_coordinator":"Daronte Jones","general_manager":"Adam Peters"},
}

OWNER_FALLBACK_2026 = {
    "ARI":"Michael Bidwill", "ATL":"Arthur Blank", "BAL":"Steve Bisciotti",
    "BUF":"Terry and Kim Pegula", "CAR":"David Tepper", "CHI":"George McCaskey",
    "CIN":"Mike Brown", "CLE":"Dee and Jimmy Haslam", "DAL":"Jerry Jones",
    "DEN":"Rob Walton", "DET":"Sheila Ford Hamp", "GB":"Green Bay Packers, Inc.",
    "HOU":"Cal McNair", "IND":"Carlie Irsay-Gordon", "JAX":"Shahid Khan", "JAC":"Shahid Khan",
    "KC":"Clark Hunt", "LAC":"Dean Spanos", "LAR":"Stan Kroenke",
    "LV":"Mark and Carol Davis", "MIA":"Stephen Ross", "MIN":"Zygi Wilf",
    "NE":"Robert Kraft", "NO":"Gayle Benson", "NYG":"John Mara and Steve Tisch",
    "NYJ":"Woody Johnson", "PHI":"Jeffrey Lurie", "PIT":"Art Rooney II",
    "SF":"Denise DeBartolo York and John York", "SEA":"Neera Khosla",
    "TB":"The Glazer family", "TEN":"Amy Adams Strunk", "WAS":"Josh Harris",
}

ROLE_LABELS = {
    "owner": "OWNER", "general_manager": "GENERAL MANAGER", "head_coach": "HEAD COACH",
    "offensive_coordinator": "OFFENSIVE COORDINATOR", "defensive_coordinator": "DEFENSIVE COORDINATOR"
}


def _number(value, default=None):
    """Convert ordinary values and pandas scalars to a finite float."""
    try:
        result = float(value)
        return result if math.isfinite(result) else default
    except (TypeError, ValueError):
        return default


def _coaching_side(person: dict) -> str | None:
    """Return offense/defense only when staff metadata or bio supports it."""
    person = person or {}
    explicit = str(person.get("side") or person.get("side_of_ball")
                   or person.get("specialty") or person.get("unit") or "").lower()
    if any(word in explicit for word in ("offen", "quarterback", "passing game")):
        return "offense"
    if any(word in explicit for word in ("defen", "lineback", "secondary")):
        return "defense"
    bio = " ".join(str(person.get(k) or "") for k in
                   ("bio", "description", "experience", "title")).lower()
    offense_terms = ("offensive coordinator", "offensive assistant", "quarterback",
                     "passing game", "wide receiver", "running back", "offensive line",
                     "offensive coach", "play caller")
    defense_terms = ("defensive coordinator", "defensive assistant", "linebacker",
                     "defensive line", "defensive back", "secondary", "defensive coach")
    offense_hits = sum(bio.count(term) for term in offense_terms)
    defense_hits = sum(bio.count(term) for term in defense_terms)
    if offense_hits > defense_hits and offense_hits:
        return "offense"
    if defense_hits > offense_hits and defense_hits:
        return "defense"
    return None

@st.cache_data(ttl=86400, show_spinner=False)
def _fetch_team_staff(team_code: str) -> dict:
    """Attempt daily-refresh ESPN team personnel feed. Fail safely when unavailable."""
    team_id = ESPN_TEAM_IDS.get(team_code)
    if not team_id:
        return {}
    urls = [
        f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team_id}?enable=roster,coaches",
        f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team_id}?enable=coaches",
        f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team_id}/coaches",
    ]
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0 NFL Ratings dashboard"})
            with urllib.request.urlopen(req, timeout=7) as response:
                payload = json.loads(response.read().decode("utf-8"))
            # Normalize a few known ESPN response shapes without assuming all roles exist.
            staff = payload.get("team", payload)
            coaches = staff.get("coaches", payload.get("coaches", payload.get("coach", [])))
            if not coaches and isinstance(payload.get("team"), dict):
                coaches = payload["team"].get("coach", payload["team"].get("coaches", []))
            normalized = {}
            if isinstance(coaches, dict):
                coaches = coaches.get("items", coaches.get("coaches", []))
            if isinstance(coaches, list):
                for entry in coaches:
                    if not isinstance(entry, dict):
                        continue
                    name = entry.get("fullName") or entry.get("displayName") or entry.get("name")
                    title = str(entry.get("title") or entry.get("position") or entry.get("role") or "").lower()
                    if not name:
                        continue
                    key = None
                    if "head coach" in title or title.strip() == "hc": key = "head_coach"
                    elif "offensive coordinator" in title or title.strip() in {"oc","offense"}: key = "offensive_coordinator"
                    elif "defensive coordinator" in title or title.strip() in {"dc","defense"}: key = "defensive_coordinator"
                    elif "general manager" in title or title.strip() == "gm": key = "general_manager"
                    if key and key not in normalized:
                        headshot = entry.get("headshot")
                        image_url = (headshot.get("href") or headshot.get("url") if isinstance(headshot, dict)
                                     else headshot if isinstance(headshot, str) else None)
                        image_url = image_url or entry.get("image") or entry.get("photo")
                        if not image_url and isinstance(entry.get("images"), list) and entry["images"]:
                            first_image = entry["images"][0]
                            image_url = first_image.get("href") or first_image.get("url") if isinstance(first_image, dict) else first_image
                        if not image_url and isinstance(entry.get("links"), dict):
                            image_url = entry["links"].get("headshot", {}).get("href") if isinstance(entry["links"].get("headshot"), dict) else None
                        normalized[key] = {
                            "name": name,
                            "image": image_url,
                            "years": entry.get("yearsInRole") or entry.get("yearsInPosition"),
                            "start_date": (
                                entry.get("roleStartDate") or entry.get("startDate")
                                or entry.get("hireDate") or entry.get("dateHired")
                            ),
                            "bio": entry.get("description") or "",
                            "side": (entry.get("sideOfBall") or entry.get("side")
                                     or entry.get("specialty") or entry.get("unit")),
                            "experience": entry.get("experience") or entry.get("careerSummary") or "",
                            "title": entry.get("title") or entry.get("position") or "",
                        }
            if normalized:
                return {"staff": normalized, "source": "ESPN staff feed", "updated": datetime.now(timezone.utc).isoformat()}
        except Exception:
            continue
    return {}



def _score_result(score: float, performance: float, detail: str,
                  tenure_status: str, extra_reason: str = "") -> dict:
    score = max(0, min(100, round(score)))
    if score < 20:
        status, color = "ICE COLD", "#2E7D58"
    elif score < 40:
        status, color = "COOL", "#4D9469"
    elif score < 60:
        status, color = "WARM", "#B78A36"
    elif score < 80:
        status, color = "HOT", "#C66B35"
    else:
        status, color = "BURNING", "#B64242"

    reason = f"Performance context {performance:.0f}/100 · {detail}"
    if tenure_status == "first_year":
        reason += " · first-year curve applied"
    elif tenure_status == "unverified":
        reason += " · tenure unavailable; normal scoring used"
    if extra_reason:
        reason += f" · {extra_reason}"
    return {"score": score, "status": status, "color": color,
            "reason": reason, "tenure_status": tenure_status}


def hot_seat_score(performance: float, trend: float = 0, expectations: float = 0,
                   tenure_years: int | float | None = None,
                   success_history: float = 0) -> dict:
    """General coach/coordinator pressure model; only verified year one is curved."""
    performance = max(0.0, min(100.0, _number(performance, 50.0)))
    trend = max(-1.0, min(1.0, _number(trend, 0.0)))
    expectations = max(-1.0, min(1.0, _number(expectations, 0.0)))
    history = max(0.0, min(100.0, _number(success_history, 0.0)))

    trend_adjustment = trend * 15
    expectation_adjustment = expectations * 15
    raw_score = 90 - performance * 0.85 + trend_adjustment + expectation_adjustment - history * 0.15
    score = max(0.0, min(100.0, raw_score))
    tenure_status = "unverified"
    if tenure_years is not None:
        years = _number(tenure_years)
        if years is not None and years < 1:
            score *= 0.35 + 0.30 * (score / 100)
            tenure_status = "first_year"
        elif years is not None:
            tenure_status = "established"

    return _score_result(score, performance,
                         f"trend {trend_adjustment:+.0f}; expectations {expectation_adjustment:+.0f}",
                         tenure_status)


def gm_hot_seat_score(roster_strength: float, record_strength: float,
                      trend: float = 0, expectations: float = 0,
                      tenure_years: int | float | None = None) -> dict:
    """Patient GM model; a single-season snapshot cannot establish repeated failure."""
    roster_strength = max(0.0, min(100.0, _number(roster_strength, 50.0)))
    record_strength = max(0.0, min(100.0, _number(record_strength, 50.0)))
    trend = max(-1.0, min(1.0, _number(trend, 0.0)))
    expectations = max(-1.0, min(1.0, _number(expectations, 0.0)))

    # GM evaluation emphasizes roster quality and long-run direction over one record.
    gm_strength = 0.65 * roster_strength + 0.20 * record_strength + 0.15 * (50 + 50 * trend)
    raw_pressure = 84 - 0.78 * gm_strength + max(0.0, expectations) * 7

    # Without multi-year results, don't label a GM BURNING from one season alone.
    score = min(79.0, max(0.0, raw_pressure))
    tenure_status = "unverified"
    if tenure_years is not None:
        years = _number(tenure_years)
        if years is not None and years < 1:
            score *= 0.55
            tenure_status = "first_year"
        elif years is not None:
            tenure_status = "established"

    return _score_result(
        score, gm_strength,
        "roster quality 65%; record 20%; recent trajectory 15%",
        tenure_status,
        "single-season ceiling; multi-year organizational history not supplied"
    )


def _staff_data(team_code: str, team_info: dict | None = None) -> dict:
    team_code = str(team_code or "").upper().strip()
    team_code = {"JAC":"JAX", "LA":"LAR", "WSH":"WAS", "OAK":"LV", "SD":"LAC", "STL":"LAR"}.get(team_code, team_code)
    fetched = _fetch_team_staff(team_code)
    staff = fetched.get("staff", {}) if fetched else {}
    # Fallback personnel baseline used only when the live feed doesn't supply that role.
    fallback = STAFF_FALLBACK_2026.get(team_code, {})
    for role, name in fallback.items():
        staff.setdefault(role, {"name": name, "image": None, "years": None, "bio": "2026 baseline listing; live feed unavailable for this role.", "side": None})
    for role in ROLE_LABELS:
        staff.setdefault(role, {"name": "Personnel listing unavailable", "image": None, "years": None, "bio": "No verified source data available for this role."})
    # Owners are filled from a maintained league-wide baseline because coaching feeds omit them.
    # Important: the role-default loop above may insert a placeholder; replace that placeholder
    # rather than checking only for a missing key (the original bug that hid owner names).
    owner_entry = staff.get("owner", {})
    if not owner_entry.get("name") or owner_entry.get("name") == "Personnel listing unavailable":
        staff["owner"] = {
            "name": ((str((team_info or {}).get("owner") or (team_info or {}).get("owner_name") or "").strip() if str((team_info or {}).get("owner") or (team_info or {}).get("owner_name") or "").strip() else OWNER_FALLBACK_2026.get(team_code, OWNER_FALLBACK_2026.get({"JAX":"JAC"}.get(team_code, team_code), "Owner listing unavailable")))),
            "image": None, "years": None,
            "bio": "Owner name from the maintained ownership baseline.",
        }
    return {"staff": staff, "source": fetched.get("source", "2026 baseline fallback" if fallback else "Personnel feed unavailable"),
            "updated": fetched.get("updated")}


def _card(role: str, person: dict, team_color: str, hotseat: dict | None = None) -> str:
    """Consistent dark card with equal height, readable name, and role-specific footer."""
    name = person.get("name") or "Personnel update pending"
    safe_name = html.escape(str(name))
    role_label = ROLE_LABELS.get(role, role.replace("_", " ").upper())
    title = {
        "owner": "OWNER'S BOX", "general_manager": "FRONT OFFICE",
        "head_coach": "ON THE SIDELINE", "offensive_coordinator": "OFFENSE",
        "defensive_coordinator": "DEFENSE",
    }.get(role, "TEAM STAFF")
    footer_copy = {
        "owner": "The big-picture direction and investment behind the franchise.",
        "general_manager": "Building the roster and shaping the team's future.",
        "head_coach": "Setting the tone, culture, and game-day decisions.",
        "offensive_coordinator": "Crafting the plan on the offensive side of the ball.",
        "defensive_coordinator": "Putting the defensive game plan together.",
    }.get(role, "Part of the team leadership group.")
    accent = team_color if isinstance(team_color, str) and team_color.startswith("#") else "#52657d"
    heat = ""
    if hotseat:
        score = int(hotseat["score"])
        heat = (
            f'<div style="margin-top:12px;padding-top:10px;border-top:1px solid #303947;">'
            f'<div style="display:flex;align-items:center;justify-content:space-between;gap:8px;">'
            f'<span style="font-size:10px;color:#aeb9c8;letter-spacing:.45px;">HOT-SEAT METER</span>'
            f'<span style="font-size:11px;font-weight:750;color:{hotseat["color"]};">{hotseat["status"]}</span></div>'
            f'<div style="height:5px;background:#303947;border-radius:99px;overflow:hidden;margin-top:7px;">'
            f'<div style="height:100%;width:{score}%;background:{hotseat["color"]};border-radius:99px;"></div></div>'
            f'<div style="font-size:11px;color:#aeb9c8;line-height:1.35;margin-top:6px;">{html.escape(hotseat.get("reason", "Pressure estimate from team results"))}</div>'
            f'</div>'
        )
    return (
        f'<div style="box-sizing:border-box;min-height:238px;height:238px;display:flex;flex-direction:column;'
        f'background:#171d27;border:1px solid #303947;border-left:4px solid {accent};'
        f'border-radius:14px;padding:17px 17px 15px;box-shadow:0 5px 14px rgba(0,0,0,.16);">'
        f'<div style="font-size:10px;font-weight:750;letter-spacing:1px;color:#8996a8;margin-bottom:10px;">{title}</div>'
        f'<div style="font-size:10px;font-weight:700;letter-spacing:.65px;color:{accent};text-transform:uppercase;">{role_label}</div>'
        f'<div style="font-size:20px;font-weight:750;color:#f1f4f8;line-height:1.25;margin-top:7px;word-break:break-word;">{safe_name}</div>'
        f'{heat}'
        f'<div style="margin-top:auto;padding-top:11px;border-top:1px solid #2b3442;font-size:11px;color:#9eabbc;line-height:1.45;">{footer_copy}</div>'
        f'</div>'
    )


def _pulse_card(record: dict, rank: float | None, team_color: str, fan_temp: float = 50) -> str:
    """Sixth tile: season snapshot plus an estimated fanbase temperature meter."""
    accent = team_color if isinstance(team_color, str) and team_color.startswith("#") else "#52657d"
    wins = record.get("W", "—") if record else "—"
    losses = record.get("L", "—") if record else "—"
    ties = record.get("T", 0) if record else 0
    record_text = f"{wins}-{losses}" + (f"-{ties}" if ties not in (None, 0, "0") else "")
    rank_text = f"#{int(rank)}" if rank is not None else "—"
    fan_temp = max(0, min(100, int(round(fan_temp))))
    if fan_temp < 25:
        mood, meter_color = "CHILLY", "#64748b"
    elif fan_temp < 45:
        mood, meter_color = "QUIET", "#60a5fa"
    elif fan_temp < 65:
        mood, meter_color = "ENGAGED", "#38bdf8"
    elif fan_temp < 82:
        mood, meter_color = "BUZZING", "#34d399"
    else:
        mood, meter_color = "ELECTRIC", "#fb7185"
    return (
        f'<div style="box-sizing:border-box;min-height:238px;height:238px;display:flex;flex-direction:column;'
        f'background:#171d27;border:1px solid #303947;border-left:4px solid {accent};'
        f'border-radius:14px;padding:17px 17px 15px;box-shadow:0 5px 14px rgba(0,0,0,.16);">'
        f'<div style="font-size:10px;font-weight:750;letter-spacing:1px;color:#8996a8;margin-bottom:10px;">SEASON CHECK-IN</div>'
        f'<div style="font-size:10px;font-weight:700;letter-spacing:.65px;color:{accent};text-transform:uppercase;">TEAM PULSE</div>'
        f'<div style="display:flex;gap:16px;margin-top:13px;">'
        f'<div><div style="font-size:10px;color:#9eabbc;letter-spacing:.4px;">RECORD</div><div style="font-size:23px;font-weight:800;color:#f1f4f8;margin-top:3px;">{html.escape(str(record_text))}</div></div>'
        f'<div><div style="font-size:10px;color:#9eabbc;letter-spacing:.4px;">POWER RANK</div><div style="font-size:23px;font-weight:800;color:#f1f4f8;margin-top:3px;">{rank_text}</div></div>'
        f'</div>'
        f'<div style="margin-top:14px;">'
        f'<div style="display:flex;align-items:center;justify-content:space-between;gap:8px;">'
        f'<span style="font-size:10px;color:#aeb9c8;letter-spacing:.45px;">FANBASE TEMPERATURE</span>'
        f'<span style="font-size:11px;font-weight:750;color:{meter_color};">{mood} · {fan_temp}/100</span></div>'
        f'<div style="height:8px;background:#303947;border-radius:99px;overflow:hidden;margin-top:8px;">'
        f'<div style="height:100%;width:{fan_temp}%;background:{meter_color};border-radius:99px;transition:width .3s ease;"></div></div>'
        f'<div style="font-size:10px;color:#8290a2;margin-top:5px;">Based on results and recent momentum</div>'
        f'</div>'
        f'<div style="margin-top:auto;padding-top:10px;border-top:1px solid #2b3442;font-size:11px;color:#9eabbc;line-height:1.45;">The crowd’s mood, measured by how the season is going.</div>'
        f'</div>'
    )


def _tenure_years(person: dict) -> float | None:
    """Read ESPN tenure or calculate it from a verified role start date."""
    person = person or {}
    value = person.get("years")
    if value is not None:
        parsed = _number(value)
        if parsed is not None:
            return max(0.0, parsed)
        match = re.search(r"(\\d+(?:\\.\\d+)?)", str(value))
        if match:
            return max(0.0, float(match.group(1)))

    start_value = person.get("start_date")
    if start_value:
        try:
            start_text = str(start_value).strip().replace("Z", "+00:00")
            try:
                started = datetime.fromisoformat(start_text)
            except ValueError:
                started = datetime.strptime(start_text[:10], "%Y-%m-%d")
            if started.tzinfo is not None:
                started = started.astimezone(timezone.utc).replace(tzinfo=None)
            elapsed_days = (datetime.now(timezone.utc).replace(tzinfo=None) - started).days
            return max(0.0, elapsed_days / 365.2425)
        except (TypeError, ValueError, OverflowError):
            pass
    return None


def render_team_profile_leadership(team_code: str, team_info: dict, ratings_row, record: dict,
                                  metrics_row=None, league_metrics=None, recent_form=None):
    """Render leadership cards with separate GM, head-coach, and coordinator models."""
    st.markdown("## 🏛️ Leadership")
    st.caption("The front office and sideline crew shaping this season.")

    data = _staff_data(team_code, team_info)
    staff = data["staff"]
    team_color = team_info.get("color", "#4b5563")

    rank = _number(ratings_row.get("rank") if hasattr(ratings_row, "get") else None)
    rank_strength = max(0.0, min(100.0, 100 - ((rank - 1) / 31 * 100))) if rank else 50.0
    win_pct = _number(record.get("PCT") if record else None, 0.5)
    record_strength = max(0.0, min(100.0, win_pct * 100))
    overall_strength = 0.55 * rank_strength + 0.45 * record_strength

    recent_form = list(recent_form or [])
    last_five = recent_form[-5:]
    recent_wins = sum(1 for result in last_five if result == "W")
    recent_ties = sum(1 for result in last_five if result == "T")
    recent_games_count = len(last_five)
    recent_pct = ((recent_wins + 0.5 * recent_ties) / recent_games_count
                  if recent_games_count else win_pct)
    form_trend = max(-1.0, min(1.0, (recent_pct - win_pct) * 2))
    fanbase_temperature = max(0, min(100, round(overall_strength * 0.75 + recent_pct * 100 * 0.25)))

    expected_pct = 0.35 + (rank_strength / 100) * 0.30
    expectation_pressure = max(-1.0, min(1.0, (expected_pct - win_pct) * 2))

    def rating_value(column):
        try:
            value = _number(ratings_row.get(column))
            return max(0.0, min(100.0, value)) if value is not None else None
        except Exception:
            return None

    offense_strength = rating_value("offensive_rating")
    defense_strength = rating_value("defensive_rating")
    if offense_strength is None:
        offense_strength = overall_strength
    if defense_strength is None:
        defense_strength = overall_strength

    gm_tenure = _tenure_years(staff.get("general_manager", {}))
    hc_tenure = _tenure_years(staff.get("head_coach", {}))
    coach_side = _coaching_side(staff.get("head_coach", {}))
    coach_side_strength = (offense_strength if coach_side == "offense"
                           else defense_strength if coach_side == "defense" else None)

    gm_score = gm_hot_seat_score(
        roster_strength=rank_strength,
        record_strength=record_strength,
        trend=form_trend,
        expectations=expectation_pressure,
        tenure_years=gm_tenure,
    )

    hc_score = hot_seat_score(
        overall_strength, trend=form_trend, expectations=expectation_pressure,
        tenure_years=hc_tenure
    )
    if coach_side_strength is not None and win_pct < 0.500:
        losing_severity = max(0.0, min(1.0, (0.500 - win_pct) * 2.5))
        side_adjustment = max(-15.0, min(15.0, (50.0 - coach_side_strength) * 0.45))
        side_adjustment *= losing_severity
        hc_score = _score_result(
            hc_score["score"] + side_adjustment,
            overall_strength,
            f"team results plus {coach_side} performance",
            hc_score["tenure_status"],
            f"{coach_side} rating {coach_side_strength:.0f}/100; side-of-ball adjustment {side_adjustment:+.1f}"
        )
    elif coach_side_strength is None:
        hc_score["reason"] += " · head coach side of ball not verified; no unit adjustment"

    score_map = {
        "general_manager": gm_score,
        "head_coach": hc_score,
        "offensive_coordinator": hot_seat_score(offense_strength, trend=form_trend * 0.50),
        "defensive_coordinator": hot_seat_score(defense_strength, trend=form_trend * 0.50),
    }

    for score in score_map.values():
        if score["score"] < 20:
            explanation = "Things are rolling—very little heat right now."
        elif score["score"] < 40:
            explanation = "Some pressure, but the seat is pretty comfortable."
        elif score["score"] < 60:
            explanation = "The spotlight is getting brighter. Results matter."
        elif score["score"] < 80:
            explanation = "Hot seat territory—fans are asking questions."
        else:
            explanation = "Full-on pressure cooker. The next stretch is huge."
        if score.get("tenure_status") == "first_year":
            explanation += " First-year adjustment applied."
        if "side-of-ball adjustment" in score.get("reason", ""):
            explanation += " " + score["reason"].split(" · ")[-1] + "."
        if "side of ball not verified" in score.get("reason", ""):
            explanation += " Side of ball not verified; no unit adjustment."
        if "single-season ceiling" in score.get("reason", ""):
            explanation += " Multi-year GM history is not currently available."
        score["reason"] = explanation

    card_rows = [
        ["owner", "general_manager", "head_coach"],
        ["offensive_coordinator", "defensive_coordinator", "team_pulse"],
    ]
    for roles in card_rows:
        cols = st.columns(3, gap="large")
        for index, role in enumerate(roles):
            with cols[index]:
                if role == "team_pulse":
                    st.markdown(_pulse_card(record, rank, team_color, fanbase_temperature),
                                unsafe_allow_html=True)
                else:
                    person = staff.get(role, {"name": "Staff listing unavailable", "image": None, "years": None})
                    st.markdown(_card(role, person, team_color, score_map.get(role)),
                                unsafe_allow_html=True)
        st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

    with st.expander("🔥 Hot-seat methodology", expanded=False):
        st.markdown(
            "**General manager:** roster quality carries the most weight; current record and recent trajectory "
            "carry less. A single-season snapshot cannot establish repeated organizational failure, so the GM "
            "score is capped below BURNING until multi-year evidence is available. A verified first-year GM "
            "receives additional protection. This module is not currently receiving historical draft, contract, "
            "roster, or multi-year playoff data, so it does not pretend to measure those things.\n\n"
            "**Head coach:** team results, power strength, momentum, and expectations are combined. When the team "
            "is below .500, the head coach's identified side of the ball adjusts pressure: a strong unit reduces "
            "blame, while a weak unit increases it. If the coaching side cannot be verified from staff metadata "
            "or bio text, no side adjustment is applied. Only verified first-year coaches receive the first-year "
            "curve; year two onward uses normal scoring.\n\n"
            "**Coordinators:** evaluated against their own unit ratings. These are fan-facing estimates, not "
            "predictions that anyone will be fired."
        )
        st.markdown(
            "**Team picture:** rank strength **%.0f/100** · record strength **%.0f/100** · combined **%.0f/100**"
            % (rank_strength, record_strength, overall_strength)
        )
        st.markdown(
            f"**Recent form:** {recent_wins}-{recent_games_count-recent_wins-recent_ties}-{recent_ties} "
            f"over last {recent_games_count} · trend {form_trend:+.2f}"
        )
        st.markdown(f"**Head coach evaluation side:** {coach_side or 'not verified'}")
        st.markdown(f"**Unit ratings:** offense {offense_strength:.0f}/100 · defense {defense_strength:.0f}/100")

    updated = data.get("updated")
    st.caption(
        f"Personnel source: {data['source']} · Last successful fetch: {updated or 'not available'} "
        "· cached up to 24 hours"
    )
