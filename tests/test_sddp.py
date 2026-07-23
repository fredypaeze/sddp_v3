"""Pruebas del SDDP: limite deterministico, monotonia de la cota, convergencia, riesgo."""

from __future__ import annotations

import unittest

import numpy as np

from minenergia_sddp.optimization.sddp import Sddp, SddpConfig, StageInput


def _stages(inflows_per_stage, demanda=100.0, cap=1000.0, hmax=250.0, tmax=40.0):
    stages = []
    for infl in inflows_per_stage:
        infl = np.atleast_1d(np.asarray(infl, dtype=float))
        stages.append(StageInput(demanda_gwh=demanda, capacidad_gwh=cap, hmax_gwh=hmax,
                                 tmax_gwh=tmax, inflow_samples=infl,
                                 probs=np.full(len(infl), 1.0 / len(infl))))
    return stages


def _cfg(v0=500.0, vfin=500.0, lam=0.0, alpha=0.95):
    return SddpConfig(c_term=217.0, c_ens=1500.0, c_spill=0.01, c_terminal=217.0,
                      vfin=vfin, v0=v0, lam=lam, alpha=alpha)


class SddpTest(unittest.TestCase):
    def test_limite_deterministico_lb_igual_ub(self) -> None:
        # con un unico aporte por etapa (K=1), LB y UB deben coincidir (deterministico)
        stages = _stages([[90.0], [80.0], [70.0], [110.0]])
        s = Sddp(stages, _cfg())
        r = s.train(iteraciones=6, n_forward=1, seed=0)
        self.assertAlmostEqual(r.lb, r.ub, delta=abs(r.ub) * 1e-4 + 1e-6)

    def test_cota_inferior_no_decrece(self) -> None:
        rng = np.random.default_rng(0)
        stages = _stages([rng.uniform(40, 120, 8) for _ in range(4)])
        s = Sddp(stages, _cfg())
        r = s.train(iteraciones=10, n_forward=6, seed=1, tol=0.0)
        lbs = [h["LB"] for h in r.historia]
        for a, b in zip(lbs, lbs[1:]):
            self.assertGreaterEqual(b, a - abs(a) * 1e-6 - 1e-6)

    def test_convergencia_gap_pequeno(self) -> None:
        rng = np.random.default_rng(2)
        stages = _stages([rng.uniform(60, 110, 10) for _ in range(3)])
        s = Sddp(stages, _cfg())
        r = s.train(iteraciones=25, n_forward=10, seed=3, tol=0.005)
        # convergencia: la cota inferior mejora sustancialmente y la brecha queda
        # acotada (el UB es un estimador Monte Carlo, con ruido para pocos forward).
        lbs = [h["LB"] for h in r.historia]
        self.assertGreaterEqual(lbs[-1], lbs[0])   # cota inferior no decrece
        self.assertLess(abs(r.gap), 0.15)          # UB (estimador MC) cerca de LB

    def test_reproducibilidad(self) -> None:
        stages = _stages([[90.0, 60.0], [80.0, 100.0], [70.0, 50.0]])
        a = Sddp(stages, _cfg()).train(iteraciones=8, n_forward=6, seed=5)
        b = Sddp(stages, _cfg()).train(iteraciones=8, n_forward=6, seed=5)
        self.assertAlmostEqual(a.lb, b.lb, places=6)

    def test_riesgo_no_baja_costo_esperado(self) -> None:
        # una politica aversa al riesgo (lam>0) no puede tener menor E[costo] que la neutral
        rng = np.random.default_rng(7)
        infl = [rng.uniform(30, 120, 12) for _ in range(3)]
        neutral = Sddp(_stages(infl), _cfg(lam=0.0))
        neutral.train(iteraciones=15, n_forward=8, seed=9, tol=0.0)
        averso = Sddp(_stages(infl), _cfg(lam=0.8, alpha=0.9))
        averso.train(iteraciones=15, n_forward=8, seed=9, tol=0.0)
        e_neu = neutral.simulate(n=300, seed=1)["totales"].mean()
        e_ave = averso.simulate(n=300, seed=1)["totales"].mean()
        self.assertGreaterEqual(e_ave, e_neu - abs(e_neu) * 0.02)

    def test_checkpoint_roundtrip(self) -> None:
        import tempfile
        from pathlib import Path
        stages = _stages([[90.0, 60.0], [80.0, 100.0]])
        s = Sddp(stages, _cfg())
        s.train(iteraciones=5, n_forward=4, seed=0)
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "cuts.json"
            s.save_cuts(p)
            s2 = Sddp(stages, _cfg())
            s2.load_cuts(p)
            self.assertEqual(len(s2.cuts[1]), len(s.cuts[1]))


if __name__ == "__main__":
    unittest.main()
