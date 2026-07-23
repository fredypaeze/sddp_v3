"""Construccion de las etapas mensuales del horizonte para el SDDP.

Une demanda (climatologia mensual), capacidad y volumen inicial observados, y los
escenarios de aportes del modelo estocastico condicionado a ONI. Reutilizado por
el SDDP, el CVaR y el backtesting.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from minenergia_sddp.config.paths import project_root
from minenergia_sddp.dispatch.datasets import load_daily
from minenergia_sddp.dispatch.deterministic import load_config
from minenergia_sddp.forecasting.aportes import ONI, load_monthly_aportes
from minenergia_sddp.optimization.sddp import SddpConfig, StageInput
from minenergia_sddp.scenarios.inflow import InflowModel


@dataclass(frozen=True)
class HorizonMeta:
    fechas: list[str]
    meses: list[int]
    oni_path: list[float]
    fase: str
    demanda_gwh: list[float]
    v0: float
    capacidad_gwh: float
    k: int
    seed: int


def _monthly_demand_climatology(daily: pd.DataFrame) -> dict[int, float]:
    d = daily.copy()
    d["ym"] = d["fecha"].dt.to_period("M")
    g = d.groupby("ym").agg(dem=("demanda_gwh", "sum"), dias=("fecha", "count")).reset_index()
    g = g[g["dias"] >= 28]
    g["mes"] = g["ym"].astype(str).str[-2:].astype(int)
    # normaliza a demanda diaria media por mes (independiente de dias del mes)
    g["dem_dia"] = g["dem"] / g["dias"]
    return g.groupby("mes")["dem_dia"].mean().to_dict()


def build_horizon_stages(start_year: int, start_month: int, horizon: int = 6, *,
                         fase: str = "auto", k: int = 20, seed: int = 42,
                         cfg_json: dict | None = None,
                         v0_frac: float | None = None, tmax_dia: float | None = None,
                         c_terminal: float | None = None,
                         root: Path | None = None) -> tuple[list[StageInput], SddpConfig, HorizonMeta]:
    """Construye las etapas del horizonte.

    v0_frac: si se da, fuerza V0 = v0_frac * capacidad (prueba de estres del embalse).
    tmax_dia: si se da, sobreescribe la capacidad termica diaria (p.ej. restriccion de gas).
    c_terminal: valor del agua terminal (COP/kWh); por defecto = costo termico de la fase.
    """
    root = root or project_root()
    cfg = cfg_json or load_config()
    rng = np.random.default_rng(seed)

    daily = load_daily()
    monthly = load_monthly_aportes()
    model = InflowModel.fit(monthly)
    dem_clim = _monthly_demand_climatology(daily)

    capacidad = float(daily["capacidad_gwh"].iloc[-1])
    v0 = v0_frac * capacidad if v0_frac is not None else float(daily["volumen_gwh"].iloc[-1])
    tmax_val = tmax_dia if tmax_dia is not None else cfg["termica"]["capacidad_max_gwh_dia"]["valor"]

    oni_tbl = pd.read_csv(root / ONI)
    meses, fechas, oni_path, demandas, stages = [], [], [], [], []
    y, mth = start_year, start_month
    for _ in range(horizon):
        dias = calendar.monthrange(y, mth)[1]
        row = oni_tbl[(oni_tbl.anio == y) & (oni_tbl.mes == mth)]
        oni = float(row["oni"].iloc[0]) if len(row) else float(monthly["oni"].iloc[-1])
        dem_dia = dem_clim.get(mth, np.mean(list(dem_clim.values())))
        samp = model.sample_stage(mth, oni, k, rng) * dias
        stages.append(StageInput(demanda_gwh=dem_dia * dias, capacidad_gwh=capacidad,
                                 hmax_gwh=cfg["hidraulica"]["turbina_max_gwh_dia"]["valor"] * dias,
                                 tmax_gwh=tmax_val * dias,
                                 inflow_samples=samp, probs=np.full(k, 1.0 / k),
                                 etiqueta=f"{y:04d}-{mth:02d}"))
        meses.append(mth); fechas.append(f"{y:04d}-{mth:02d}"); oni_path.append(oni)
        demandas.append(dem_dia * dias)
        mth += 1
        if mth > 12:
            mth = 1; y += 1

    if fase == "auto":
        avg = float(np.mean(oni_path))
        fase = "nino" if avg >= 0.5 else ("nina" if avg <= -0.5 else "neutral")
    c_term = float(cfg["termica"]["costo_variable_cop_kwh"][fase])
    scfg = SddpConfig(
        c_term=c_term,
        c_ens=float(cfg["energia_no_servida"]["costo_cop_kwh"]["valor"]),
        c_spill=float(cfg["vertimiento"]["penalizacion_cop_kwh"]["valor"]),
        c_terminal=c_terminal if c_terminal is not None else c_term,
        vfin=float(cfg["hidraulica"]["volumen_terminal_frac_v0"]["valor"]) * v0,
        v0=v0,
    )
    meta = HorizonMeta(fechas=fechas, meses=meses, oni_path=oni_path, fase=fase,
                       demanda_gwh=demandas, v0=v0, capacidad_gwh=capacidad, k=k, seed=seed)
    return stages, scfg, meta
