"""Pronostico mensual de aportes del SIN (GWh/dia) condicionado a ENOS.

Objetivo: aportes medios diarios por mes (suaviza el diario). Se comparan
baselines (climatologia, persistencia estacional) contra SARIMAX con y sin la
exogena ONI, seleccionando por backtesting de origen movil (sin fuga temporal).

Metricas: MAE, RMSE, sesgo y sMAPE por horizonte y por fase ENOS del mes objetivo.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from minenergia_sddp.config.paths import project_root

HYDRO_DAILY = "data/processed/xm/hydro_system_historical_v1/hydro_system_daily_model_ready.csv"
ONI = "data/reference/oni_noaa.csv"


def load_monthly_aportes(root: Path | None = None) -> pd.DataFrame:
    """Serie mensual: aportes medios diarios (GWh/dia) + ONI + fase ENOS."""
    root = root or project_root()
    df = pd.read_csv(root / HYDRO_DAILY, parse_dates=["date"])
    df = df.dropna(subset=["aportes_energia_gwh"])
    m = (df.set_index("date")["aportes_energia_gwh"]
           .resample("MS").mean().rename("aportes_gwh_dia").to_frame())
    m["anio"] = m.index.year
    m["mes"] = m.index.month
    oni = pd.read_csv(root / ONI)
    out = m.reset_index().merge(oni[["anio", "mes", "oni", "fase_enos"]], on=["anio", "mes"], how="left")
    out["oni"] = out["oni"].ffill().fillna(0.0)
    out["fase_enos"] = out["fase_enos"].fillna("neutral")
    return out.set_index("date")


# ----------------------------- modelos -----------------------------

def forecast_climatology(train: pd.DataFrame, horizon_index: pd.DatetimeIndex) -> np.ndarray:
    clim = train.groupby(train.index.month)["aportes_gwh_dia"].mean()
    return np.array([clim.get(ts.month, train["aportes_gwh_dia"].mean()) for ts in horizon_index])


def forecast_seasonal_naive(train: pd.DataFrame, horizon_index: pd.DatetimeIndex) -> np.ndarray:
    s = train["aportes_gwh_dia"]
    out = []
    for ts in horizon_index:
        prev = ts - pd.DateOffset(years=1)
        out.append(s.get(prev, s.iloc[-1]))
    return np.array(out, dtype=float)


def forecast_sarimax(train: pd.DataFrame, horizon_index: pd.DatetimeIndex,
                     exog_col: str | None = None,
                     future_exog: np.ndarray | None = None) -> np.ndarray:
    from statsmodels.tsa.statespace.sarimax import SARIMAX
    y = train["aportes_gwh_dia"].astype(float)
    exog = train[[exog_col]].astype(float) if exog_col else None
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            model = SARIMAX(y, exog=exog, order=(1, 0, 0), seasonal_order=(0, 1, 1, 12),
                            enforce_stationarity=False, enforce_invertibility=False)
            fit = model.fit(disp=False, maxiter=200)
            fe = future_exog.reshape(-1, 1) if (exog_col and future_exog is not None) else None
            pred = fit.forecast(steps=len(horizon_index), exog=fe)
            return np.asarray(pred, dtype=float)
        except Exception:
            return forecast_climatology(train, horizon_index)


# ----------------------------- backtest -----------------------------

@dataclass(frozen=True)
class BacktestResult:
    detalle: pd.DataFrame   # cada (origen, horizonte, modelo): y_real, y_pred, error
    por_horizonte: pd.DataFrame
    por_fase: pd.DataFrame
    ranking: pd.DataFrame


def _metrics(g: pd.DataFrame) -> pd.Series:
    err = g["y_pred"] - g["y_real"]
    smape = (2 * err.abs() / (g["y_pred"].abs() + g["y_real"].abs()).replace(0, np.nan)).mean()
    return pd.Series({
        "n": len(g),
        "MAE": err.abs().mean(),
        "RMSE": float(np.sqrt((err ** 2).mean())),
        "sesgo": err.mean(),
        "sMAPE": smape,
    })


def backtest(data: pd.DataFrame, horizon: int = 6, min_train: int = 60,
             step: int = 3, models: list[str] | None = None) -> BacktestResult:
    models = models or ["climatologia", "persistencia_estacional", "sarimax", "sarimax_oni"]
    idx = data.index
    filas = []
    origins = range(min_train, len(data) - horizon, step)
    for o in origins:
        train = data.iloc[:o]
        fut_index = idx[o:o + horizon]
        fut = data.iloc[o:o + horizon]
        preds = {}
        if "climatologia" in models:
            preds["climatologia"] = forecast_climatology(train, fut_index)
        if "persistencia_estacional" in models:
            preds["persistencia_estacional"] = forecast_seasonal_naive(train, fut_index)
        if "sarimax" in models:
            preds["sarimax"] = forecast_sarimax(train, fut_index)
        if "sarimax_oni" in models:
            preds["sarimax_oni"] = forecast_sarimax(train, fut_index, exog_col="oni",
                                                    future_exog=fut["oni"].to_numpy())
        for modelo, yhat in preds.items():
            for h in range(len(fut_index)):
                filas.append({
                    "origen": idx[o - 1], "horizonte": h + 1, "modelo": modelo,
                    "fecha": fut_index[h], "fase_enos": fut["fase_enos"].iloc[h],
                    "y_real": float(fut["aportes_gwh_dia"].iloc[h]), "y_pred": float(yhat[h]),
                })
    detalle = pd.DataFrame(filas)
    por_h = detalle.groupby(["modelo", "horizonte"]).apply(_metrics, include_groups=False).reset_index()
    por_fase = detalle.groupby(["modelo", "fase_enos"]).apply(_metrics, include_groups=False).reset_index()
    ranking = (detalle.groupby("modelo").apply(_metrics, include_groups=False)
               .reset_index().sort_values("MAE").reset_index(drop=True))
    return BacktestResult(detalle=detalle, por_horizonte=por_h, por_fase=por_fase, ranking=ranking)
