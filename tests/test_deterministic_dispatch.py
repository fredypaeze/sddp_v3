"""Pruebas del despacho deterministico: balances, unidades, cotas, no negatividad."""

from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from minenergia_sddp.dispatch.datasets import StageData, to_stages
from minenergia_sddp.dispatch.deterministic import load_config, solve_deterministic


def _stage_data(demanda, aportes, cap=1000.0, v0=500.0, dias=7):
    filas = []
    for i, (d, a) in enumerate(zip(demanda, aportes)):
        filas.append({"etapa": i, "fecha_ini": pd.Timestamp("2025-01-01") + pd.Timedelta(days=7 * i),
                      "fecha_fin": pd.Timestamp("2025-01-07") + pd.Timedelta(days=7 * i),
                      "dias": dias, "demanda_gwh": d, "aportes_gwh": a, "capacidad_gwh": cap,
                      "volumen_ini_obs": v0, "volumen_fin_obs": v0})
    return StageData(etapas=pd.DataFrame(filas), volumen_inicial_gwh=v0, fuente="test")


class DeterministicDispatchTest(unittest.TestCase):
    def setUp(self) -> None:
        self.cfg = load_config()

    def test_balance_electrico_exacto(self) -> None:
        sd = _stage_data([100, 120, 90, 110], [80, 95, 130, 100])
        res = solve_deterministic(sd, self.cfg, fase_enos="neutral")
        self.assertTrue(res.factible)
        t = res.tabla
        desb = (t.gen_hidro_gwh + t.gen_termica_gwh + t.ens_gwh - t.demanda_gwh).abs().max()
        self.assertLess(desb, 1e-6)

    def test_balance_hidrico_exacto(self) -> None:
        sd = _stage_data([100, 120, 90, 110], [80, 95, 130, 100], cap=1000.0, v0=500.0)
        res = solve_deterministic(sd, self.cfg, fase_enos="neutral")
        t = res.tabla.reset_index(drop=True)
        vprev = 500.0
        for i in range(len(t)):
            esperado = vprev + t.aportes_gwh[i] - t.gen_hidro_gwh[i] - t.vertimiento_gwh[i]
            self.assertAlmostEqual(esperado, t.volumen_fin_gwh[i], places=4)
            vprev = t.volumen_fin_gwh[i]

    def test_no_negatividad_y_cotas(self) -> None:
        sd = _stage_data([100, 120, 90, 110], [80, 95, 130, 100], cap=1000.0)
        res = solve_deterministic(sd, self.cfg, fase_enos="neutral")
        t = res.tabla
        for col in ["gen_hidro_gwh", "gen_termica_gwh", "ens_gwh", "vertimiento_gwh", "volumen_fin_gwh"]:
            self.assertGreaterEqual(t[col].min(), -1e-7, col)
        self.assertLessEqual(t.volumen_fin_gwh.max(), 1000.0 + 1e-6)

    def test_ens_cuando_falta_agua_y_capacidad(self) -> None:
        # demanda altisima, sin aportes ni agua, con techo termico -> ENS obligada
        sd = _stage_data([1000, 1000], [0, 0], cap=100.0, v0=10.0)
        res = solve_deterministic(sd, self.cfg, fase_enos="neutral")
        self.assertTrue(res.factible)
        self.assertGreater(res.resumen["ens_total_gwh"], 0.0)

    def test_condicion_terminal(self) -> None:
        sd = _stage_data([100, 100, 100], [100, 100, 100], cap=1000.0, v0=500.0)
        res = solve_deterministic(sd, self.cfg, fase_enos="neutral", vfin=500.0)
        self.assertGreaterEqual(res.resumen["volumen_final_gwh"], 500.0 - 1e-6)

    def test_nino_no_mas_barato_que_neutral(self) -> None:
        sd = _stage_data([100, 120, 90, 110], [80, 95, 70, 60], cap=1000.0, v0=200.0)
        neu = solve_deterministic(sd, self.cfg, fase_enos="neutral")
        nino = solve_deterministic(sd, self.cfg, fase_enos="nino")
        self.assertGreaterEqual(nino.resumen["costo_total_cop"], neu.resumen["costo_total_cop"] - 1e-3)


if __name__ == "__main__":
    unittest.main()
