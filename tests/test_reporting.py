"""Pruebas de la capa de interpretacion operativa (recomendacion termica)."""

from __future__ import annotations

import types
import unittest

import numpy as np

from minenergia_sddp.reporting.recomendacion import frase_recomendacion, recomendacion_por_etapa


def _sim_meta(prob_ens_alta: bool):
    n, T = 100, 3
    val_agua = 400.0 if prob_ens_alta else 120.0
    det = {
        "gh": np.full((n, T), 30.0 * 30),
        "gt": np.full((n, T), 20.0 * 30),
        "ens": np.where(np.arange(n)[:, None] < (30 if prob_ens_alta else 0), 5.0, 0.0) * np.ones((1, T)),
        "sp": np.zeros((n, T)),
        "v_next": np.full((n, T), 4000.0),
        "valor_agua_cop_kwh": np.full((n, T), val_agua),
    }
    meta = types.SimpleNamespace(fechas=["2026-08", "2026-09", "2026-10"],
                                 oni_path=[0.9, 0.9, 0.9], capacidad_gwh=17000.0)
    return {"detalle": det}, meta


class ReportingTest(unittest.TestCase):
    def test_senal_aumentar_termica_con_riesgo(self) -> None:
        sim, meta = _sim_meta(prob_ens_alta=True)
        rec = recomendacion_por_etapa(sim, meta)
        self.assertEqual(len(rec), 3)
        self.assertTrue(any(e["senal"] == "aumentar_termica_conservar_agua" for e in rec))

    def test_senal_priorizar_hidro_sin_riesgo(self) -> None:
        sim, meta = _sim_meta(prob_ens_alta=False)
        rec = recomendacion_por_etapa(sim, meta)
        self.assertTrue(all(e["prob_ens"] == 0.0 for e in rec))
        self.assertTrue(any(e["senal"] == "priorizar_hidro" for e in rec))

    def test_frase_usa_valores_del_run(self) -> None:
        sim, meta = _sim_meta(prob_ens_alta=True)
        rec = recomendacion_por_etapa(sim, meta)
        resumen = {"E_costo_billones_cop": 6.5, "CVaR_billones_cop": 8.3,
                   "alpha": 0.95, "prob_ens_horizonte": 0.3}
        frase = frase_recomendacion(rec, resumen)
        self.assertIn("billones COP", frase)
        self.assertIn("CVaR", frase)


if __name__ == "__main__":
    unittest.main()
