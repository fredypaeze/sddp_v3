from __future__ import annotations

import unittest

import pandas as pd

from minenergia_sddp.validation.checks import date_range, duplicate_count, probabilities_sum_to_one


class ValidationChecksTest(unittest.TestCase):
    def test_date_range(self) -> None:
        df = pd.DataFrame({"fecha": ["2026-01-01", "2026-01-03", "bad"]})
        self.assertEqual(date_range(df, "fecha"), ("2026-01-01", "2026-01-03", 1))

    def test_duplicate_count(self) -> None:
        df = pd.DataFrame({"fecha": ["a", "a", "b"], "codigo": [1, 1, 1]})
        self.assertEqual(duplicate_count(df, ["fecha", "codigo"]), 1)

    def test_probabilities(self) -> None:
        df = pd.DataFrame({"fecha": ["x", "x", "y"], "p": [0.4, 0.6, 0.9]})
        out = probabilities_sum_to_one(df, ["fecha"], "p")
        self.assertTrue(bool(out.loc[out["fecha"].eq("x"), "valid"].iloc[0]))
        self.assertFalse(bool(out.loc[out["fecha"].eq("y"), "valid"].iloc[0]))


if __name__ == "__main__":
    unittest.main()

