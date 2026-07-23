"""Plan de actualizacion incremental de datos XM.

Detecta la ultima fecha local, calcula las ventanas faltantes hasta la fecha
objetivo y produce un informe. Ejecuta la descarga solo si las fuentes externas
estan montadas (execute controlado); si no, entrega el plan y documenta el bloqueo.

Uso: PYTHONPATH=src python scripts/27_actualizar_incremental.py [--hasta 2026-07-23]
"""

from __future__ import annotations

import argparse
import json

from minenergia_sddp.config.paths import project_root
from minenergia_sddp.data.incremental import build_update_plan
from minenergia_sddp.reporting.run import new_run


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hasta", default=None, help="fecha objetivo YYYY-MM-DD (por defecto hoy)")
    args = ap.parse_args()
    root = project_root()

    plan = build_update_plan(hasta=args.hasta)
    carpeta = new_run("run_027_v001", descripcion="Plan de actualizacion incremental XM.")
    informe = {
        "ultima_fecha_local": plan.ultima_fecha,
        "fecha_objetivo": plan.fecha_objetivo,
        "dias_faltantes": plan.dias_faltantes,
        "ventanas_a_descargar": plan.ventanas,
        "puede_descargar": plan.puede_descargar,
        "nota": plan.nota,
        "tipo_dato": "actualizacion programada con rezago (XM no es tiempo real)",
    }
    (carpeta / "plan_actualizacion.json").write_text(json.dumps(informe, ensure_ascii=False, indent=2),
                                                     encoding="utf-8")
    print("Ultima fecha local:", plan.ultima_fecha)
    print("Objetivo:", plan.fecha_objetivo, "| dias faltantes:", plan.dias_faltantes)
    print("Ventanas:", plan.ventanas)
    print("Puede descargar:", plan.puede_descargar)
    print("Nota:", plan.nota)
    print("Salida:", carpeta.relative_to(root))


if __name__ == "__main__":
    main()
