"""Backtesting historico de politicas de despacho sobre episodios ENOS.

Para cada episodio (ventana de 6 meses) compara el costo realizado de:
  - vision perfecta deterministica (cota inferior; conoce los aportes),
  - politica SDDP neutral al riesgo (lam=0),
  - politica SDDP aversa al riesgo (lam>0, CVaR),
  - regla miope "hidro-primero" (turbina lo disponible, termica solo el faltante).
Todas se evaluan sobre la MISMA trayectoria de aportes OBSERVADA. El modelo de
escenarios se ajusta solo con datos ANTERIORES al episodio (sin fuga temporal).

Guarda outputs/run_026_v001/. Uso: PYTHONPATH=src python scripts/26_backtesting.py
"""

from __future__ import annotations

import calendar
import json

import numpy as np
import pandas as pd

from minenergia_sddp.config.paths import project_root
from minenergia_sddp.dispatch.datasets import load_daily
from minenergia_sddp.dispatch.deterministic import load_config
from minenergia_sddp.forecasting.aportes import ONI, load_monthly_aportes
from minenergia_sddp.optimization.sddp import Sddp, SddpConfig, StageInput
from minenergia_sddp.reporting.run import new_run
from minenergia_sddp.scenarios.inflow import InflowModel

EPISODIOS = [
    ("Nino 2023-24", 2023, 8),
    ("Transicion 2024-25", 2024, 8),
    ("Reciente 2025", 2025, 1),
]


def _meses(y, m, h):
    out = []
    for _ in range(h):
        out.append((y, m)); m += 1
        if m > 12:
            m = 1; y += 1
    return out


def _demanda_mes(daily, y, m):
    d = daily[(daily.fecha.dt.year == y) & (daily.fecha.dt.month == m)]
    return float(d["demanda_gwh"].sum()), len(d)


def construir_episodio(nombre, y0, m0, horizon, k, seed, v0_frac=None):
    root = project_root()
    cfg = load_config()
    daily = load_daily()
    monthly = load_monthly_aportes()
    oni_tbl = pd.read_csv(root / ONI)
    inicio = pd.Timestamp(f"{y0:04d}-{m0:02d}-01")

    # sin fuga: ajustar el modelo de aportes solo con datos anteriores al episodio
    train = monthly[monthly.index < inicio]
    model = InflowModel.fit(train)

    daily_ep = daily[daily.fecha < inicio]
    capacidad = float(daily_ep["capacidad_gwh"].iloc[-1])
    v0 = v0_frac * capacidad if v0_frac is not None else float(daily_ep["volumen_gwh"].iloc[-1])

    meses = _meses(y0, m0, horizon)
    rng = np.random.default_rng(seed)
    stages, aportes_obs, oni_path, demanda = [], [], [], []
    for (y, m) in meses:
        dias = calendar.monthrange(y, m)[1]
        row = oni_tbl[(oni_tbl.anio == y) & (oni_tbl.mes == m)]
        oni = float(row["oni"].iloc[0]) if len(row) else 0.0
        dem, ndias = _demanda_mes(daily, y, m)
        if ndias < 20:
            return None  # episodio sin demanda observada suficiente
        samp = model.sample_stage(m, oni, k, rng) * dias
        stages.append(StageInput(demanda_gwh=dem, capacidad_gwh=capacidad,
                                 hmax_gwh=cfg["hidraulica"]["turbina_max_gwh_dia"]["valor"] * dias,
                                 tmax_gwh=cfg["termica"]["capacidad_max_gwh_dia"]["valor"] * dias,
                                 inflow_samples=samp, probs=np.full(k, 1.0 / k), etiqueta=f"{y}-{m:02d}"))
        # aporte observado del mes (GWh totales)
        obs = monthly[(monthly.index.year == y) & (monthly.index.month == m)]["aportes_gwh_dia"]
        aportes_obs.append(float(obs.iloc[0]) * dias if len(obs) else float(np.mean(samp)))
        oni_path.append(oni); demanda.append(dem)

    fase = "nino" if np.mean(oni_path) >= 0.5 else ("nina" if np.mean(oni_path) <= -0.5 else "neutral")
    c_term = float(cfg["termica"]["costo_variable_cop_kwh"][fase])
    scfg = SddpConfig(c_term=c_term, c_ens=float(cfg["energia_no_servida"]["costo_cop_kwh"]["valor"]),
                      c_spill=float(cfg["vertimiento"]["penalizacion_cop_kwh"]["valor"]),
                      c_terminal=c_term, vfin=v0, v0=v0)
    return {"nombre": nombre, "stages": stages, "scfg": scfg, "aportes_obs": aportes_obs,
            "fase": fase, "meses": [f"{y}-{m:02d}" for (y, m) in meses]}


