import pandas as pd

roster_url = "https://github.com/nflverse/nflverse-data/releases/download/weekly_rosters/roster_weekly_2026.parquet"

roster = pd.read_parquet(roster_url)
pbp = pd.read_parquet("Data/cache/play_by_play_2026.parquet")

id_columns = [c for c in pbp.columns if c.endswith("_player_id")]

roster_ids = set(
    roster["gsis_id"].dropna().astype(str).str.strip()
)

pbp_ids = set()

for column in id_columns:
    pbp_ids.update(
        pbp[column].dropna().astype(str).str.strip()
    )

pbp_ids.discard("nan")
pbp_ids.discard("")

matched = roster_ids.intersection(pbp_ids)

print("ROSTER ROWS:", len(roster))
print("ROSTER ROWS WITH GSIS ID:", roster["gsis_id"].notna().sum())
print("UNIQUE ROSTER PLAYER IDS:", len(roster_ids))
print("UNIQUE PLAY-BY-PLAY PLAYER IDS:", len(pbp_ids))
print("MATCHED PLAYER IDS:", len(matched))

print("\nROSTER POSITIONS:")
print(roster["position"].value_counts(dropna=False).to_string())

print("\nSAMPLE MATCHED PLAYERS:")
print(
    roster[roster["gsis_id"].astype(str).isin(matched)]
    [["full_name", "team", "position", "gsis_id"]]
    .drop_duplicates()
    .head(15)
    .to_string(index=False)
)
