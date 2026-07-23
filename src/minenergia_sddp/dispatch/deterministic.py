"""Despacho hidro-termico deterministico multiperiodo (embalse-equivalente agregado).

Formulacion (por etapa t = 0..T-1), energia en GWh, costos en COP:

  Variables: gh_t (hidro), gt_t (termica), ens_t (energia no servida),
             sp_t (vertimiento), v_t (volumen util al cierre de la etapa).

  Balance electrico:   gh_t + gt_t + ens_t = demanda_t - otras_t
  Balance hidrico:     v_t = v_{t-1} + aportes_t - gh_t - sp_t   (v_{-1} = V0)
  Cotas:               0 <= v_t <= capacidad_t
                       0 <= gh_t <= Hmax_t ; 0 <= gt_t <= Tmax_t
                       0 <= ens_t <= demanda_t ; sp_t >= 0
  Condicion terminal:  v_{T-1} >= vfin

  Objetivo:  min sum_t  c_term*gt_t + c_ens*ens_t + c_vert*sp_t   (COP)

Los costos se pasan de COP/kWh a COP/GWh multiplicando por 1e6.
El dual del balance hidrico es el **valor del agua** (COP/GWh) de cada etapa.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from minenergia_sddp.config.paths import project_root
from minenergia_sddp.dispatch.datasets import StageData
from minenergia_sddp.optimization.lp import INF, LpModel

KWH_PER_GWH = 1_000_000.0
CONFIG_DEFAULT = "config/model/parametros_base.json"


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    p = Path(path) if path else project_root() / CONFIG_DEFAULT
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


@dataclass(frozen=True)
class DispatchResult:
    tabla: pd.DataFrame       # por etapa: gen/ens/vertimiento/volumen/valor_agua
    resumen: dict[str, Any]   # costos, totales, factibilidad
    factible: bool


def _costo_termico(cfg: dict[str, Any], fase_enos: str) -> float:
    c = cfg["termica"]["costo_variable_cop_kwh"]
    if fase_enos not in ("neutral", "nino", "nina"):
        raise ValueError(f"fase_enos invalida: {fase_enos}")
    return float(c[fase_enos])


def solve_deterministic(stage_data: StageData, cfg: dict[str, Any], *,
                        fase_enos: str = "neutral",
                        v0: float | None = None,
                        vfin: float | None = None) -> DispatchResult:
    etapas = stage_data.etapas.reset_index(drop=True)
    T = len(etapas)
    if T == 0:
        raise ValueError("StageData vacio")

    hmax_dia = float(cfg["hidraulica"]["turbina_max_gwh_dia"]["valor"])
    tmax_dia = float(cfg["termica"]["capacidad_max_gwh_dia"]["valor"])
    otras_dia = float(cfg["otras_fuentes_gwh_dia"]["valor"])
    c_term = _costo_termico(cfg, fase_enos) * KWH_PER_GWH
    c_ens = float(cfg["energia_no_servida"]["costo_cop_kwh"]["valor"]) * KWH_PER_GWH
    c_vert = float(cfg["vertimiento"]["penalizacion_cop_kwh"]["valor"]) * KWH_PER_GWH

    if v0 is None:
        v0 = stage_data.volumen_inicial_gwh
    if vfin is None:
        frac = float(cfg["hidraulica"]["volumen_terminal_frac_v0"]["valor"])
        vfin = frac * v0

    m = LpModel("min")
    gh, gt, ens, sp, v = [], [], [], [], []
    balance_hidrico_rows: list[int] = []

    for t in range(T):
        dias = int(etapas.loc[t, "dias"])
        cap = float(etapas.loc[t, "capacidad_gwh"])
        dem = float(etapas.loc[t, "demanda_gwh"])
        otras = otras_dia * dias
        gh.append(m.add_var(0.0, hmax_dia * dias, 0.0, f"gh_{t}"))
        gt.append(m.add_var(0.0, tmax_dia * dias, c_term, f"gt_{t}"))
        ens.append(m.add_var(0.0, max(dem, 0.0), c_ens, f"ens_{t}"))
        sp.append(m.add_var(0.0, INF, c_vert, f"sp_{t}"))
        v.append(m.add_var(0.0, cap, 0.0, f"v_{t}"))

        # Balance electrico: gh + gt + ens = demanda - otras
        m.add_eq({gh[t]: 1.0, gt[t]: 1.0, ens[t]: 1.0}, dem - otras, name=f"elec_{t}")

        # Balance hidrico: v_t - v_{t-1} + gh + sp = aportes
        aportes = float(etapas.loc[t, "aportes_gwh"])
        coeffs = {v[t]: 1.0, gh[t]: 1.0, sp[t]: 1.0}
        if t == 0:
            rhs = aportes + v0
        else:
            coeffs[v[t - 1]] = -1.0
            rhs = aportes
        row = m.add_eq(coeffs, rhs, name=f"hidrico_{t}")
        balance_hidrico_rows.append(row)

    # Condicion terminal
    m.add_ge({v[T - 1]: 1.0}, vfin, name="terminal")

    factible = m.solve()
    if not factible:
        return DispatchResult(tabla=pd.DataFrame(), resumen={"status": m.status()}, factible=False)

    filas = []
    for t in range(T):
        # valor del agua = ahorro marginal de costo por GWh extra de aporte
        # = -dual del balance hidrico (COP/GWh) -> COP/kWh (positivo cuando el agua es valiosa)
        valor_agua_cop_kwh = -m.dual(balance_hidrico_rows[t]) / KWH_PER_GWH
        filas.append({
            "etapa": int(etapas.loc[t, "etapa"]),
            "fecha_ini": etapas.loc[t, "fecha_ini"],
            "fecha_fin": etapas.loc[t, "fecha_fin"],
            "demanda_gwh": float(etapas.loc[t, "demanda_gwh"]),
            "aportes_gwh": float(etapas.loc[t, "aportes_gwh"]),
            "gen_hidro_gwh": m.primal(gh[t]),
            "gen_termica_gwh": m.primal(gt[t]),
            "ens_gwh": m.primal(ens[t]),
            "vertimiento_gwh": m.primal(sp[t]),
            "volumen_fin_gwh": m.primal(v[t]),
            "volumen_pct": 100.0 * m.primal(v[t]) / float(etapas.loc[t, "capacidad_gwh"]),
            "valor_agua_cop_kwh": valor_agua_cop_kwh,
        })
    tabla = pd.DataFrame(filas)

    costo_term = (tabla["gen_termica_gwh"] * _costo_termico(cfg, fase_enos) * KWH_PER_GWH).sum()
    costo_ens = (tabla["ens_gwh"] * c_ens).sum()
    resumen = {
        "status": m.status(),
        "fase_enos": fase_enos,
        "n_etapas": T,
        "costo_total_cop": float(m.objective()),
        "costo_termico_cop": float(costo_term),
        "costo_ens_cop": float(costo_ens),
        "costo_total_billones_cop": float(m.objective()) / 1e12,
        "gen_hidro_total_gwh": float(tabla["gen_hidro_gwh"].sum()),
        "gen_termica_total_gwh": float(tabla["gen_termica_gwh"].sum()),
        "ens_total_gwh": float(tabla["ens_gwh"].sum()),
        "vertimiento_total_gwh": float(tabla["vertimiento_gwh"].sum()),
        "volumen_inicial_gwh": float(v0),
        "volumen_final_gwh": float(tabla["volumen_fin_gwh"].iloc[-1]),
        "volumen_terminal_min_gwh": float(vfin),
        "participacion_termica_pct": 100.0 * float(tabla["gen_termica_gwh"].sum()) /
            max(float(tabla["demanda_gwh"].sum()), 1e-9),
    }
    return DispatchResult(tabla=tabla, resumen=resumen, factible=True)
