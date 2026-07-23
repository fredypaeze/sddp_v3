"""Pruebas de los escenarios estocasticos de aportes."""

from __future__ import annotations

import unittest

import numpy as np

from minenergia_sddp.forecasting.aportes import load_monthly_aportes
from minenergia_sddp.scenarios.inflow import InflowModel, reduce_scenarios, validate


class ScenariosTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = load_monthly_aportes()
        cls.mdl = InflowModel.fit(cls.data)

    def test_parametros_fisicos(self) -> None:
        self.assertTrue(0.0 < self.mdl.phi < 1.0)   # persistencia positiva y estacionaria
        self.assertLess(self.mdl.b_oni, 0.0)         # El Nino (ONI alto) reduce aportes
        self.assertGreater(self.mdl.sigma_eps, 0.0)

    def test_reproducibilidad_semilla(self) -> None:
        meses = [8, 9, 10, 11, 12, 1]
        oni = [0.5] * 6
        a = self.mdl.simulate(meses, oni, n=100, rng=np.random.default_rng(7))
        b = self.mdl.simulate(meses, oni, n=100, rng=np.random.default_rng(7))
        self.assertTrue(np.allclose(a, b))

    def test_escenarios_positivos_y_probs(self) -> None:
        meses = [8, 9, 10]
        mat, probs = self.mdl.stage_scenarios(meses, [0.0, 0.0, 0.0], k=15, rng=np.random.default_rng(1))
        self.assertEqual(mat.shape, (3, 15))
        self.assertTrue((mat > 0).all())
        self.assertAlmostEqual(float(probs.sum()), 1.0, places=6)

    def test_nino_reduce_media_simulada(self) -> None:
        meses = [10]
        rng = np.random.default_rng(3)
        neutral = self.mdl.sample_stage(10, 0.0, 5000, rng).mean()
        nino = self.mdl.sample_stage(10, 1.5, 5000, rng).mean()
        self.assertLess(nino, neutral)

    def test_validacion_estructura(self) -> None:
        traj = self.mdl.simulate([8, 9, 10], [0.0] * 3, n=200, rng=np.random.default_rng(5))
        val = validate(traj, self.data, [8, 9, 10])
        self.assertEqual(len(val), 3)
        self.assertIn("sim_media", val.columns)

    def test_reduccion_probs_suman_uno(self) -> None:
        traj = self.mdl.simulate([8, 9, 10, 11], [0.0] * 4, n=300, rng=np.random.default_rng(9))
        reps, probs = reduce_scenarios(traj, 8, np.random.default_rng(9))
        self.assertEqual(reps.shape, (8, 4))
        self.assertAlmostEqual(float(probs.sum()), 1.0, places=6)


if __name__ == "__main__":
    unittest.main()
