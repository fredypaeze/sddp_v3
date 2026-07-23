"""Genera, valida y reduce escenarios estocasticos de aportes para el horizonte.

Ajusta el modelo PAR/ARX(1) periodico, simula trayectorias (Monte Carlo),
valida contra la historia, construye la matriz de escenarios por etapa para el
SDDP y una version reducida. Semilla reproducible. Guarda outputs/run_023_v001/.

Uso: PYTHONPATH=src python scripts/23_escenarios_aportes.py [--n 2000] [--k 20] [--seed 42]
"""

from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

from minenergia_sddp.config.paths import project_root
from minenergia_sddp.forecasting.aportes import ONI, load_monthly_aportes
from minenergia_sddp.reporting.run import new_run
from minenergia_sddp.scenarios.inflow import InflowModel, reduce_scenarios, validate


def horizon_months(start_year: int, start_month: int, h: int):
    meses, fechas = [], []
    y, m = start_year, start_month
    for _ in range(h):
        meses.append(m)
        fechas.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            m = 1
            y += 1
    return meses, fechas


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=2000)
    ap.add_argument("--k", type=int, default=20)
    ap.add_argument("--horizon", type=int, default=6)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    root = project_root()
    rng = np.random.default_rng(args.seed)

    data = load_monthly_aportes()
    mdl = InflowModel.fit(data)

    last = data.index[-1]
    start = (last + pd.DateOffset(months=1))
    meses, fechas = horizon_months(start.year, start.month, args.horizon)
    oni_tbl = pd.read_csv(root / ONI)
    oni_path = []
    for f in fechas:
        yy, mm = int(f[:4]), int(f[5:7])
        row = oni_tbl[(oni_tbl.anio == yy) & (oni_tbl.mes == mm)]
        oni_path.append(float(row["oni"].iloc[0]) if len(row) else float(data["oni"].iloc[-1]))

    traj = mdl.simulate(meses, oni_path, n=args.n, rng=rng)
    val = validate(traj, data, meses)
    mat, probs = mdl.stage_scenarios(meses, oni_path, k=args.k, rng=rng)
    reps, rprobs = reduce_scenarios(traj, min(args.k, 10), rng)

    carpeta = new_run("run_023_v001", semilla=args.seed,
                      descripcion=f"Escenarios de aportes {fechas[0]}..{fechas[-1]} (n={args.n}, k={args.k}).")
    pd.DataFrame(mat, index=[f"etapa_{i+1}" for i in range(len(meses))],
                 columns=[f"s{j+1}" for j in range(args.k)]).to_csv(carpeta / "escenarios_por_etapa.csv")
    val.to_csv(carpeta / "validacion_vs_historia.csv", index=False)
    pd.DataFrame(reps, columns=fechas).assign(prob=rprobs).to_csv(carpeta / "escenarios_reducidos.csv", index=False)
    (carpeta / "modelo_parametros.json").write_text(json.dumps({
        "phi": mdl.phi, "b_oni": mdl.b_oni, "sigma_eps": mdl.sigma_eps,
        "aportes_por_fase_hist": {k: round(v, 2) for k, v in mdl.fase_media_hist.items()},
        "horizonte": fechas, "oni_path": oni_path,
        "autocorr_lag1_sim": val.attrs.get("autocorr_lag1_sim"),
        "semilla": args.seed, "n_trayectorias": args.n, "k_escenarios": args.k,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"phi={mdl.phi:.3f} b_oni={mdl.b_oni:.3f} | horizonte {fechas[0]}..{fechas[-1]}")
    print(val[["etapa", "mes", "sim_media", "hist_media", "sim_sd", "hist_sd"]].round(1).to_string(index=False))
    print("Salida:", carpeta.relative_to(root))


if __name__ == "__main__":
    main()
