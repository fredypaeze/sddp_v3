from __future__ import annotations

import unittest

from minenergia_sddp.risk.cvar import empirical_cvar, expected_plus_lambda_cvar
from minenergia_sddp.validation.units import assert_cop_kwh_unit, gwh_times_cop_kwh_to_billion_cop, mw_to_gwh


class UnitsAndRiskTest(unittest.TestCase):
    def test_mw_to_gwh(self) -> None:
        self.assertAlmostEqual(mw_to_gwh(100.0, 168.0), 16.8)

    def test_gwh_times_cop_kwh_to_billion_cop(self) -> None:
        self.assertAlmostEqual(gwh_times_cop_kwh_to_billion_cop(10.0, 250.0), 2.5)

    def test_rejects_non_cop_kwh_price_unit(self) -> None:
        with self.assertRaises(ValueError):
            assert_cop_kwh_unit("COP/MWh")
        assert_cop_kwh_unit("COP/kWh")

    def test_cvar(self) -> None:
        costs = [10, 20, 30, 100]
        self.assertEqual(empirical_cvar(costs, 0.75), 100.0)
        self.assertAlmostEqual(expected_plus_lambda_cvar(costs, 0.75, 0.5), 40.0 + 50.0)


if __name__ == "__main__":
    unittest.main()

