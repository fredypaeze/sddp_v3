"""Sensibilidad del SDDP+CVaR a la aversion al riesgo (lambda) y al nivel de cola (alpha).

Entrena la politica para cada (lambda, alpha), la evalua sobre un mismo conjunto de
escenarios y reporta el trade-off costo esperado vs. riesgo (CVaR), agua conservada,
generacion termica y probabilidad de ENS. Guarda outputs/run_025_v001/.

Uso: PYTHONPATH=src python scripts/25_cvar_sensibilidad.py [--iters 20] [--k 20]
"""

from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

from minenergia_sddp.config.paths import project_root
from minenergia_sddp.dispatch.datasets import load_daily
from minenergia_sddp.optimization.build import build_horizon_stages
from minenergia_sddp.optimization.sddp import Sddp
from minenergia_sddp.reporting.run import new_run
from minenergia_sddp.risk.cvar import empirical_cvar


def evaluar(stages, scfg, lam, alpha, iters, forward, seed, n_eval, eval_seed):
    import copy
    cfg = copy.copy(scfg)
    cfg.lam, cfg.alpha = lam, alpha
    s = Sddp(stages, cfg)
    s.train(iteraciones=iters, n_forward=forward, seed=seed, tol=0.0)
    sim = s.simulate(n=n_eval, seed=eval_seed)   # mismo eval_seed => comparabilidad
    tot = sim["totales"]
    det = sim["detalle"]
    return {
        "lambda": lam, "alpha": alpha,
        "E_costo": float(tot.mean()) / 1e6,
        "VaR": float(np.quantile(tot, alpha, method="higher")) / 1e6,
        "CVaR": empirical_cvar(tot, alpha) / 1e6,
        "gen_termica_gwh": float(det["gt"].sum(axis=1).mean()),
        "prob_ens": float((det["ens"].sum(axis=1) > 1e-6).mean()),
        "volumen_final_gwh": float(det["v_next"][:, -1].mean()),
    }


def barrido(stages, scfg, iters, forward, seed):
    filas = []
    for lam in [0.0, 0.25, 0.5, 0.75, 1.0]:
        filas.append(evaluar(stages, scfg, lam, 0.95, iters, forward, seed, 1000, seed + 1))
    for alpha in [0.90, 0.99]:
        filas.append(evaluar(stages, scfg, 0.75, alpha, iters, forward, seed, 1000, seed + 1))
    return pd.DataFrame(filas)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--iters", type=int, default=18)
    ap.add_argument("--forward", type=int, default=12)
    ap.add_argument("--k", type=int, default=15)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--v0_frac", type=float, default=0.32, help="V0 = fraccion de capacidad (estres)")
    ap.add_argument("--tmax_dia", type=float, default=60.0, help="capacidad termica diaria en estres")
    ap.add_argument("--c_terminal", type=float, default=800.0,
                    help="valor estrategico del agua al final (COP/kWh); >costo termico para incentivar conservar")
    args = ap.parse_args()
    root = project_root()

    daily = load_daily()
    start = daily["fecha"].iloc[-1] + pd.DateOffset(months=1)

    # --- caso BASE (sistema real, embalse actual) ---
    st_b, cfg_b, meta_b = build_horizon_stages(start.year, start.month, 6, k=args.k, seed=args.seed)
    base0 = evaluar(st_b, cfg_b, 0.0, 0.95, args.iters, args.forward, args.seed, 1000, args.seed + 1)
    print(f"[BASE] fase={meta_b.fase} V0={meta_b.v0:.0f} ({100*meta_b.v0/meta_b.capacidad_gwh:.0f}%) "
          f"| E={base0['E_costo']:.3f} CVaR={base0['CVaR']:.3f} P(ENS)={base0['prob_ens']:.1%}")

    # --- caso ESTRES (embalse bajo + termica restringida, p.ej. Nino severo + gas) ---
    st_s, cfg_s, meta_s = build_horizon_stages(start.year, start.month, 6, k=args.k, seed=args.seed,
                                               v0_frac=args.v0_frac, tmax_dia=args.tmax_dia,
                                               c_terminal=args.c_terminal)
    df = barrido(st_s, cfg_s, args.iters, args.forward, args.seed)
    for _, r in df.iterrows():
        print(f"[ESTRES] lam={r['lambda']:.2f} a={r['alpha']:.2f} | E={r['E_costo']:.3f} "
              f"CVaR={r['CVaR']:.3f} term={r['gen_termica_gwh']:.0f} "
              f"vol_fin={r['volumen_final_gwh']:.0f} P(ENS)={r['prob_ens']:.1%}")

    carpeta = new_run("run_025_v001", semilla=args.seed,
                      descripcion="Sensibilidad SDDP+CVaR a lambda/alpha. Caso base (embalse actual) "
                                  f"y caso de estres (V0={args.v0_frac:.0%} cap, termica {args.tmax_dia:.0f} GWh/dia).")
    df.to_csv(carpeta / "sensibilidad_estres.csv", index=False)
    pd.DataFrame([base0]).to_csv(carpeta / "caso_base.csv", index=False)
    b = df[(df["lambda"] == 0.0)].iloc[0]
    a = df[(df["lambda"] == 1.0) & (df["alpha"] == 0.95)].iloc[0]
    (carpeta / "resumen.json").write_text(json.dumps({
        "base": {"fase": meta_b.fase, "v0_gwh": meta_b.v0, "resultado": base0},
        "estres": {"v0_frac": args.v0_frac, "tmax_dia": args.tmax_dia,
                   "lectura_lambda_0_a_1": {
                       "delta_E_costo_billones": float(a["E_costo"] - b["E_costo"]),
                       "delta_CVaR_billones": float(a["CVaR"] - b["CVaR"]),
                       "delta_prob_ens": float(a["prob_ens"] - b["prob_ens"]),
                       "delta_agua_final_gwh": float(a["volumen_final_gwh"] - b["volumen_final_gwh"])},
                   "tabla": df.to_dict("records")},
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[ESTRES] lambda 0 -> 1: E[costo] {b['E_costo']:.3f}->{a['E_costo']:.3f} | "
          f"CVaR {b['CVaR']:.3f}->{a['CVaR']:.3f} | P(ENS) {b['prob_ens']:.1%}->{a['prob_ens']:.1%}")
    print("Salida:", carpeta.relative_to(root))


if __name__ == "__main__":
    main()
