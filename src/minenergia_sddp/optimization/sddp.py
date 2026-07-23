"""SDDP (Stochastic Dual Dynamic Programming) de embalse-equivalente agregado.

Estado: volumen util almacenado (GWh). Incertidumbre: aportes por etapa
(independencia por etapa, muestras discretas con probabilidad). Metodo:

- Forward pass: desde V0, para varias trayectorias muestreadas se resuelve el
  subproblema de cada etapa con la aproximacion actual de la funcion de costo
  futuro (FCF) y se registran estados visitados y costo inmediato.
- Backward pass: de la ultima etapa a la primera, en cada estado visitado se
  resuelve el subproblema para cada aporte posible; se promedia valor y dual del
  balance hidrico (subgradiente respecto al volumen de entrada) y se agrega un
  corte de Benders a la FCF de la etapa previa.
- Cota inferior (LB): valor del subproblema de la 1a etapa (deterministica).
- Cota superior (UB): media del costo total de las trayectorias forward (+/- IC).
- Convergencia: brecha (UB-LB)/UB por debajo de tolerancia, o max iteraciones.

La FCF terminal codifica el valor del agua al final del horizonte (penaliza
terminar por debajo de vfin). Los cortes se pueden guardar/recargar (checkpoint).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from minenergia_sddp.optimization.lp import INF, LpModel


@dataclass
class StageInput:
    demanda_gwh: float
    capacidad_gwh: float
    hmax_gwh: float
    tmax_gwh: float
    inflow_samples: np.ndarray   # [K]
    probs: np.ndarray            # [K]
    etiqueta: str = ""


@dataclass
class SddpConfig:
    # Costos en MnCOP por GWh. Nota: 1 MnCOP/GWh = 1 COP/kWh, por lo que estos
    # valores se pasan directamente en COP/kWh y el problema queda bien escalado.
    # El costo total resulta en MnCOP (dividir por 1e6 para billones de COP).
    c_term: float       # MnCOP/GWh (= COP/kWh)
    c_ens: float        # MnCOP/GWh (= COP/kWh)
    c_spill: float      # MnCOP/GWh (= COP/kWh)
    c_terminal: float   # MnCOP/GWh (= COP/kWh) valor del agua terminal
    vfin: float         # GWh minimo deseado al final
    v0: float           # GWh inicial
    lam: float = 0.0    # aversion al riesgo en [0,1] (0 = neutral). CVaR integrado (ETAPA 8)
    alpha: float = 0.95 # nivel de cola del CVaR en [0.80, 0.99]


@dataclass
class SddpResult:
    historia: list[dict] = field(default_factory=list)  # LB/UB/gap por iteracion
    lb: float = 0.0
    ub: float = 0.0
    ub_sd: float = 0.0
    gap: float = 1.0
    iteraciones: int = 0


class Sddp:
    def __init__(self, stages: list[StageInput], cfg: SddpConfig) -> None:
        self.stages = stages
        self.cfg = cfg
        self.T = len(stages)
        # cuts[s] = FCF de la etapa s (usada por el subproblema de la etapa s-1);
        # cuts[T] = valor terminal. Cada corte: (intercepto, pendiente) en th >= intc + slope*v_next
        self.cuts: dict[int, list[tuple[float, float]]] = {s: [] for s in range(1, self.T + 1)}
        self.cuts[self.T] = [(cfg.c_terminal * cfg.vfin, -cfg.c_terminal), (0.0, 0.0)]

    def _terminal_cost(self, v_final: float) -> float:
        """Costo terminal exacto: max sobre la FCF terminal (valor del agua al final)."""
        return max(intc + slope * v_final for intc, slope in self.cuts[self.T])

    @staticmethod
    def _risk_weights(vals: np.ndarray, probs: np.ndarray, lam: float, alpha: float) -> np.ndarray:
        """Pesos de la medida de riesgo rho = (1-lam)*E + lam*CVaR_alpha (minimizacion).

        Implementa SDDP averso al riesgo (CVaR anidado): el corte del backward usa
        una expectativa reponderada que carga mas masa en los peores (mayor costo)
        resultados. lam=0 => pesos = probabilidades (neutral al riesgo).
        """
        if lam <= 0.0:
            return probs
        order = np.argsort(vals)[::-1]      # de peor (mayor costo) a mejor
        tail = 1.0 - alpha
        w_cvar = np.zeros_like(probs)
        acum = 0.0
        for k in order:
            if acum >= tail:
                break
            tomar = min(probs[k], tail - acum)
            w_cvar[k] = tomar / tail
            acum += tomar
        q = (1.0 - lam) * probs + lam * w_cvar
        return q / q.sum()

    # -------- subproblema de una etapa --------
    def _subproblem(self, s: int, v_in: float, inflow: float) -> dict:
        st = self.stages[s]
        cfg = self.cfg
        m = LpModel("min")
        gh = m.add_var(0.0, st.hmax_gwh, 0.0)
        gt = m.add_var(0.0, st.tmax_gwh, cfg.c_term)
        ens = m.add_var(0.0, max(st.demanda_gwh, 0.0), cfg.c_ens)
        sp = m.add_var(0.0, INF, cfg.c_spill)
        vnx = m.add_var(0.0, st.capacidad_gwh, 0.0)
        th = m.add_var(0.0, INF, 1.0)
        m.add_eq({gh: 1.0, gt: 1.0, ens: 1.0}, st.demanda_gwh)
        row_h = m.add_eq({vnx: 1.0, gh: 1.0, sp: 1.0}, v_in + inflow)
        for (intc, slope) in self.cuts[s + 1]:
            m.add_ge({th: 1.0, vnx: -slope}, intc)
        ok = m.solve()
        if not ok:
            raise RuntimeError(
                f"Subproblema no optimo en etapa {s}: {m.status()} "
                f"(v_in={v_in:.1f}, inflow={inflow:.1f}, demanda={st.demanda_gwh:.1f}, "
                f"cap={st.capacidad_gwh:.1f}, hmax={st.hmax_gwh:.1f}, tmax={st.tmax_gwh:.1f}, "
                f"n_cortes={len(self.cuts[s + 1])})")
        gt_v, ens_v, sp_v = m.primal(gt), m.primal(ens), m.primal(sp)
        inmediato = cfg.c_term * gt_v + cfg.c_ens * ens_v + cfg.c_spill * sp_v
        return {
            "valor": m.objective(),        # inmediato + costo futuro (theta)
            "inmediato": inmediato,
            "dual_v": m.dual(row_h),        # subgradiente d(valor)/d(v_in)
            "gh": m.primal(gh), "gt": gt_v, "ens": ens_v, "sp": sp_v,
            "v_next": m.primal(vnx), "theta": m.primal(th),
        }

    # -------- entrenamiento --------
    def train(self, iteraciones: int = 25, n_forward: int = 20, seed: int = 0,
              tol: float = 0.02) -> SddpResult:
        rng = np.random.default_rng(seed)
        res = SddpResult()
        for it in range(iteraciones):
            # ----- forward -----
            estados = np.zeros((n_forward, self.T))   # v_in por etapa
            totales = np.zeros(n_forward)
            for j in range(n_forward):
                v = self.cfg.v0
                for s in range(self.T):
                    st = self.stages[s]
                    k = rng.choice(len(st.inflow_samples), p=st.probs)
                    sol = self._subproblem(s, v, float(st.inflow_samples[k]))
                    estados[j, s] = v
                    totales[j] += sol["inmediato"]
                    v = sol["v_next"]
                totales[j] += self._terminal_cost(v)   # costo terminal exacto
            ub = float(totales.mean())
            ub_sd = float(totales.std(ddof=1)) if n_forward > 1 else 0.0

            # ----- backward -----
            for s in range(self.T - 1, 0, -1):
                st = self.stages[s]
                for j in range(n_forward):
                    v_in = estados[j, s]
                    vals = np.empty(len(st.inflow_samples))
                    duals = np.empty(len(st.inflow_samples))
                    for k in range(len(st.inflow_samples)):
                        sol = self._subproblem(s, v_in, float(st.inflow_samples[k]))
                        vals[k] = sol["valor"]
                        duals[k] = sol["dual_v"]
                    q = self._risk_weights(vals, st.probs, self.cfg.lam, self.cfg.alpha)
                    qbar = float((q * vals).sum())
                    lbar = float((q * duals).sum())
                    # corte: Q_s(v) >= qbar + lbar*(v - v_in) = (qbar - lbar*v_in) + lbar*v
                    self.cuts[s].append((qbar - lbar * v_in, lbar))

            # ----- cota inferior: 1a etapa deterministica con aporte esperado -----
            st0 = self.stages[0]
            inflow0 = float((st0.probs * st0.inflow_samples).sum())
            lb = self._subproblem(0, self.cfg.v0, inflow0)["valor"]

            gap = (ub - lb) / ub if ub > 0 else 1.0
            res.historia.append({"iter": it + 1, "LB": lb, "UB": ub, "UB_sd": ub_sd, "gap": gap,
                                  "n_cortes_etapa1": len(self.cuts[1])})
            res.lb, res.ub, res.ub_sd, res.gap, res.iteraciones = lb, ub, ub_sd, gap, it + 1
            if abs(gap) < tol and it >= 3:
                break
        return res

    # -------- simulacion de la politica final --------
    def simulate(self, n: int = 500, seed: int = 123) -> dict:
        rng = np.random.default_rng(seed)
        totales = np.zeros(n)
        detalle = {c: np.zeros((n, self.T)) for c in
                   ["gh", "gt", "ens", "sp", "v_next", "inflow", "valor_agua_cop_kwh"]}
        for j in range(n):
            v = self.cfg.v0
            for s in range(self.T):
                st = self.stages[s]
                k = rng.choice(len(st.inflow_samples), p=st.probs)
                infl = float(st.inflow_samples[k])
                sol = self._subproblem(s, v, infl)
                totales[j] += sol["inmediato"]
                for c in ["gh", "gt", "ens", "sp", "v_next"]:
                    detalle[c][j, s] = sol[c]
                detalle["inflow"][j, s] = infl
                detalle["valor_agua_cop_kwh"][j, s] = -sol["dual_v"]  # dual en MnCOP/GWh = COP/kWh
                v = sol["v_next"]
            totales[j] += self._terminal_cost(v)
        return {"totales": totales, "detalle": detalle}

    def simulate_path(self, inflow_path: list[float]) -> dict:
        """Evalua la politica (cortes actuales) a lo largo de una trayectoria dada de
        aportes (p.ej. la historia observada). Devuelve costo realizado y detalle."""
        assert len(inflow_path) == self.T, "la trayectoria debe cubrir todas las etapas"
        v = self.cfg.v0
        total = 0.0
        det = {c: [] for c in ["gh", "gt", "ens", "sp", "v_next", "valor_agua_cop_kwh"]}
        for s in range(self.T):
            sol = self._subproblem(s, v, float(inflow_path[s]))
            total += sol["inmediato"]
            for c in ["gh", "gt", "ens", "sp", "v_next"]:
                det[c].append(sol[c])
            det["valor_agua_cop_kwh"].append(-sol["dual_v"])
            v = sol["v_next"]
        total += self._terminal_cost(v)
        return {"costo_total": total, "detalle": det, "volumen_final": v}

    # -------- checkpoints --------
    def save_cuts(self, path: str | Path) -> None:
        data = {str(s): self.cuts[s] for s in self.cuts}
        Path(path).write_text(json.dumps(data), encoding="utf-8")

    def load_cuts(self, path: str | Path) -> None:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        self.cuts = {int(s): [tuple(c) for c in cuts] for s, cuts in data.items()}
