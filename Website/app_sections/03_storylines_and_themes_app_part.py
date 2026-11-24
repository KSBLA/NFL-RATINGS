

def evaluate_record_storylines(team, opponent, context):
    """Generate record and standings storyline candidates."""

    candidates = []

    name = team["name"]
    opponent_name = opponent["name"]

    wins = team["wins"]
    losses = team["losses"]
    ties = team.get("ties", 0)

    opponent_wins = opponent["wins"]
    opponent_losses = opponent["losses"]

    playoff_status = team["playoff_status"]
    opponent_status = opponent["playoff_status"]

    division_position = team.get("division_position")
    opponent_division_position = opponent.get("division_position")

    seed = None
    opponent_seed = None

    if playoff_status.startswith("SEED #"):
        seed = int(playoff_status.replace("SEED #", ""))

    if opponent_status.startswith("SEED #"):
        opponent_seed = int(
            opponent_status.replace("SEED #", "")
        )

    # --------------------------------------------------------
    # DIVISION STAKES
    # --------------------------------------------------------

    if (
            context.get("is_division_game")
            and division_position == 1
            and opponent_division_position == 2
    ):
        candidates.append({
            "pillar": "record",
            "headline": "PROTECTING THE DIVISION LEAD",
            "description": (
                f"{name} currently leads its division, but "
                f"{opponent_name} is directly behind. A win "
                f"would help protect its position at the top."
            ),
            "score": 90,
        })

    elif (
            context.get("is_division_game")
            and division_position == 2
            and opponent_division_position == 1
    ):
        candidates.append({
            "pillar": "record",
            "headline": "TAKING CONTROL OF THE DIVISION",
            "description": (
                f"{name} has an opportunity to challenge "
                f"{opponent_name} for the division lead. "
                f"A victory would strengthen its position "
                f"in the divisional race."
            ),
            "score": 90,
        })

    elif (
            context.get("is_division_game")
            and division_position in (2, 3)
            and opponent_division_position in (1, 2, 3)
            and abs(wins - opponent_wins) <= 2
    ):
        candidates.append({
            "pillar": "record",
            "headline": "CLOSING THE GAP IN THE DIVISION",
            "description": (
                f"{name} is within reach of the teams ahead "
                f"in its division. This matchup offers an "
                f"important opportunity to improve its position."
            ),
            "score": 75,
        })

    # --------------------------------------------------------
    # PLAYOFF POSITIONING
    # --------------------------------------------------------

    if seed is not None and seed <= 4:
        candidates.append({
            "pillar": "record",
            "headline": "DEFENDING THEIR PLAYOFF POSITION",
            "description": (
                f"{name} currently holds the #{seed} seed "
                f"in its conference. Every result matters as "
                f"the team looks to maintain valuable postseason "
                f"positioning."
            ),
            "score": 65,
        })

    elif seed in (5, 6, 7):
        candidates.append({
            "pillar": "record",
            "headline": "FIGHTING FOR A WILD CARD",
            "description": (
                f"{name} currently occupies the #{seed} "
                f"playoff position. Staying ahead of the "
                f"teams chasing a wild-card spot is critical."
            ),
            "score": 75,
        })

    elif playoff_status == "IN THE HUNT":
        candidates.append({
            "pillar": "record",
            "headline": "KEEPING POSTSEASON HOPES ALIVE",
            "description": (
                f"{name} remains within reach of the playoff "
                f"picture. A strong result would help keep "
                f"its postseason hopes alive."
            ),
            "score": 80,
        })

    # --------------------------------------------------------
    # SPOILER OPPORTUNITY
    # --------------------------------------------------------

    if (
            seed is None
            and playoff_status != "IN THE HUNT"
            and opponent_seed is not None
            and opponent_seed <= 7
    ):
        candidates.append({
            "pillar": "record",
            "headline": "A CHANCE TO PLAY SPOILER",
            "description": (
                f"{name} has an opportunity to disrupt "
                f"{opponent_name}'s postseason positioning. "
                f"A win could make the playoff race more "
                f"complicated for its opponent."
            ),
            "score": 60,
        })

    return candidates


