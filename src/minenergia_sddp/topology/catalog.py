"""Catalogo de topologia hidraulica: une atributos curados con datos XM.

Cruza `config/model/topologia_hidraulica.json` (cuenca/region/tipo/cascadas, con
confianza y validacion por entidad) con el dataset por embalse (capacidad/volumen
energeticos observados) para producir un catalogo trazable. Verifica que las
entidades del config coincidan con las de los datos y expone las relaciones de
cascada como aristas (origen -> destino) con su metadato.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from minenergia_sddp.config.paths import project_root

TOPO_CONFIG = "config/model/topologia_hidraulica.json"
RESERVOIR_DAILY = "data/processed/xm/hydro_reservoir_historical_v2/hydro_reservoir_daily_model_ready.csv"


def load_topologia(path: str | Path | None = None) -> dict:
    p = Path(path) if path else project_root() / TOPO_CONFIG
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def build_catalog(root: Path | None = None) -> pd.DataFrame:
    root = root or project_root()
    topo = load_topologia()
    emb = pd.DataFrame(topo["embalses"])

    res = pd.read_csv(root / RESERVOIR_DAILY,
                      usecols=["reservoir_code", "capacidad_util_energia_gwh",
                               "volumen_util_energia_gwh", "porcentaje_volumen_util_oficial"])
    agg = res.groupby("reservoir_code").agg(
        capacidad_media_gwh=("capacidad_util_energia_gwh", "mean"),
        volumen_medio_gwh=("volumen_util_energia_gwh", "mean"),
        pct_medio=("porcentaje_volumen_util_oficial", "mean"),
    ).reset_index().rename(columns={"reservoir_code": "codigo"})

    cat = emb.merge(agg, on="codigo", how="left")
    cat["fuente"] = topo["meta"]["fuente_default"]
    cat["validacion"] = topo["meta"]["validacion_default"]
    cat["en_datos"] = cat["capacidad_media_gwh"].notna()
    return cat


def relations(root: Path | None = None) -> pd.DataFrame:
    """Aristas de cascada origen->destino (aguas_abajo) con metadato."""
    topo = load_topologia()
    filas = []
    for e in topo["embalses"]:
        destino = e.get("aguas_abajo")
        if destino:
            filas.append({"origen": e["codigo"], "destino": destino, "tipo_relacion": "aguas_abajo",
                          "fuente": topo["meta"]["fuente_default"],
                          "confianza": e.get("confianza", "baja"),
                          "validacion": topo["meta"]["validacion_default"]})
    return pd.DataFrame(filas)


def check_consistency(root: Path | None = None) -> dict:
    """Verifica cobertura config vs datos y coherencia de las cascadas."""
    root = root or project_root()
    cat = build_catalog(root)
    topo = load_topologia()
    codigos = set(cat["codigo"])
    rel = relations(root)
    destinos_validos = all(d in codigos for d in rel["destino"]) if len(rel) else True
    return {
        "n_embalses_config": len(cat),
        "n_embalses_en_datos": int(cat["en_datos"].sum()),
        "faltantes_en_datos": sorted(cat.loc[~cat["en_datos"], "codigo"].tolist()),
        "n_relaciones_cascada": int(len(rel)),
        "destinos_de_cascada_validos": bool(destinos_validos),
    }
