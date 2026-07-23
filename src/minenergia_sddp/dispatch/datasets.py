"""Carga y alineacion de datos model-ready para el despacho hidro-termico.

Acopla el balance diario del sistema (demanda, generacion) con la hidrologia
energetica agregada del SIN (aportes, volumen y capacidad utiles en GWh) sobre la
ventana temporal comun. Provee vistas diarias y agregadas por etapa.

Unidades: energia en GWh. Fechas como pandas.Timestamp (diarias).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from minenergia_sddp.config.paths import project_root

SYSTEM_DAILY = "data/processed/xm/system_historical_v3/system_daily_model_ready.csv"
HYDRO_DAILY = "data/processed/xm/hydro_system_historical_v1/hydro_system_daily_model_ready.csv"


def load_daily(root: Path | None = None) -> pd.DataFrame:
    """DataFrame diario indexado por fecha con demanda/aportes/volumen/capacidad (GWh).

    La ventana resultante es la interseccion de ambos insumos
    (2023-01-31 .. ultima fecha del sistema).
    """
    root = root or project_root()
    sysd = pd.read_csv(root / SYSTEM_DAILY, parse_dates=["fecha"])
    hyd = pd.read_csv(root / HYDRO_DAILY, parse_dates=["date"])
    df = sysd.merge(hyd, left_on="fecha", right_on="date", how="inner")
    out = pd.DataFrame({
        "fecha": df["fecha"],
        "demanda_gwh": df["demanda_sin_gwh"],
        "aportes_gwh": df["aportes_energia_gwh"],
        "volumen_gwh": df["volumen_util_energia_gwh"],
        "capacidad_gwh": df["capacidad_util_energia_gwh"],
    }).dropna(subset=["demanda_gwh", "aportes_gwh", "volumen_gwh", "capacidad_gwh"])
    out = out.sort_values("fecha").reset_index(drop=True)
    return out


@dataclass(frozen=True)
class StageData:
    """Datos agregados por etapa para el modelo multiperiodo."""

    etapas: pd.DataFrame  # columnas: etapa, fecha_ini, fecha_fin, dias, demanda_gwh, aportes_gwh, capacidad_gwh, volumen_ini_obs, volumen_fin_obs
    volumen_inicial_gwh: float  # estado observado al inicio de la 1a etapa
    fuente: str

    @property
    def n_etapas(self) -> int:
        return len(self.etapas)


def to_stages(daily: pd.DataFrame, dias_por_etapa: int = 7, n_etapas: int | None = None,
              fecha_inicio: str | pd.Timestamp | None = None) -> StageData:
    """Agrega el diario en etapas consecutivas de `dias_por_etapa` dias.

    Flujos (demanda, aportes) se suman; capacidad se toma al cierre de la etapa;
    el volumen inicial de la ventana es el estado (V0) del modelo.
    """
    df = daily.copy()
    if fecha_inicio is not None:
        df = df[df["fecha"] >= pd.Timestamp(fecha_inicio)]
    df = df.reset_index(drop=True)
    if n_etapas is not None:
        df = df.iloc[: n_etapas * dias_por_etapa]
    df["etapa"] = df.index // dias_por_etapa
    if n_etapas is not None:
        df = df[df["etapa"] < n_etapas]

    filas = []
    for etapa, g in df.groupby("etapa"):
        filas.append({
            "etapa": int(etapa),
            "fecha_ini": g["fecha"].iloc[0],
            "fecha_fin": g["fecha"].iloc[-1],
            "dias": len(g),
            "demanda_gwh": float(g["demanda_gwh"].sum()),
            "aportes_gwh": float(g["aportes_gwh"].sum()),
            "capacidad_gwh": float(g["capacidad_gwh"].iloc[-1]),
            "volumen_ini_obs": float(g["volumen_gwh"].iloc[0]),
            "volumen_fin_obs": float(g["volumen_gwh"].iloc[-1]),
        })
    etapas = pd.DataFrame(filas)
    v0 = float(df["volumen_gwh"].iloc[0])
    return StageData(etapas=etapas, volumen_inicial_gwh=v0,
                     fuente="XM system_daily + hydro_system_daily (model-ready)")