def render_halloween_hero(
        away,
        home,
        away_record,
        home_record,
        stadium,
        away_rank,
        home_rank,
        week,
        date_label,
        kickoff_label,
        away_logo,
        home_logo,
):
    halloween_html = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;600;700;800;900&family=Roboto:wght@400;500;700;900&display=swap');

    .halloween-hero {
        position: relative;
        overflow: hidden;
        min-height: 500px;
        padding: 30px 28px 34px;
        border-radius: 18px;
        background:
            radial-gradient(ellipse at 50% 100%, #49215f 0%, transparent 58%),
            linear-gradient(135deg, #080910 0%, #171020 55%, #080910 100%);
        border: 1px solid #75422f;
        color: #fff;
        font-family: 'Roboto', Arial, sans-serif;
        text-align: center;
        box-sizing: border-box;
    }
    .halloween-hero::before,
    .halloween-hero::after {
        content: "";
        position: absolute;
        left: -12%;
        right: -12%;
        bottom: -42px;
        height: 125px;
        pointer-events: none;
        z-index: 1;
        background: radial-gradient(ellipse at 20% 55%, rgba(188, 170, 205, .15), transparent 58%),
                    radial-gradient(ellipse at 75% 45%, rgba(137, 115, 160, .13), transparent 62%);
        filter: blur(17px);
        animation: halloween-fog-drift 13s ease-in-out infinite alternate;
    }
    .halloween-hero::after {
        bottom: -58px;
        opacity: .7;
        animation-duration: 19s;
        animation-direction: alternate-reverse;
    }
    .halloween-hero .halloween-decor {
        position: absolute;
        inset: 0;
        overflow: hidden;
        pointer-events: none;
        z-index: 1;
    }
    .halloween-hero .halloween-content {
        position: relative;
        z-index: 2;
    }
    .halloween-hero .pumpkin {
        position: absolute;
        bottom: 8px;
        font-size: clamp(42px, 6vw, 72px);
        line-height: 1;
        opacity: .88;
        filter: drop-shadow(0 0 12px rgba(255, 105, 20, .35));
        animation: pumpkin-glow 4s ease-in-out infinite alternate;
    }
    .halloween-hero .pumpkin-left { left: 14px; transform: rotate(-9deg); }
    .halloween-hero .pumpkin-right { right: 14px; transform: rotate(9deg); animation-delay: 1.4s; }
    .halloween-hero .bat {
        position: absolute;
        color: #05050a;
        font-size: 27px;
        opacity: .82;
        text-shadow: 0 0 8px rgba(182, 76, 255, .35);
        animation: bat-flight 12s linear infinite;
    }
    .halloween-hero .bat-one { top: 16%; left: -8%; animation-delay: -2s; }
    .halloween-hero .bat-two { top: 31%; left: -12%; font-size: 21px; animation-duration: 16s; animation-delay: -9s; }
    .halloween-hero .bat-three { top: 10%; left: -10%; font-size: 18px; animation-duration: 19s; animation-delay: -13s; }
    .halloween-hero .ghost {
        position: absolute;
        right: 8%;
        top: 20%;
        font-size: 34px;
        opacity: .16;
        animation: ghost-float 6s ease-in-out infinite;
    }
    @keyframes bat-flight {
        0% { transform: translateX(0) translateY(0) scale(.8); }
        25% { transform: translateX(30vw) translateY(-18px) scale(1); }
        55% { transform: translateX(65vw) translateY(12px) scale(.9); }
        100% { transform: translateX(115vw) translateY(-8px) scale(.75); }
    }
    @keyframes halloween-fog-drift {
        from { transform: translateX(-4%) scaleX(.96); opacity: .55; }
        to { transform: translateX(5%) scaleX(1.05); opacity: .95; }
    }
    @keyframes pumpkin-glow {
        from { filter: drop-shadow(0 0 7px rgba(255, 105, 20, .2)); }
        to { filter: drop-shadow(0 0 17px rgba(255, 105, 20, .55)); }
    }
    @keyframes ghost-float {
        0%, 100% { transform: translateY(0) rotate(-4deg); }
        50% { transform: translateY(-13px) rotate(4deg); }
    }
    @media (prefers-reduced-motion: reduce) {
        .halloween-hero *, .halloween-hero::before, .halloween-hero::after { animation: none !important; }
    }
    .halloween-hero .eyebrow {
        color: #ff8c28;
        font-family: 'Barlow Condensed', sans-serif;
        font-size: 16px;
        font-weight: 900;
        letter-spacing: 4px;
        text-transform: uppercase;
    }
    .halloween-hero .teams {
        margin-top: 28px;
        display: grid;
        grid-template-columns: 1fr 90px 1fr;
        align-items: center;
        gap: 16px;
    }
    .halloween-hero .side-label {
        color: #ff8c28;
        font-family: 'Barlow Condensed', sans-serif;
        font-size: 13px;
        font-weight: 900;
        letter-spacing: 2px;
        margin-bottom: 12px;
    }
    .halloween-hero .team-logo {
        width: 100px;
        height: 100px;
        object-fit: contain;
        filter: drop-shadow(0 5px 12px #000b);
    }
    .halloween-hero .team-name {
        margin-top: 12px;
        color: #fff;
        font-family: 'Barlow Condensed', 'Roboto', sans-serif;
        font-size: 25px;
        line-height: 1.1;
        font-weight: 900;
    }
    .halloween-hero .record {
        margin-top: 7px;
        color: #d6c8df;
        font-size: 14px;
        font-weight: 700;
    }
    .halloween-hero .rank {
        margin-top: 8px;
        color: #ff7518;
        font-family: 'Barlow Condensed', sans-serif;
        font-size: 23px;
        font-weight: 900;
    }
    .halloween-hero .versus {
        color: #ff7518;
        font-family: 'Barlow Condensed', sans-serif;
        font-size: 32px;
        font-weight: 900;
        text-shadow: 0 0 18px #ff7518;
    }
    .halloween-hero .game-details {
        margin-top: 38px;
        padding-top: 20px;
        border-top: 1px solid rgba(255, 117, 24, 0.35);
        color: #d6c8df;
        font-size: 14px;
        font-weight: 700;
        letter-spacing: 1.5px;
    }
    .halloween-hero .stadium {
        margin-top: 15px;
        color: #ff9a45;
        font-family: 'Barlow Condensed', sans-serif;
        font-size: 18px;
        font-weight: 800;
        letter-spacing: 1px;
    }
    .halloween-hero .kickoff {
        margin-top: 12px;
        color: #d6c8df;
        font-size: 13px;
        font-weight: 700;
        letter-spacing: .5px;
    }
    @media (max-width: 650px) {
        .halloween-hero { padding: 25px 12px; min-height: 0; }
        .halloween-hero .teams { grid-template-columns: 1fr 42px 1fr; gap: 5px; }
        .halloween-hero .team-logo { width: 70px; height: 70px; }
        .halloween-hero .team-name { font-size: 19px; }
        .halloween-hero .versus { font-size: 25px; }
        .halloween-hero .game-details { margin-top: 28px; font-size: 11px; }
    }
    </style>

    <div class="halloween-hero">
        <div class="halloween-decor" aria-hidden="true">
            <span class="pumpkin pumpkin-left">🎃</span>
            <span class="pumpkin pumpkin-right">🎃</span>
            <span class="bat bat-one">🦇</span>
            <span class="bat bat-two">🦇</span>
            <span class="bat bat-three">🦇</span>
            <span class="ghost">👻</span>
        </div>
        <div class="halloween-content">
        <div class="eyebrow">WEEK {week}</div>
        <div style="margin-top: 10px; color: #b64cff; font-family: 'Barlow Condensed', sans-serif; font-size: 13px; font-weight: 900; letter-spacing: 3px;">HALLOWEEN</div>

        <div class="teams">
            <div>
                <div class="side-label">AWAY</div>
                <img class="team-logo" src="{away_logo}" alt="{away} logo">
                <div class="team-name">{away}</div>
                <div class="record">{away_record}</div>
                <div class="rank">{away_rank}</div>
            </div>

            <div class="versus">VS</div>

            <div>
                <div class="side-label">HOME</div>
                <img class="team-logo" src="{home_logo}" alt="{home} logo">
                <div class="team-name">{home}</div>
                <div class="record">{home_record}</div>
                <div class="rank">{home_rank}</div>
            </div>
        </div>

        <div class="game-details">
            {date_label}
            <div class="stadium">{stadium}</div>
            <div class="kickoff">{kickoff_label}</div>
        </div>
        </div>
    </div>
    """

    replacements = {
        "{away}": away,
        "{home}": home,
        "{away_record}": away_record,
        "{home_record}": home_record,
        "{away_rank}": away_rank,
        "{home_rank}": home_rank,
        "{week}": week,
        "{date_label}": date_label,
        "{kickoff_label}": kickoff_label,
        "{stadium}": stadium,
        "{away_logo}": away_logo,
        "{home_logo}": home_logo,
    }
    for placeholder, value in replacements.items():
        halloween_html = halloween_html.replace(placeholder, str(value))

    st.html(halloween_html)


def render_themed_hero(
        theme_name,
        away,
        home,
        away_record,
        home_record,
        stadium,
        away_rank,
        home_rank,
        week,
        date_label,
        kickoff_label,
        away_logo,
        home_logo,
        theme,
):
    """Render the seasonal or primetime game-preview hero."""
    allowed_themes = {
        "thanksgiving", "christmas_eve", "christmas_day", "tnf", "snf", "mnf"
    }
    if theme_name not in allowed_themes:
        return

    css_class = theme_name.replace("_", "-")
    decor = {
        "thanksgiving": """
            <span class="leaf leaf-a">🍂</span><span class="leaf leaf-b">🍁</span>
            <span class="leaf leaf-c">🍂</span><span class="leaf leaf-d">🍁</span>
            <span class="harvest harvest-left">🌾</span><span class="harvest harvest-right">🧺</span>
            <span class="leaf-pile">🍂 🍁 🍂 🍁 🍂 🍁 🍂</span>""",
        "christmas_eve": """
            <span class="snowflake snow-a">❄</span><span class="snowflake snow-b">❅</span>
            <span class="snowflake snow-c">❆</span><span class="snowflake snow-d">❄</span>
            <span class="christmas-tree tree-left">🎄</span><span class="christmas-tree tree-right">🎄</span>
            <span class="snowbank">❄ ❄ ❄ ❄ ❄ ❄ ❄ ❄ ❄ ❄ ❄</span>
            <span class="garland">✦　✧　✦　✧　✦　✧　✦</span>""",
        "christmas_day": """
            <span class="snowflake snow-a">❄</span><span class="snowflake snow-b">❅</span>
            <span class="snowflake snow-c">❆</span><span class="snowflake snow-d">❄</span>
            <span class="christmas-tree tree-left">🎄</span><span class="christmas-tree tree-right">🎄</span>
            <span class="gift gift-left">🎁</span><span class="gift gift-right">🎁</span>
            <span class="snowbank">❄ ❄ ❄ ❄ ❄ ❄ ❄ ❄ ❄ ❄ ❄</span>
            <span class="garland">🔴　✨　🟡　✨　🔴　✨　🟢</span>""",
        "tnf": """<span class="light-beam beam-a"></span><span class="light-beam beam-b"></span><span class="energy-line"></span>""",
        "snf": """<span class="light-beam beam-a"></span><span class="light-beam beam-b"></span><span class="stadium-glow"></span><span class="energy-line"></span>""",
        "mnf": """<span class="light-beam beam-a"></span><span class="light-beam beam-b"></span><span class="blue-flare"></span><span class="energy-line"></span>""",
    }[theme_name]

    html_block = f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;600;700;800;900&family=Roboto:wght@400;500;700;900&display=swap');
    .themed-hero {{ position:relative; overflow:hidden; min-height:500px; padding:30px 28px 34px;
        border-radius:18px; border:1px solid {theme['accent']}88; color:#fff; text-align:center;
        box-sizing:border-box; font-family:'Roboto',Arial,sans-serif;
        background: radial-gradient(ellipse at 50% 100%, {theme['secondary']}55 0%, transparent 60%),
                    linear-gradient(135deg,{theme['background']} 0%,#111827 55%,{theme['background']} 100%); }}
    .themed-hero.thanksgiving {{ background:radial-gradient(ellipse at 50% 100%,#8b451366,transparent 60%),linear-gradient(135deg,#17120d,#302014 55%,#130f0c); }}
    .themed-hero.christmas-eve {{ background:radial-gradient(ellipse at 50% 100%,#145b4266,transparent 60%),linear-gradient(135deg,#071b17,#102b25 55%,#06130f); }}
    .themed-hero.christmas-day {{ background:radial-gradient(ellipse at 50% 100%,#b91c1c55,transparent 60%),linear-gradient(135deg,#071a12,#153326 55%,#07140f); border-color:#d6b64c; }}
    .themed-hero.tnf {{ background:radial-gradient(ellipse at 50% 100%,#5424a866,transparent 60%),linear-gradient(120deg,#080d20,#171238 55%,#07152a); }}
    .themed-hero.snf {{ background:radial-gradient(ellipse at 50% 100%,#244c7866,transparent 60%),linear-gradient(120deg,#050b16,#111d32 55%,#050914); }}
    .themed-hero.mnf {{ background:radial-gradient(ellipse at 50% 100%,#1555a866,transparent 60%),linear-gradient(120deg,#050b19,#0c2450 55%,#050b19); }}
    .themed-decor {{ position:absolute; inset:0; overflow:hidden; pointer-events:none; z-index:1; }}
    .themed-content {{ position:relative; z-index:2; }}
    .themed-hero .eyebrow {{ color:{theme['accent']}; font:900 16px 'Barlow Condensed',sans-serif; letter-spacing:4px; }}
    .themed-hero .teams {{ margin-top:28px; display:grid; grid-template-columns:1fr 90px 1fr; align-items:center; gap:16px; }}
    .themed-hero .side-label {{ color:{theme['accent']}; font:900 13px 'Barlow Condensed',sans-serif; letter-spacing:2px; margin-bottom:12px; }}
    .themed-hero .team-logo {{ width:100px; height:100px; object-fit:contain; filter:drop-shadow(0 5px 12px #000b); }}
    .themed-hero .team-name {{ margin-top:12px; color:#fff; font:900 25px/1.1 'Barlow Condensed',sans-serif; }}
    .themed-hero .record {{ margin-top:7px; color:#e5e7eb; font-size:14px; font-weight:700; }}
    .themed-hero .rank {{ margin-top:8px; color:{theme['accent']}; font:900 23px 'Barlow Condensed',sans-serif; }}
    .themed-hero .versus {{ color:{theme['accent']}; font:900 32px 'Barlow Condensed',sans-serif; text-shadow:0 0 18px {theme['accent']}; }}
    .themed-hero .game-details {{ margin-top:38px; padding-top:20px; border-top:1px solid {theme['accent']}66; color:#e5e7eb; font-size:14px; font-weight:700; letter-spacing:1.5px; }}
    .themed-hero .stadium {{ margin-top:15px; color:{theme['accent']}; font:800 18px 'Barlow Condensed',sans-serif; letter-spacing:1px; }}
    .themed-hero .kickoff {{ margin-top:12px; color:#e5e7eb; font-size:13px; font-weight:700; }}
    /* Thanksgiving: falling leaves settle into a harvest border. */
    .thanksgiving .leaf {{ position:absolute; top:-50px; font-size:28px; animation:leaf-fall 10s linear infinite; }}
    .thanksgiving .leaf-a {{ left:12%; animation-delay:-2s; }} .thanksgiving .leaf-b {{ left:36%; animation-delay:-7s; animation-duration:13s; }}
    .thanksgiving .leaf-c {{ left:67%; animation-delay:-4s; animation-duration:11s; }} .thanksgiving .leaf-d {{ left:88%; animation-delay:-9s; animation-duration:15s; }}
    @keyframes leaf-fall {{ 0% {{ transform:translate(0,-20px) rotate(0); opacity:0; }} 12% {{opacity:.95;}} 85% {{opacity:.9;}} 100% {{transform:translate(75px,560px) rotate(540deg);opacity:.1;}} }}
    .thanksgiving .harvest {{ position:absolute; bottom:12px; font-size:48px; opacity:.8; filter:drop-shadow(0 0 10px #d99a3266); }}
    .harvest-left {{left:16px;}} .harvest-right {{right:16px;}}
    .thanksgiving .leaf-pile {{ position:absolute; bottom:-8px; left:10%; right:10%; font-size:26px; letter-spacing:8px; opacity:.75; text-shadow:0 0 8px #d99a32; }}
    /* Christmas: layered snowfall, snowbank, trees and festive lights. */
    .snowflake {{ position:absolute; top:-35px; color:#fff; font-size:25px; text-shadow:0 0 10px #bdeaff; animation:snow-fall 9s linear infinite; }}
    .snow-a {{left:12%;animation-delay:-1s;}} .snow-b {{left:38%;animation-delay:-6s;animation-duration:12s;}}
    .snow-c {{left:65%;animation-delay:-3s;animation-duration:10s;}} .snow-d {{left:90%;animation-delay:-8s;animation-duration:14s;}}
    @keyframes snow-fall {{0% {{transform:translate(0,-20px);opacity:0;}} 10% {{opacity:.95;}} 100% {{transform:translate(35px,560px);opacity:.85;}}}}
    .snowbank {{ position:absolute; bottom:-16px; left:-2%; right:-2%; height:55px; padding-top:5px; color:#fff; font-size:27px; letter-spacing:12px; opacity:.78; background:linear-gradient(180deg,transparent,#eaf7ff55); }}
    .christmas-tree {{ position:absolute; bottom:20px; font-size:48px; filter:drop-shadow(0 0 12px #e8fff566); }}
    .tree-left {{left:15px;}} .tree-right {{right:15px;}}
    .christmas-day .christmas-tree {{font-size:56px;}}
    .gift {{position:absolute;bottom:17px;font-size:35px;}} .gift-left {{left:75px;}} .gift-right {{right:75px;}}
    .garland {{position:absolute;top:5px;left:0;right:0;color:#f5d76e;font-size:18px;letter-spacing:3px;opacity:.85;text-shadow:0 0 12px #f5d76e;}}
    /* Primetime: dramatic broadcast lighting, tailored to each night. */
    .light-beam {{position:absolute;top:-30%;width:22%;height:145%;background:linear-gradient(180deg,#fff5,transparent 75%);filter:blur(20px);transform:rotate(22deg);opacity:.22;animation:beam-pulse 5s ease-in-out infinite alternate;}}
    .beam-a {{left:8%;}} .beam-b {{right:8%;transform:rotate(-22deg);animation-delay:1.5s;}}
    @keyframes beam-pulse {{from {{opacity:.12;}} to {{opacity:.38;}}}}
    .stadium-glow {{position:absolute;inset:0;background:radial-gradient(ellipse at 50% 0%,#fff3,transparent 52%);}}
    .energy-line {{position:absolute;left:-20%;right:-20%;top:22%;height:2px;background:linear-gradient(90deg,transparent,{theme['accent']}aa,transparent);box-shadow:0 0 18px {theme['accent']};animation:energy-sweep 7s linear infinite;opacity:.6;}}
    @keyframes energy-sweep {{from {{transform:translateX(-20%);}} to {{transform:translateX(20%);}}}}
    .blue-flare {{position:absolute;inset:0;background:radial-gradient(ellipse at 50% 30%,#2563eb33,transparent 55%);}}
    @media(max-width:650px) {{ .themed-hero {{padding:25px 12px;min-height:0;}} .themed-hero .teams {{grid-template-columns:1fr 42px 1fr;gap:5px;}} .themed-hero .team-logo {{width:70px;height:70px;}} .themed-hero .team-name {{font-size:19px;}} .themed-hero .versus {{font-size:25px;}} .themed-hero .game-details {{margin-top:28px;font-size:11px;}} }}
    @media(prefers-reduced-motion:reduce) {{ .themed-hero * {{animation:none!important;}} }}
    </style>
    <div class="themed-hero {css_class}">
      <div class="themed-decor" aria-hidden="true">{decor}</div>
      <div class="themed-content">
        <div class="eyebrow">WEEK {html.escape(str(week))}</div>
        <div style="margin-top:10px;color:{theme['secondary']};font:900 13px 'Barlow Condensed',sans-serif;letter-spacing:3px;">{html.escape(theme['label'])}</div>
        <div class="teams">
          <div><div class="side-label">AWAY</div><img class="team-logo" src="{away_logo}" alt="{away} logo"><div class="team-name">{away}</div><div class="record">{away_record}</div><div class="rank">{away_rank}</div></div>
          <div class="versus">VS</div>
          <div><div class="side-label">HOME</div><img class="team-logo" src="{home_logo}" alt="{home} logo"><div class="team-name">{home}</div><div class="record">{home_record}</div><div class="rank">{home_rank}</div></div>
        </div>
        <div class="game-details">{date_label}<div class="stadium">{stadium}</div><div class="kickoff">{kickoff_label}</div></div>
      </div>
    </div>
    """
    st.html(html_block)