def regla_miope(stages, scfg, inflow_path):
    """Hidro-primero: turbina min(demanda, agua disponible, hmax); termica cubre; ENS si falta."""
    v = scfg.v0; total = 0.0; ens_tot = 0.0; term_tot = 0.0
    for s, st in enumerate(stages):
        disp = v + inflow_path[s]
        gh = min(st.demanda_gwh, st.hmax_gwh, disp)
        resto = st.demanda_gwh - gh
        gt = min(resto, st.tmax_gwh)
        ens = max(resto - gt, 0.0)
        sp = max(disp - gh - st.capacidad_gwh, 0.0)
        v = min(disp - gh - sp, st.capacidad_gwh)
        total += scfg.c_term * gt + scfg.c_ens * ens + scfg.c_spill * sp
        ens_tot += ens; term_tot += gt
    total += max(intc + slope * v for intc, slope in
                 [(scfg.c_terminal * scfg.vfin, -scfg.c_terminal), (0.0, 0.0)])
    return {"costo": total, "ens": ens_tot, "termica": term_tot, "vol_final": v}


def main() -> None:
    root = project_root()
    filas = []
    detalles = {}
    for (nombre, y0, m0) in EPISODIOS:
        ep = construir_episodio(nombre, y0, m0, 6, k=15, seed=42)
        if ep is None:
            print(f"[{nombre}] omitido (sin demanda observada suficiente)"); continue
        stages, scfg, path = ep["stages"], ep["scfg"], ep["aportes_obs"]

        # deterministico vision perfecta (K=1 = aportes observados)
        det_stages = [StageInput(demanda_gwh=st.demanda_gwh, capacidad_gwh=st.capacidad_gwh,
                                 hmax_gwh=st.hmax_gwh, tmax_gwh=st.tmax_gwh,
                                 inflow_samples=np.array([path[i]]), probs=np.array([1.0]))
                      for i, st in enumerate(stages)]
        det = Sddp(det_stages, scfg); det.train(iteraciones=6, n_forward=1, seed=0)
        det_real = det.simulate_path(path)

        # SDDP neutral y averso, evaluados en la trayectoria observada
        neu = Sddp(stages, SddpConfig(**{**scfg.__dict__, "lam": 0.0}))
        neu.train(iteraciones=18, n_forward=12, seed=42)
        neu_real = neu.simulate_path(path)
        ave = Sddp(stages, SddpConfig(**{**scfg.__dict__, "lam": 0.6, "alpha": 0.95}))
        ave.train(iteraciones=18, n_forward=12, seed=42)
        ave_real = ave.simulate_path(path)

        miope = regla_miope(stages, scfg, path)

        row = {"episodio": nombre, "fase": ep["fase"],
               "det_vision_perfecta_B": det_real["costo_total"] / 1e6,
               "sddp_neutral_B": neu_real["costo_total"] / 1e6,
               "sddp_cvar_B": ave_real["costo_total"] / 1e6,
               "miope_B": miope["costo"] / 1e6,
               "ens_neutral_gwh": float(sum(neu_real["detalle"]["ens"])),
               "ens_miope_gwh": miope["ens"]}
        filas.append(row)
        detalles[nombre] = {"meses": ep["meses"], "aportes_obs": path}
        print(f"[{nombre}] fase={ep['fase']} | det={row['det_vision_perfecta_B']:.3f} "
              f"neutral={row['sddp_neutral_B']:.3f} cvar={row['sddp_cvar_B']:.3f} "
              f"miope={row['miope_B']:.3f} B COP")

    # --- variante de ESTRES: mismo episodio con embalse bajo (SDDP vs miope) ---
    filas_estres = []
    for (nombre, y0, m0) in EPISODIOS:
        ep = construir_episodio(nombre, y0, m0, 6, k=15, seed=42, v0_frac=0.25)
        if ep is None:
            continue
        stages, scfg, path = ep["stages"], ep["scfg"], ep["aportes_obs"]
        neu = Sddp(stages, SddpConfig(**{**scfg.__dict__, "lam": 0.0}))
        neu.train(iteraciones=18, n_forward=12, seed=42)
        neu_real = neu.simulate_path(path)
        miope = regla_miope(stages, scfg, path)
        r = {"episodio": nombre, "fase": ep["fase"], "v0_frac": 0.25,
             "sddp_neutral_B": neu_real["costo_total"] / 1e6,
             "miope_B": miope["costo"] / 1e6,
             "ens_sddp_gwh": float(sum(neu_real["detalle"]["ens"])),
             "ens_miope_gwh": miope["ens"],
             "ventaja_sddp_B": (miope["costo"] - neu_real["costo_total"]) / 1e6}
        filas_estres.append(r)
        print(f"[ESTRES {nombre}] sddp={r['sddp_neutral_B']:.3f} miope={r['miope_B']:.3f} "
              f"| ENS sddp={r['ens_sddp_gwh']:.0f} miope={r['ens_miope_gwh']:.0f} GWh "
              f"| ventaja SDDP={r['ventaja_sddp_B']:.3f} B COP")

    df = pd.DataFrame(filas)
    carpeta = new_run("run_026_v001", descripcion="Backtesting historico de politicas por episodio ENOS.")
    df.to_csv(carpeta / "backtesting_episodios.csv", index=False)
    df_estres = pd.DataFrame(filas_estres)
    df_estres.to_csv(carpeta / "backtesting_estres.csv", index=False)
    (carpeta / "resumen.json").write_text(json.dumps({"tabla": df.to_dict("records"),
                                                      "estres": df_estres.to_dict("records"),
                                                      "detalles": detalles}, ensure_ascii=False, indent=2),
                                          encoding="utf-8")
    print("Salida:", carpeta.relative_to(root))


if __name__ == "__main__":
    main()
