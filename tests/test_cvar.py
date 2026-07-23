"""Pruebas del CVaR integrado en el SDDP (politica aversa al riesgo)."""

from __future__ import annotations

import unittest

import numpy as np

from minenergia_sddp.optimization.sddp import Sddp, SddpConfig, StageInput
from minenergia_sddp.risk.cvar import empirical_cvar, expected_plus_lambda_cvar


def _stages(inflows, demanda=100.0, cap=1000.0, hmax=250.0, tmax=40.0):
    out = []
    for infl in inflows:
        infl = np.atleast_1d(np.asarray(infl, dtype=float))
        out.append(StageInput(demanda_gwh=demanda, capacidad_gwh=cap, hmax_gwh=hmax,
                              tmax_gwh=tmax, inflow_samples=infl,
                              probs=np.full(len(infl), 1.0 / len(infl))))
    return out


class CvarUtilTest(unittest.TestCase):
    def test_cvar_mayor_o_igual_media(self) -> None:
        x = np.array([1.0, 2, 3, 4, 100.0])
        self.assertGreaterEqual(empirical_cvar(x, 0.95), x.mean())

    def test_expected_plus_lambda(self) -> None:
        x = np.array([1.0, 2, 3, 4, 5])
        self.assertGreater(expected_plus_lambda_cvar(x, 0.9, 1.0),
                           expected_plus_lambda_cvar(x, 0.9, 0.0))


class CvarWeightsTest(unittest.TestCase):
    def test_pesos_neutral_igual_probs(self) -> None:
        probs = np.full(5, 0.2)
        vals = np.array([1.0, 5, 2, 4, 3])
        q = Sddp._risk_weights(vals, probs, lam=0.0, alpha=0.95)
        self.assertTrue(np.allclose(q, probs))

    def test_pesos_cargan_la_cola(self) -> None:
        probs = np.full(10, 0.1)
        vals = np.arange(10.0)  # el peor es el ultimo
        q = Sddp._risk_weights(vals, probs, lam=1.0, alpha=0.8)
        self.assertGreater(q[np.argmax(vals)], q[np.argmin(vals)])
        self.assertAlmostEqual(float(q.sum()), 1.0, places=6)


class RiskAversePolicyTest(unittest.TestCase):
    def test_aversion_no_reduce_costo_esperado(self) -> None:
        # la politica neutral es optima en E[costo]; cualquier politica aversa
        # (lam>0) tiene E[costo] >= neutral (invariante garantizado).
        rng = np.random.default_rng(11)
        infl = [rng.uniform(30, 130, 15) for _ in range(4)]
        cfg = dict(c_term=217.0, c_ens=1500.0, c_spill=0.01, c_terminal=217.0, vfin=300.0, v0=400.0)
        neutral = Sddp(_stages(infl), SddpConfig(lam=0.0, alpha=0.95, **cfg))
        neutral.train(iteraciones=18, n_forward=10, seed=3, tol=0.0)
        averso = Sddp(_stages(infl), SddpConfig(lam=1.0, alpha=0.9, **cfg))
        averso.train(iteraciones=18, n_forward=10, seed=3, tol=0.0)
        e_neu = neutral.simulate(n=400, seed=5)["totales"].mean()
        e_ave = averso.simulate(n=400, seed=5)["totales"].mean()
        self.assertGreaterEqual(e_ave, e_neu - abs(e_neu) * 0.02)


if __name__ == "__main__":
    unittest.main()
