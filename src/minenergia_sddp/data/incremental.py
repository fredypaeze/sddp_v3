"""Actualizacion incremental de datos XM.

Detecta la ultima fecha disponible localmente, planifica solo las ventanas
faltantes (2-3 meses maximo por solicitud, para evitar timeouts de XM) y produce
un informe. La DESCARGA real requiere el catalogo maestro externo (ListadoMetricas)
y red; sin ellos, se entrega el plan y se documenta el bloqueo (no se declara
"tiempo real": XM tiene rezago).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

from minenergia_sddp.config.paths import external_sources_available, project_root

SYSTEM_DAILY = "data/processed/xm/system_historical_v3/system_daily_model_ready.csv"
HYDRO_DAILY = "data/processed/xm/hydro_system_historical_v1/hydro_system_daily_model_ready.csv"
MAX_DIAS_VENTANA = 60


def last_available_date(root: Path | None = None) -> dict[str, str]:
    root = root or project_root()
    out = {}
    for nombre, ruta, col in (("sistema", SYSTEM_DAILY, "fecha"), ("hidrologia", HYDRO_DAILY, "date")):
        df = pd.read_csv(root / ruta, usecols=[col], parse_dates=[col])
        out[nombre] = str(df[col].max().date())
    return out


def plan_missing_windows(desde: str, hasta: str, max_dias: int = MAX_DIAS_VENTANA) -> list[tuple[str, str]]:
    """Ventanas [inicio, fin] (<= max_dias) para cubrir (desde, hasta]."""
    d0 = datetime.strptime(desde, "%Y-%m-%d").date() + timedelta(days=1)
    d1 = datetime.strptime(hasta, "%Y-%m-%d").date()
    ventanas = []
    cur = d0
    while cur <= d1:
        fin = min(cur + timedelta(days=max_dias - 1), d1)
        ventanas.append((cur.isoformat(), fin.isoformat()))
        cur = fin + timedelta(days=1)
    return ventanas


@dataclass(frozen=True)
class UpdatePlan:
    ultima_fecha: dict[str, str]
    fecha_objetivo: str
    ventanas: list[tuple[str, str]]
    dias_faltantes: int
    puede_descargar: bool
    nota: str


def build_update_plan(hasta: str | None = None, root: Path | None = None) -> UpdatePlan:
    root = root or project_root()
    ult = last_available_date(root)
    ref = min(ult.values())  # la fuente mas atrasada manda
    objetivo = hasta or date.today().isoformat()
    ventanas = plan_missing_windows(ref, objetivo) if objetivo > ref else []
    d0 = datetime.strptime(ref, "%Y-%m-%d").date()
    d1 = datetime.strptime(objetivo, "%Y-%m-%d").date()
    faltantes = max((d1 - d0).days, 0)
    puede = external_sources_available()
    nota = ("Fuentes externas XM montadas: la descarga incremental puede ejecutarse con "
            "scripts/08 (execute=True)." if puede else
            "BLOQUEO: falta el catalogo maestro externo (ListadoMetricas) y/o red. "
            "El plan queda listo; la descarga real requiere montar las fuentes externas.")
    return UpdatePlan(ultima_fecha=ult, fecha_objetivo=objetivo, ventanas=ventanas,
                      dias_faltantes=faltantes, puede_descargar=puede, nota=nota)
