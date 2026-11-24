"""Calibrated 0-100 scale for NFL team ratings.

The underlying rating (``overall_raw``) is the weighted blend of the five
rating pillars. It is currently a league-relative composite built from
within-season percentile scores. This module converts that raw composite to
a user-facing 0-100 scale without changing team order.

Calibration anchors:
    raw  0 -> grade  0
    raw 50 -> grade 65  (league-average raw score)
    raw 70 -> grade 85
    raw 85 -> grade 95  (All-Time Great threshold is intentionally rare)
    raw 100 -> grade 99

The piecewise-linear mapping is monotonic and exactly invertible. The upper
range is compressed so exceptional grades require exceptional raw scores.
"""

from __future__ import annotations

SCALE_VERSION = 3

# (raw_score, displayed_grade) calibration anchors.
_CALIBRATION_POINTS = (
    (0.0, 0.0),
    (50.0, 65.0),
    (70.0, 85.0),
    (85.0, 95.0),
    (100.0, 99.0),
)

# Highest floor first. Boundaries are non-overlapping:
# [95, 100], [90, 95), [80, 90), [70, 80), [60, 70), [55, 60), [0, 55).
GRADE_BANDS = (
    (95.0, "All-Time Great"),
    (90.0, "Elite"),
    (80.0, "Super Bowl Contender"),
    (70.0, "Playoff Contender"),
    (60.0, "Middle of the Pack"),
    (55.0, "Building"),
    (0.0, "Complete Rebuild"),
)


def _interpolate(value: float, points: tuple[tuple[float, float], ...], *, inverse: bool) -> float:
    """Interpolate between adjacent calibration anchors."""
    x_index, y_index = (1, 0) if inverse else (0, 1)

    for left, right in zip(points, points[1:]):
        x0, y0 = left[x_index], left[y_index]
        x1, y1 = right[x_index], right[y_index]
        if value <= x1:
            fraction = (value - x0) / (x1 - x0)
            return y0 + fraction * (y1 - y0)

    return points[-1][y_index]


def raw_to_grade(raw: float) -> float:
    """Convert an underlying 0-100 raw score to the displayed 0-99 grade."""
    raw = float(raw)
    if not 0.0 <= raw <= 100.0:
        raise ValueError(f"Raw rating must be between 0 and 100; received {raw}.")
    return _interpolate(raw, _CALIBRATION_POINTS, inverse=False)


def grade_to_raw(grade: float) -> float:
    """Invert :func:`raw_to_grade` for grades in the calibrated 0-99 range."""
    grade = float(grade)
    if not 0.0 <= grade <= 99.0:
        raise ValueError(f"Displayed grade must be between 0 and 99; received {grade}.")
    return _interpolate(grade, _CALIBRATION_POINTS, inverse=True)


def grade_label(grade: float) -> str:
    """Return the exact project classification for a displayed grade."""
    grade = float(grade)
    if not 0.0 <= grade <= 100.0:
        raise ValueError(f"Displayed grade must be between 0 and 100; received {grade}.")
    for floor, label in GRADE_BANDS:
        if grade >= floor:
            return label
    # Defensive fallback; the 0-point band covers every valid grade.
    return GRADE_BANDS[-1][1]
