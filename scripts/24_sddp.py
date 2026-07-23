"""Entrena el SDDP en el horizonte de 6 meses, simula la politica y reporta.

Guarda outputs/run_024_v001/: curva de convergencia, cortes (checkpoint),
estadisticos de la politica (E[costo], VaR, CVaR, ENS), valor del agua y la
recomendacion termica por etapa.

Uso: PYTHONPATH=src python scripts/24_sddp.py [--iters 30] [--forward 20] [--k 20]
                                              [--lam 0.0] [--alpha 0.95] [--seed 42]
"""

from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

from minenergia_sddp.config.paths import project_root
from minenergia_sddp.dispatch.datasets import load_daily
from minenergia_sddp.dispatch.deterministic import load_config
from minenergia_sddp.optimization.build import build_horizon_stages
from minenergia_sddp.optimization.sddp import Sddp
from minenergia_sddp.reporting.run import new_run
from minenergia_sddp.risk.cvar import empirical_cvar


def resumen_politica(sim: dict, meta, alpha: float) -> dict:
    tot = sim["totales"]
    det = sim["detalle"]
    var = float(np.quantile(tot, alpha, method="higher"))
    cvar = empirical_cvar(tot, alpha)
    por_etapa = []
    for s in range(det["gt"].shape[1]):
        por_etapa.append({
            "etapa": s + 1, "fecha": meta.fechas[s],
            "gen_termica_gwh_media": float(det["gt"][:, s].mean()),
            "gen_hidro_gwh_media": float(det["gh"][:, s].mean()),
            "prob_ens": float((det["ens"][:, s] > 1e-6).mean()),
            "ens_gwh_media": float(det["ens"][:, s].mean()),
            "volumen_fin_gwh_media": float(det["v_next"][:, s].mean()),
            "valor_agua_cop_kwh_media": float(det["valor_agua_cop_kwh"][:, s].mean()),
        })
    return {
        "E_costo_billones_cop": float(tot.mean()) / 1e6,
        "VaR_billones_cop": var / 1e6,
        "CVaR_billones_cop": cvar / 1e6,
        "alpha": alpha,
        "prob_ens_horizonte": float((det["ens"].sum(axis=1) > 1e-6).mean()),
        "ens_total_gwh_media": float(det["ens"].sum(axis=1).mean()),
        "gen_termica_total_gwh_media": float(det["gt"].sum(axis=1).mean()),
        "volumen_final_gwh_media": float(det["v_next"][:, -1].mean()),
        "por_etapa": por_etapa,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--iters", type=int, default=30)
    ap.add_argument("--forward", type=int, default=20)
    ap.add_argument("--k", type=int, default=20)
    ap.add_argument("--lam", type=float, default=0.0)
    ap.add_argument("--alpha", type=float, default=0.95)
    ap.add_argument("--horizon", type=int, default=6)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--run", default="run_024_v001")
    args = ap.parse_args()
    root = project_root()

    daily = load_daily()
    last = daily["fecha"].iloc[-1]
    start = last + pd.DateOffset(months=1)
    stages, scfg, meta = build_horizon_stages(start.year, start.month, args.horizon,
                                              k=args.k, seed=args.seed)
    scfg.lam, scfg.alpha = args.lam, args.alpha

    sddp = Sddp(stages, scfg)
    res = sddp.train(iteraciones=args.iters, n_forward=args.forward, seed=args.seed)
    sim = sddp.simulate(n=800, seed=args.seed + 1)
    rp = resumen_politica(sim, meta, args.alpha)

    carpeta = new_run(args.run, config=load_config(), semilla=args.seed,
                      descripcion=f"SDDP {meta.fechas[0]}..{meta.fechas[-1]} fase={meta.fase} "
                                  f"lam={args.lam} alpha={args.alpha}.")
    pd.DataFrame(res.historia).to_csv(carpeta / "convergencia.csv", index=False)
    pd.DataFrame(rp["por_etapa"]).to_csv(carpeta / "politica_por_etapa.csv", index=False)
    sddp.save_cuts(carpeta / "cortes_checkpoint.json")
    (carpeta / "resumen.json").write_text(json.dumps({
        "horizonte": meta.fechas, "fase": meta.fase, "oni_path": meta.oni_path,
        "v0_gwh": meta.v0, "capacidad_gwh": meta.capacidad_gwh,
        "convergencia": {"LB_billones": res.lb / 1e6, "UB_billones": res.ub / 1e6,
                         "gap": res.gap, "iteraciones": res.iteraciones},
        "politica": rp,
        "lambda": args.lam, "alpha": args.alpha,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"SDDP {meta.fechas[0]}..{meta.fechas[-1]} fase={meta.fase} | "
          f"iters={res.iteraciones} gap={res.gap:.3f}")
    print(f"  LB={res.lb/1e6:.3f}  UB={res.ub/1e6:.3f} B COP")
    print(f"  E[costo]={rp['E_costo_billones_cop']:.3f}  VaR={rp['VaR_billones_cop']:.3f}  "
          f"CVaR={rp['CVaR_billones_cop']:.3f} B COP  P(ENS)={rp['prob_ens_horizonte']:.2%}")
    print("Salida:", carpeta.relative_to(root))


if __name__ == "__main__":
    main()
