"""Stress combinado: El Nino analogo 2015-16 + embalse BAJO.

Bajo los aportes OBSERVADOS del super El Nino 2015-16, barre el nivel inicial del
embalse (V0) para mostrar como escala el riesgo de apagon cuando el sistema entra
a la temporada seca con el embalse ya depletado (el caso real de 2015-16).

Uso: PYTHONPATH=src python scripts/31_elnino_embalse_bajo.py
"""

from __future__ import annotations

import calendar
import json

import numpy as np
import pandas as pd

from minenergia_sddp.config.paths import project_root
from minenergia_sddp.dispatch.datasets import load_daily
from minenergia_sddp.dispatch.deterministic import load_config
from minenergia_sddp.forecasting.aportes import load_monthly_aportes
from minenergia_sddp.optimization.sddp import Sddp, SddpConfig, StageInput
from minenergia_sddp.reporting.run import new_run
from minenergia_sddp.risk.cvar import empirical_cvar
from minenergia_sddp.scenarios.inflow import InflowModel

HORIZON = [(2026, 8), (2026, 9), (2026, 10), (2026, 11), (2026, 12), (2027, 1)]
ANALOG = [(2015, 8), (2015, 9), (2015, 10), (2015, 11), (2015, 12), (2016, 1)]
K = 20
V0_FRACS = [None, 0.50, 0.40, 0.30, 0.25]  # None = embalse actual observado


def build_stages(centros, model, dem_clim, v0, cap, cfg, fase, seed):
    rng = np.random.default_rng(seed)
    hmax = float(cfg["hidraulica"]["turbina_max_gwh_dia"]["valor"])
    tmax = float(cfg["termica"]["capacidad_max_gwh_dia"]["valor"])
    stages = []
    for i, (y, m) in enumerate(HORIZON):
        dias = calendar.monthrange(y, m)[1]
        s = model.sigma_mes[m]
        samples = centros[i] * np.exp(rng.normal(-0.5 * s * s, s, K)) * dias
        stages.append(StageInput(demanda_gwh=dem_clim[m] * dias, capacidad_gwh=cap,
                                 hmax_gwh=hmax * dias, tmax_gwh=tmax * dias,
                                 inflow_samples=samples, probs=np.full(K, 1.0 / K),
                                 etiqueta=f"{y}-{m:02d}"))
    c_term = float(cfg["termica"]["costo_variable_cop_kwh"][fase])
    scfg = SddpConfig(c_term=c_term,
                      c_ens=float(cfg["energia_no_servida"]["costo_cop_kwh"]["valor"]),
                      c_spill=float(cfg["vertimiento"]["penalizacion_cop_kwh"]["valor"]),
                      c_terminal=c_term, vfin=v0, v0=v0)
    return stages, scfg


def evaluar(stages, scfg, seed=42):
    s = Sddp(stages, scfg)
    s.train(iteraciones=25, n_forward=15, seed=seed)
    sim = s.simulate(n=1000, seed=seed + 1)
    tot = sim["totales"]; det = sim["detalle"]
    # mes en que aparece la primera ENS (promedio)
    ens_mes = det["ens"]  # [n, T]
    prob_mes = (ens_mes > 1e-6).mean(axis=0)
    return {
        "E_costo_B": float(tot.mean()) / 1e6,
        "CVaR95_B": empirical_cvar(tot, 0.95) / 1e6,
        "prob_ens": float((ens_mes.sum(axis=1) > 1e-6).mean()),
        "ens_total_gwh": float(ens_mes.sum(axis=1).mean()),
        "gen_termica_gwh": float(det["gt"].sum(axis=1).mean()),
        "prob_ens_por_mes": [round(float(p), 3) for p in prob_mes],
    }


def main():
    root = project_root()
    cfg = load_config()
    daily = load_daily()
    monthly = load_monthly_aportes()
    model = InflowModel.fit(monthly)
    cap = float(daily["capacidad_gwh"].iloc[-1])
    v0_actual = float(daily["volumen_gwh"].iloc[-1])
    daily["mes"] = daily["fecha"].dt.month
    dem_clim = daily.groupby("mes")["demanda_gwh"].apply(lambda x: x.sum() / max(len(x), 1)).to_dict()

    centros = []
    for (y, m) in ANALOG:
        o = monthly[(monthly.index.year == y) & (monthly.index.month == m)]["aportes_gwh_dia"]
        centros.append(float(o.iloc[0]))

    filas = []
    for frac in V0_FRACS:
        v0 = v0_actual if frac is None else frac * cap
        stages, scfg = build_stages(centros, model, dem_clim, v0, cap, cfg, "nino", seed=42)
        r = evaluar(stages, scfg)
        pct = 100 * v0 / cap
        r["embalse_inicial_pct"] = round(pct, 0)
        r["etiqueta"] = "ACTUAL" if frac is None else f"{int(pct)}%"
        filas.append(r)
        print(f"[Embalse {r['etiqueta']:>7s} = {v0:6.0f} GWh] E={r['E_costo_B']:5.2f} "
              f"CVaR={r['CVaR95_B']:5.2f} B COP | P(ENS)={r['prob_ens']:5.1%} | "
              f"ENS={r['ens_total_gwh']:5.0f} GWh | term={r['gen_termica_gwh']:.0f}")

    df = pd.DataFrame(filas)
    carpeta = new_run("run_031_v001", semilla=42,
                      descripcion="El Nino analogo 2015-16 + barrido de embalse inicial (riesgo apagon).")
    df[["etiqueta", "embalse_inicial_pct", "E_costo_B", "CVaR95_B", "prob_ens",
        "ens_total_gwh", "gen_termica_gwh"]].to_csv(carpeta / "stress_embalse_bajo.csv", index=False)
    (carpeta / "resumen.json").write_text(json.dumps({
        "horizonte": [f"{y}-{m:02d}" for (y, m) in HORIZON],
        "aportes": "analogo El Nino 2015-16 (observados)",
        "capacidad_gwh": cap, "v0_actual_gwh": v0_actual,
        "tabla": df.to_dict("records"),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nP(ENS) por mes (embalse 30%):", df[df.etiqueta == "30%"].iloc[0]["prob_ens_por_mes"],
          "→", [f"{y}-{m:02d}" for (y, m) in HORIZON])
    print("Salida:", carpeta.relative_to(root))


if __name__ == "__main__":
    main()
