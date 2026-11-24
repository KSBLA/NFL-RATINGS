"""
This function builds the display game themes for the upcoming games to give each
a unique feel for the date and time it takes place.

"""
from datetime import datetime, date, timedelta


def get_thanksgiving_date(year: int) -> date:
    """Return the fourth Thursday of November."""
    november_first = date(year, 11, 1)

    days_until_thursday = (
        3 - november_first.weekday()
    ) % 7

    first_thursday = november_first + timedelta(
        days=days_until_thursday
    )

    return first_thursday + timedelta(days=21)


def get_holiday_presentation(game_date: date) -> str:
    """Determine the active holiday presentation."""

    year = game_date.year
    thanksgiving = get_thanksgiving_date(year)

    # Christmas Day
    if game_date == date(year, 12, 25):
        return "christmas_day"

    # Christmas season: December 1–24
    if date(year, 12, 1) <= game_date <= date(year, 12, 24):
        return "christmas_eve"

    # Thanksgiving season: two weeks before Thanksgiving through Thanksgiving
    thanksgiving_start = thanksgiving - timedelta(days=14)

    if thanksgiving_start <= game_date <= thanksgiving:
        return "thanksgiving"

    # Halloween season: October 18–31
    halloween_start = date(year, 10, 18)
    halloween_end = date(year, 10, 31)

    if halloween_start <= game_date <= halloween_end:
        return "halloween"

    return "standard"


def get_game_presentation(
    game_date: date,
    kickoff: str = "",
) -> dict:
    """Select the visual presentation for an NFL game."""

    holiday = get_holiday_presentation(game_date)

    kickoff = str(kickoff).strip().upper()
    kickoff_time = None

    try:
        kickoff_time = datetime.strptime(
            " ".join(kickoff.split()[:2]), "%I:%M %p"
        ).time()
    except (ValueError, TypeError):
        pass

    primetime = None

    # Only classify actual evening kickoffs as primetime presentations.
    if game_date.weekday() == 3 and kickoff_time and kickoff_time.hour >= 18:
        primetime = "tnf"

    elif game_date.weekday() == 6 and kickoff_time and kickoff_time.hour >= 20:
        primetime = "snf"

    elif game_date.weekday() == 0 and kickoff_time and kickoff_time.hour >= 18:
        primetime = "mnf"

    # Holiday themes take priority over primetime themes.
    if holiday != "standard":
        return {
            "theme": holiday,
            "holiday": holiday,
            "primetime": primetime,
        }

    return {
        "theme": primetime or "standard",
        "holiday": None,
        "primetime": primetime,
    }


GAME_THEMES = {
    "standard": {
        "label": "",
        "accent": "#B99A5A",
        "secondary": "#FFFFFF",
        "background": "#101820",
        "effect": "none",
    },
    "halloween": {
        "label": "HALLOWEEN",
        "accent": "#FF7518",
        "secondary": "#8A2BE2",
        "background": "#120D1C",
        "effect": "fog",
    },
    "thanksgiving": {
        "label": "THANKSGIVING",
        "accent": "#D99A32",
        "secondary": "#8B4513",
        "background": "#21150F",
        "effect": "leaves",
    },
    "christmas_eve": {
        "label": "CHRISTMAS EVE",
        "accent": "#D62828",
        "secondary": "#16803C",
        "background": "#091A14",
        "effect": "snow",
    },
    "christmas_day": {
        "label": "CHRISTMAS DAY",
        "accent": "#FFD700",
        "secondary": "#D62828",
        "background": "#071A12",
        "effect": "festive_snow",
    },
    "tnf": {
        "label": "THURSDAY NIGHT FOOTBALL",
        "accent": "#8B5CF6",
        "secondary": "#2563EB",
        "background": "#0B1020",
        "effect": "purple_lighting",
    },
    "snf": {
        "label": "SUNDAY NIGHT FOOTBALL",
        "accent": "#E5E7EB",
        "secondary": "#60A5FA",
        "background": "#080D18",
        "effect": "stadium_lights",
    },
    "mnf": {
        "label": "MONDAY NIGHT FOOTBALL",
        "accent": "#2563EB",
        "secondary": "#111827",
        "background": "#080D18",
        "effect": "blue_sweep",
    },
}
