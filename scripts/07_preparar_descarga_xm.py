from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from minenergia_sddp.data.xm_catalog import DEFAULT_PLAN_END_DATE, create_download_configs, write_csv


def pydataxm_status() -> dict[str, str | bool]:
    spec = importlib.util.find_spec("pydataxm")
    status: dict[str, str | bool] = {"installed": bool(spec), "version": "", "known_issue": ""}
    if spec:
        try:
            import pydataxm  # type: ignore

            status["version"] = getattr(pydataxm, "__version__", "unknown")
        except Exception as exc:  # pragma: no cover - environment dependent
            status["version"] = f"import_error: {type(exc).__name__}: {exc}"
    status["known_issue"] = (
        "pydataxm 0.3.17 puede fallar con freq='M' y pandas >=2.2 por alias mensual deprecado. "
        "Si se decide usar pydataxm, aplicar parche manual documentado; este paquete no modifica el entorno."
    )
    return status


def metric_gap_text(metrics: list[dict]) -> str:
    missing = [m for m in metrics if m["status"] != "FOUND_EXACT"]
    if not missing:
        return "# Brechas de metricas XM\n\nTodas las metricas objetivo fueron identificadas en el catalogo local.\n"
    lines = ["# Brechas de metricas XM", ""]
    for item in missing:
        lines.append(f"- `{item['target']}`: {item['status']} para `{item['metric_id']}` / `{item['entity']}`.")
    return "\n".join(lines) + "\n"


def dry_run_text(metrics: list[dict], calls: list[dict], plan: dict) -> str:
    lines = [
        "DRY RUN - no se hicieron solicitudes HTTP",
        f"Metricas identificadas: {sum(1 for m in metrics if m['status'] == 'FOUND_EXACT')}/{len(metrics)}",
        f"Llamadas estimadas: {len(calls)}",
        f"Fin usado para planificacion: {plan['default_end_date_for_dry_run']}",
        "Directorios de salida:",
    ]
    for domain in ["demanda", "generacion", "recursos", "disponibilidad", "embalses", "aportes", "intercambios"]:
        lines.append(f"- data/raw/xm/{domain}/")
    lines.append("Metricas:")
    for metric in metrics:
        lines.append(f"- {metric['target']}: {metric['metric_id']} | {metric['entity']} | {metric['periodicity']} | {metric['unit']} | {metric['status']}")
    return "\n".join(lines) + "\n"


def main() -> int:
    result = create_download_configs(end_date=DEFAULT_PLAN_END_DATE)
    metrics = result["metrics"]
    calls = result["calls"]
    plan = result["plan"]
    out = ROOT / "outputs/run_006"
    out.mkdir(parents=True, exist_ok=True)

    write_csv(out / "metricas_identificadas.csv", metrics)
    write_csv(out / "plan_llamadas.csv", calls)
    summary = {
        "pydataxm": pydataxm_status(),
        "metrics_total": len(metrics),
        "metrics_found_exact": sum(1 for metric in metrics if metric["status"] == "FOUND_EXACT"),
        "estimated_calls": len(calls),
        "dry_run_end_date": DEFAULT_PLAN_END_DATE,
        "resource_estimates": {
            "central_hydrothermal_resources": len(plan["resources"]["central_hydrothermal_resources"]),
            "active_embalse_names": len(plan["resources"]["active_embalse_names"]),
            "active_rio_names": len(plan["resources"]["active_rio_names"]),
        },
        "execute_required": True,
        "http_requests_made": 0,
    }
    (out / "resumen_plan.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "brechas_metricas.md").write_text(metric_gap_text(metrics), encoding="utf-8")
    (out / "resultado_dry_run.txt").write_text(dry_run_text(metrics, calls, plan), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

