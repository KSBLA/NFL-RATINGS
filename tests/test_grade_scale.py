import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src" / "NFL_Rankings"))

from grade_scale import (  # noqa: E402
    SCALE_VERSION,
    grade_label,
    grade_to_raw,
    raw_to_grade,
)


class GradeScaleTests(unittest.TestCase):
    def test_scale_version_is_incremented(self):
        self.assertEqual(SCALE_VERSION, 3)

    def test_calibration_anchors(self):
        self.assertEqual(raw_to_grade(0), 0)
        self.assertEqual(raw_to_grade(50), 65)
        self.assertEqual(raw_to_grade(70), 85)
        self.assertEqual(raw_to_grade(85), 95)
        self.assertEqual(raw_to_grade(100), 99)

    def test_mapping_is_strictly_increasing(self):
        grades = [raw_to_grade(raw / 10) for raw in range(1001)]
        self.assertTrue(all(left < right for left, right in zip(grades, grades[1:])))

    def test_mapping_is_invertible(self):
        for raw in range(0, 101):
            self.assertAlmostEqual(grade_to_raw(raw_to_grade(raw)), raw, places=9)

    def test_classification_boundaries(self):
        cases = [
            (100, "All-Time Great"),
            (95, "All-Time Great"),
            (94.99, "Elite"),
            (90, "Elite"),
            (89.99, "Super Bowl Contender"),
            (80, "Super Bowl Contender"),
            (79.99, "Playoff Contender"),
            (70, "Playoff Contender"),
            (69.99, "Middle of the Pack"),
            (60, "Middle of the Pack"),
            (59.99, "Building"),
            (55, "Building"),
            (54.99, "Complete Rebuild"),
            (0, "Complete Rebuild"),
        ]
        for grade, expected in cases:
            with self.subTest(grade=grade):
                self.assertEqual(grade_label(grade), expected)

    def test_out_of_range_inputs_are_rejected(self):
        with self.assertRaises(ValueError):
            raw_to_grade(-0.1)
        with self.assertRaises(ValueError):
            raw_to_grade(100.1)
        with self.assertRaises(ValueError):
            grade_to_raw(99.1)


if __name__ == "__main__":
    unittest.main()
