"""Stress run El Nino 2026 — riesgo de deficit/apagon por analogo hidrologico.

Compara el horizonte operativo (ago-2026 a ene-2027) bajo tres escenarios de aportes:
  - Neutral            : climatologia mensual (todos los anios).
  - Analogo 2015-16     : aportes OBSERVADOS del super El Nino 2015-16 (analogo del 2026).
  - Severidad 1997      : analogo 2015-16 escalado (supuesto de super El Nino peor).

Reporta E[costo], VaR, CVaR y P(ENS) del SDDP para cada uno → cuantifica cuanto
sube el riesgo de apagon si 2026 sigue el camino de 1997/2015.

Uso: PYTHONPATH=src python scripts/30_elnino_stress.py
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
SEVERIDAD_1997 = 0.90  # factor sobre el analogo 2015-16 (supuesto documentado)


def build_stages(centros_gwh_dia, model, dem_clim, v0, cap, cfg, fase, seed):
    """Construye etapas del SDDP con aportes centrados en `centros_gwh_dia`."""
    rng = np.random.default_rng(seed)
    hmax = float(cfg["hidraulica"]["turbina_max_gwh_dia"]["valor"])
    tmax = float(cfg["termica"]["capacidad_max_gwh_dia"]["valor"])
    stages = []
    for i, (y, m) in enumerate(HORIZON):
        dias = calendar.monthrange(y, m)[1]
        s = model.sigma_mes[m]                       # sd log del mes
        # muestras lognormales centradas en el objetivo (GWh/dia) -> GWh/mes
        samples = centros_gwh_dia[i] * np.exp(rng.normal(-0.5 * s * s, s, K)) * dias
        stages.append(StageInput(
            demanda_gwh=dem_clim[m] * dias, capacidad_gwh=cap,
            hmax_gwh=hmax * dias, tmax_gwh=tmax * dias,
            inflow_samples=samples, probs=np.full(K, 1.0 / K), etiqueta=f"{y}-{m:02d}"))
    c_term = float(cfg["termica"]["costo_variable_cop_kwh"][fase])
    scfg = SddpConfig(c_term=c_term,
                      c_ens=float(cfg["energia_no_servida"]["costo_cop_kwh"]["valor"]),
                      c_spill=float(cfg["vertimiento"]["penalizacion_cop_kwh"]["valor"]),
                      c_terminal=c_term, vfin=v0, v0=v0)
    return stages, scfg


def evaluar(stages, scfg, seed):
    s = Sddp(stages, scfg)
    r = s.train(iteraciones=25, n_forward=15, seed=seed)
    sim = s.simulate(n=1000, seed=seed + 1)
    tot = sim["totales"]; det = sim["detalle"]
    return {
        "E_costo_B": float(tot.mean()) / 1e6,
        "VaR95_B": float(np.quantile(tot, 0.95, method="higher")) / 1e6,
        "CVaR95_B": empirical_cvar(tot, 0.95) / 1e6,
        "prob_ens": float((det["ens"].sum(axis=1) > 1e-6).mean()),
        "ens_total_gwh": float(det["ens"].sum(axis=1).mean()),
        "gen_termica_gwh": float(det["gt"].sum(axis=1).mean()),
        "vol_final_pct": 100.0 * float(det["v_next"][:, -1].mean()) / scfg.v0,
        "convergencia_gap": float(r.gap), "iters": r.iteraciones,
    }


def main():
    root = project_root()
    cfg = load_config()
    daily = load_daily()
    monthly = load_monthly_aportes()
    model = InflowModel.fit(monthly)

    v0 = float(daily["volumen_gwh"].iloc[-1])
    cap = float(daily["capacidad_gwh"].iloc[-1])
    daily["mes"] = daily["fecha"].dt.month
    dem_clim = daily.groupby("mes")["demanda_gwh"].apply(
        lambda x: x.sum() / max(len(x), 1)).to_dict()  # GWh/dia medio por mes

    clim = monthly.groupby(monthly.index.month)["aportes_gwh_dia"].mean()
    centros_neutral = [float(clim[m]) for (_, m) in HORIZON]
    centros_analogo = []
    for (y, m) in ANALOG:
        o = monthly[(monthly.index.year == y) & (monthly.index.month == m)]["aportes_gwh_dia"]
        centros_analogo.append(float(o.iloc[0]))
    centros_severo = [c * SEVERIDAD_1997 for c in centros_analogo]

    escenarios = {
        "Neutral": (centros_neutral, "neutral"),
        "Analogo_2015-16": (centros_analogo, "nino"),
        "Severidad_1997": (centros_severo, "nino"),
    }
    filas = []
    for nombre, (centros, fase) in escenarios.items():
        stages, scfg = build_stages(centros, model, dem_clim, v0, cap, cfg, fase, seed=42)
        res = evaluar(stages, scfg, seed=42)
        res["escenario"] = nombre; res["fase"] = fase
        res["aportes_medios_gwh_dia"] = round(float(np.mean(centros)), 1)
        filas.append(res)
        print(f"[{nombre:16s}] aportes~{np.mean(centros):5.0f} GWh/d | "
              f"E={res['E_costo_B']:.2f} VaR={res['VaR95_B']:.2f} CVaR={res['CVaR95_B']:.2f} B COP | "
              f"P(ENS)={res['prob_ens']:.1%} | vol_fin={res['vol_final_pct']:.0f}% | term={res['gen_termica_gwh']:.0f} GWh")

    df = pd.DataFrame(filas)[["escenario", "fase", "aportes_medios_gwh_dia", "E_costo_B",
                              "VaR95_B", "CVaR95_B", "prob_ens", "ens_total_gwh",
                              "gen_termica_gwh", "vol_final_pct"]]
    carpeta = new_run("run_030_v001", semilla=42,
                      descripcion="Stress El Nino 2026: Neutral vs Analogo 2015-16 vs Severidad 1997.")
    df.to_csv(carpeta / "stress_elnino_2026.csv", index=False)
    base = df[df.escenario == "Neutral"].iloc[0]
    ana = df[df.escenario == "Analogo_2015-16"].iloc[0]
    (carpeta / "resumen.json").write_text(json.dumps({
        "horizonte": [f"{y}-{m:02d}" for (y, m) in HORIZON],
        "v0_gwh": v0, "v0_pct": round(100 * v0 / cap, 1),
        "delta_neutral_a_analogo": {
            "E_costo_B": round(float(ana.E_costo_B - base.E_costo_B), 3),
            "CVaR_B": round(float(ana.CVaR95_B - base.CVaR95_B), 3),
            "prob_ens_pp": round(float(ana.prob_ens - base.prob_ens) * 100, 1),
        },
        "tabla": df.to_dict("records"),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nEmbalse inicial: {v0:.0f} GWh ({100*v0/cap:.0f}% de capacidad)")
    print("Salida:", carpeta.relative_to(root))


if __name__ == "__main__":
    main()
