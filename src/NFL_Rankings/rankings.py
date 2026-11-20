import nflreadpy as nfl


def test_data_connection():

    print("Testing nflverse data connection...")

    schedules = nfl.load_schedules([2026])

    print("\nConnection successful!")
    print(f"Schedule rows retrieved: {len(schedules)}")


if __name__ == "__main__":
    test_data_connection()