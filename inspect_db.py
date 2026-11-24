import sqlite3

conn = sqlite3.connect("Data/nfl_rankings.db")

tables = conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
).fetchall()

for (table,) in tables:
    print(f"\n{table}")
    columns = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
    print([column[1] for column in columns])

conn.close()
