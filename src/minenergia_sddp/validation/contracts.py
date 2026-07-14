"""Contratos de datos esperados por dominio."""

from __future__ import annotations

CONTRACTS: dict[str, list[str]] = {
    "embalses": [
        "fecha",
        "escenario_id",
        "probabilidad",
        "codigo_embalse",
        "nombre_embalse",
        "region",
        "volumen_util",
        "unidad_volumen",
        "volumen_util_pct",
        "capacidad_util",
        "unidad_capacidad",
        "energia_almacenada_gwh",
        "dato_observado_o_proyectado",
        "fecha_actualizacion",
        "fuente",
    ],
    "aportes": [
        "fecha",
        "escenario_id",
        "codigo_embalse_o_sistema",
        "aporte",
        "unidad_aporte",
        "indice_aporte",
        "fase_enos",
        "oni",
        "dato_observado_o_proyectado",
        "fuente",
    ],
    "generacion": [
        "fecha",
        "codigo_recurso",
        "tipo_recurso",
        "generacion_gwh",
        "granularidad",
        "fuente",
    ],
    "demanda_otras_fuentes": [
        "fecha",
        "demanda_gwh",
        "solar_gwh",
        "eolica_gwh",
        "cogeneracion_gwh",
        "importacion_neta_gwh",
        "otras_gwh",
        "demanda_residual_gwh",
        "fuente",
    ],
    "termicas": [
        "fecha",
        "codigo_recurso",
        "nombre_recurso",
        "combustible",
        "despacho_central",
        "capacidad_mw",
        "disponibilidad_mw",
        "energia_maxima_periodo_gwh",
        "precio_oferta_cop_kwh",
        "estado",
        "fuente",
    ],
    "escenarios": [
        "escenario_id",
        "nombre_escenario",
        "fecha",
        "probabilidad",
        "aporte",
        "almacenamiento",
        "fase_enos",
        "oni",
        "fuente",
    ],
}


VARIABLE_STATUS = {
    "validada": "disponible y validada",
    "limitada": "disponible con limitaciones",
    "proxy_backtest": "proxy admisible solo para backtesting",
    "no_disponible": "no disponible",
    "prohibida": "prohibido estimarla sin informacion adicional",
}

