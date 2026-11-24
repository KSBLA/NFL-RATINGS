

def calculate_team_records(teams, results):
    records = {
        code: {"W": 0, "L": 0, "T": 0, "PF": 0, "PA": 0}
        for code in teams
    }

    for game in results:
        home = game.get("home")
        away = game.get("away")

        if home not in records or away not in records:
            continue

        try:
            home_score = int(game["home_score"])
            away_score = int(game["away_score"])
        except (KeyError, TypeError, ValueError):
            continue

        records[home]["PF"] += home_score
        records[home]["PA"] += away_score
        records[away]["PF"] += away_score
        records[away]["PA"] += home_score

        if home_score > away_score:
            records[home]["W"] += 1
            records[away]["L"] += 1
        elif away_score > home_score:
            records[away]["W"] += 1
            records[home]["L"] += 1
        else:
            records[home]["T"] += 1
            records[away]["T"] += 1

    for record in records.values():
        games = record["W"] + record["L"] + record["T"]
        record["PCT"] = (
            (record["W"] + record["T"] * 0.5) / games
            if games else 0.0
        )
        record["DIFF"] = record["PF"] - record["PA"]

    return records
