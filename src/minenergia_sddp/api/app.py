"""API REST (FastAPI) para consultar los resultados del modelo SDDP + CVaR.

Sirve, en solo lectura, los artefactos reproducibles de outputs/run_*/ y metadatos
de datos. No ejecuta el modelo (eso lo hacen los scripts); expone lo ya calculado.

Ejecucion:
    PYTHONPATH=src .venv/bin/uvicorn minenergia_sddp.api.app:app --port 8900
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException

from minenergia_sddp.config.paths import project_root
from minenergia_sddp.dispatch.datasets import load_daily

app = FastAPI(title="SDDP + CVaR — MinEnergia Colombia", version="v001",
              description="Consulta de resultados del modelo hidrotermico estocastico. "
                          "Todas las cifras provienen de ejecuciones reproducibles (outputs/run_*).")

ROOT = project_root()
RUNS = {
    "sddp": "run_024_v001", "sensibilidad": "run_025_v001", "pronostico": "run_022_v001",
    "escenarios": "run_023_v001", "backtesting": "run_026_v001",
}


def _load_json(run: str, nombre: str = "resumen.json") -> dict[str, Any]:
    p = ROOT / "outputs" / RUNS.get(run, run) / nombre
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"Aun no ejecutado: falta {p.relative_to(ROOT)}. "
                                                    f"Corre el script correspondiente.")
    return json.loads(p.read_text(encoding="utf-8"))


@app.get("/estado")
def estado() -> dict:
    daily = load_daily()
    ult = str(daily["fecha"].iloc[-1].date())
    return {"servicio": "SDDP+CVaR MinEnergia", "version": "v001",
            "ultima_fecha_datos": ult, "dias_historicos": len(daily),
            "estado_datos": "actualizacion programada con rezago (XM no es tiempo real)",
            "runs_disponibles": {k: (ROOT / "outputs" / v / "resumen.json").exists()
                                 for k, v in RUNS.items()}}


@app.get("/ultima_actualizacion")
def ultima_actualizacion() -> dict:
    daily = load_daily()
    return {"ultima_fecha_datos": str(daily["fecha"].iloc[-1].date()),
            "fuente": "XM (pydataxm)", "tipo": "dato con rezago, no streaming"}


@app.get("/resultados")
def resultados() -> dict:
    return _load_json("sddp")


@app.get("/riesgo")
def riesgo() -> dict:
    r = _load_json("sddp")
    pol = r.get("politica", {})
    return {"horizonte": r.get("horizonte"), "fase": r.get("fase"),
            "E_costo_billones_cop": pol.get("E_costo_billones_cop"),
            "VaR_billones_cop": pol.get("VaR_billones_cop"),
            "CVaR_billones_cop": pol.get("CVaR_billones_cop"),
            "alpha": pol.get("alpha"), "prob_ens": pol.get("prob_ens_horizonte")}


@app.get("/recomendacion")
def recomendacion() -> dict:
    r = _load_json("sddp")
    return {"horizonte": r.get("horizonte"), "fase": r.get("fase"),
            "por_etapa": r.get("politica", {}).get("por_etapa", [])}


@app.get("/generacion")
def generacion() -> dict:
    r = _load_json("sddp")
    return {"por_etapa": r.get("politica", {}).get("por_etapa", [])}


@app.get("/sensibilidad/lambda")
def sensibilidad_lambda() -> dict:
    r = _load_json("sensibilidad")
    tabla = r.get("estres", {}).get("tabla", [])
    return {"base": r.get("base"), "estres_lambda": [t for t in tabla if t.get("alpha") == 0.95]}


@app.get("/sensibilidad/alpha")
def sensibilidad_alpha() -> dict:
    r = _load_json("sensibilidad")
    tabla = r.get("estres", {}).get("tabla", [])
    return {"estres_alpha": [t for t in tabla if t.get("lambda") == 0.75]}


@app.get("/escenarios")
def escenarios() -> dict:
    return _load_json("escenarios", "modelo_parametros.json")


@app.get("/pronostico")
def pronostico() -> dict:
    return _load_json("pronostico")


@app.get("/backtesting")
def backtesting() -> dict:
    return _load_json("backtesting")


@app.get("/embalses")
def embalses() -> dict:
    from minenergia_sddp.topology.catalog import build_catalog
    cat = build_catalog()
    cols = ["codigo", "region", "cuenca", "tipo", "capacidad_media_gwh", "aguas_abajo", "confianza"]
    return {"n": len(cat), "embalses": cat[[c for c in cols if c in cat.columns]]
            .round(1).to_dict("records")}
