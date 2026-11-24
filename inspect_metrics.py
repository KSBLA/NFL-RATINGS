import pandas as pd

df = pd.read_csv("Data/output/team_metrics_2026.csv")

print("NUMBER OF COLUMNS:", len(df.columns))
print("\nALL COLUMNS:")
for column in df.columns:
    print(column)
