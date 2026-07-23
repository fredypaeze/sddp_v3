"""Backtesting y pronostico a 6 meses de aportes del SIN condicionado a ENOS.

Selecciona el mejor modelo por MAE en backtesting de origen movil y produce el
pronostico de los proximos 6 meses (GWh/dia). Guarda outputs/run_022_v001/.

Uso: PYTHONPATH=src python scripts/22_pronostico_aportes.py [--horizon 6]
"""

from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

from minenergia_sddp.config.paths import project_root
from minenergia_sddp.forecasting.aportes import (
    ONI, backtest, forecast_climatology, forecast_sarimax, forecast_seasonal_naive,
    load_monthly_aportes,
)
from minenergia_sddp.reporting.run import new_run

HYD = "data/processed/xm/hydro_system_historical_v1/hydro_system_daily_model_ready.csv"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--horizon", type=int, default=6)
    args = ap.parse_args()
    root = project_root()

    data = load_monthly_aportes()
    bt = backtest(data, horizon=args.horizon, min_train=72, step=3)
    best = bt.ranking.iloc[0]["modelo"]

    # pronostico con TODO el historico y el mejor modelo
    last = data.index[-1]
    fut_index = pd.date_range(last + pd.DateOffset(months=1), periods=args.horizon, freq="MS")
    oni = pd.read_csv(root / ONI)
    fut_oni = []
    for ts in fut_index:
        row = oni[(oni.anio == ts.year) & (oni.mes == ts.month)]
        fut_oni.append(float(row["oni"].iloc[0]) if len(row) else float(data["oni"].iloc[-1]))
    fut_oni = np.array(fut_oni)

    if best == "sarimax_oni":
        yhat = forecast_sarimax(data, fut_index, exog_col="oni", future_exog=fut_oni)
    elif best == "sarimax":
        yhat = forecast_sarimax(data, fut_index)
    elif best == "persistencia_estacional":
        yhat = forecast_seasonal_naive(data, fut_index)
    else:
        yhat = forecast_climatology(data, fut_index)

    def fase(o):
        return "nino" if o >= 0.5 else ("nina" if o <= -0.5 else "neutral")

    pron = pd.DataFrame({"fecha": fut_index, "aportes_gwh_dia_pred": yhat,
                         "oni": fut_oni, "fase_enos": [fase(o) for o in fut_oni]})

    carpeta = new_run("run_022_v001", inputs=[root / HYD, root / ONI],
                      descripcion=f"Pronostico de aportes a {args.horizon} meses. Mejor modelo: {best}.")
    bt.ranking.to_csv(carpeta / "ranking_modelos.csv", index=False)
    bt.por_horizonte.to_csv(carpeta / "metricas_por_horizonte.csv", index=False)
    bt.por_fase.to_csv(carpeta / "metricas_por_fase.csv", index=False)
    pron.to_csv(carpeta / "pronostico_aportes_6m.csv", index=False)
    (carpeta / "resumen.json").write_text(json.dumps({
        "mejor_modelo": best,
        "MAE_mejor": float(bt.ranking.iloc[0]["MAE"]),
        "ranking": bt.ranking[["modelo", "MAE", "RMSE", "sesgo", "sMAPE"]].to_dict("records"),
        "aportes_por_fase_hist": data.groupby("fase_enos")["aportes_gwh_dia"].mean().round(2).to_dict(),
        "pronostico": pron.assign(fecha=pron.fecha.astype(str)).to_dict("records"),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Mejor modelo: {best} (MAE {bt.ranking.iloc[0]['MAE']:.1f} GWh/dia)")
    print(pron.assign(fecha=pron.fecha.dt.strftime("%Y-%m")).to_string(index=False))
    print("Salida:", carpeta.relative_to(root))


if __name__ == "__main__":
    main()
