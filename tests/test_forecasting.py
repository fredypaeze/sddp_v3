"""Pruebas del pronostico de aportes condicionado a ENOS."""

from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from minenergia_sddp.forecasting.aportes import (
    backtest, forecast_climatology, forecast_seasonal_naive, load_monthly_aportes,
)


class ForecastingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = load_monthly_aportes()

    def test_serie_mensual_y_enso(self) -> None:
        d = self.data
        self.assertGreater(len(d), 150)
        for col in ["aportes_gwh_dia", "oni", "fase_enos"]:
            self.assertIn(col, d.columns)
        self.assertFalse(d["aportes_gwh_dia"].isna().any())

    def test_el_nino_reduce_aportes(self) -> None:
        med = self.data.groupby("fase_enos")["aportes_gwh_dia"].mean()
        self.assertLess(med["nino"], med["neutral"])

    def test_baselines_longitud_correcta(self) -> None:
        train = self.data.iloc[:120]
        idx = self.data.index[120:126]
        self.assertEqual(len(forecast_climatology(train, idx)), 6)
        self.assertEqual(len(forecast_seasonal_naive(train, idx)), 6)

    def test_sarimax_supera_persistencia(self) -> None:
        bt = backtest(self.data, horizon=6, min_train=96, step=6,
                      models=["persistencia_estacional", "sarimax", "sarimax_oni"])
        mae = bt.ranking.set_index("modelo")["MAE"]
        self.assertLess(mae["sarimax_oni"], mae["persistencia_estacional"])


if __name__ == "__main__":
    unittest.main()
