from __future__ import annotations

import csv
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from minenergia_sddp.data.xm_catalog import build_call_plan, build_metric_definitions
from minenergia_sddp.data.xm_checkpoints import is_completed, load_checkpoint, mark_completed, mark_error, sha256_file, versioned_path
from minenergia_sddp.data.xm_client import XMClient, payload_for_call, save_json
from minenergia_sddp.data.xm_pilot import derive_units, normalize_xm_response, read_normalized_outputs, schema_summary

PILOT_START = "2026-06-01"
PILOT_END = "2026-06-07"
MAX_HTTP_REQUESTS = 100
PILOT_ROOT = ROOT / "data/raw/xm/pilot_20260601_20260607"
RUN_ROOT = ROOT / "outputs/run_007"

PILOT_TARGETS = {
    "demanda_sin_diaria",
    "demanda_real_sistema_horaria",
    "generacion_real_total",
    "volumen_util_energia_sin",
    "capacidad_util_energia_sin",
    "aportes_energia_sin",
    "importaciones_energia_sistema",
    "exportaciones_energia_sistema",
    "generacion_real_por_recurso",
    "capacidad_efectiva_neta_recurso",
    "disponibilidad_real_recurso",
    "disponibilidad_comercial_recurso",
    "disponibilidad_declarada_recurso",
    "volumen_util_energia_embalse",
    "capacidad_util_energia_embalse",
    "aportes_energia_rio",
}


def pilot_calls() -> list[dict[str, Any]]:
    metrics = [metric for metric in build_metric_definitions(end_date=PILOT_END) if metric.target in PILOT_TARGETS]
    patched = []
    for metric in metrics:
        if metric.start_date:
            patched.append(metric.__class__(**{**metric.__dict__, "start_date": PILOT_START, "end_date": PILOT_END}))
        else:
            patched.append(metric)
    calls = build_call_plan(patched)
    calls = [call for call in calls if call["target"] in PILOT_TARGETS]
    if len(calls) > MAX_HTTP_REQUESTS:
        raise RuntimeError(f"El piloto excede {MAX_HTTP_REQUESTS} solicitudes: {len(calls)}")
    return calls


def pilot_output_dir(call: dict[str, Any]) -> Path:
    return PILOT_ROOT / call["target"]


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not fieldnames:
        keys: list[str] = []
        for row in rows:
            for key in row:
                if key not in keys:
                    keys.append(key)
        fieldnames = keys
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            item = {key: row.get(key, "") for key in fieldnames}
            for key, value in item.items():
                if isinstance(value, (list, dict)):
                    item[key] = json.dumps(value, ensure_ascii=False)
            writer.writerow(item)


def execute_pilot() -> dict[str, Any]:
    RUN_ROOT.mkdir(parents=True, exist_ok=True)
    PILOT_ROOT.mkdir(parents=True, exist_ok=True)
    calls = pilot_calls()
    client = XMClient(execute=True, retries=3, backoff_seconds=[2, 5, 10], timeout=60)
    request_log: list[dict[str, Any]] = []
    schemas: dict[str, Any] = {}
    units: list[dict[str, Any]] = []
    coverage: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    metric_failed: set[str] = set()
    network_blocked = False

    for index, call in enumerate(calls, start=1):
        if call["target"] in metric_failed:
            continue
        out_dir = pilot_output_dir(call)
        previous_error = prior_network_error(out_dir, call["call_id"])
        if previous_error:
            errors.append(
                {
                    "call_id": call["call_id"],
                    "target": call["target"],
                    "metric_id": call["metric_id"],
                    "entity": call["entity"],
                    "start_date": call["start_date"],
                    "end_date": call["end_date"],
                    "error": previous_error,
                }
            )
            request_log.append(
                {
                    "call_id": call["call_id"],
                    "MetricId": call["metric_id"],
                    "entity": call["entity"],
                    "target": call["target"],
                    "requested_entities": call.get("filter_values", []),
                    "start_date": call["start_date"],
                    "end_date": call["end_date"],
                    "http_status": "ERROR_PREVIOUS_NETWORK_BLOCK",
                    "duration_seconds": 0,
                    "records": 0,
                    "saved_path": "",
                    "sha256": "",
                    "attempt": 0,
                    "error": previous_error,
                }
            )
            network_blocked = True
            metric_failed.add(call["target"])
            continue
        if is_completed(out_dir, call["call_id"]):
            continue
        payload = payload_for_call(call)
        started = time.perf_counter()
        status = ""
        error_message = ""
        saved_path = ""
        sha = ""
        records = 0
        try:
            data = client.post_json(call["url"], payload)
            duration = time.perf_counter() - started
            raw_path = versioned_path(out_dir, call["call_id"], ".json")
            save_json(raw_path, data)
            normalized = derive_units(normalize_xm_response(data, call["periodicity"]), call["unit"])
            if normalized.empty:
                raise ValueError("Respuesta no vacia pero normalizacion produjo cero registros")
            norm_path = versioned_path(out_dir, f"{call['call_id']}__normalized", ".csv")
            normalized.to_csv(norm_path, index=False, encoding="utf-8")
            mark_completed(out_dir, call["call_id"], raw_path, rows=len(normalized))
            status = "OK"
            saved_path = str(raw_path.relative_to(ROOT))
            sha = sha256_file(raw_path)
            records = int(len(normalized))
            key = call["target"]
            schemas.setdefault(key, schema_summary(normalized, call["metric_id"], call["target"], call["unit"], call["entity"]))
            unit_summary = schema_summary(normalized, call["metric_id"], call["target"], call["unit"], call["entity"])
            units.append(
                {
                    "target": call["target"],
                    "metric_id": call["metric_id"],
                    "entity": call["entity"],
                    "unit_catalog": call["unit"],
                    "unit_inferred_by_magnitude": unit_summary.get("unit_inferred_by_magnitude", ""),
                    "min_value": unit_summary.get("min_value", ""),
                    "max_value": unit_summary.get("max_value", ""),
                    "negative_values": unit_summary.get("negative_values", ""),
                    "zero_values": unit_summary.get("zero_values", ""),
                }
            )
            coverage.append(
                {
                    "target": call["target"],
                    "metric_id": call["metric_id"],
                    "requested_entities": call.get("filter_count", 0) or 1,
                    "records": records,
                    "date_min": unit_summary.get("date_min", ""),
                    "date_max": unit_summary.get("date_max", ""),
                    "entity": call["entity"],
                }
            )
        except Exception as exc:
            duration = time.perf_counter() - started
            error_message = str(exc)
            status = "ERROR"
            if any(token in error_message.lower() for token in ["urlopen", "timed out", "temporary failure", "name resolution", "connection", "forbidden by", "network"]):
                network_blocked = True
            mark_error(out_dir, call["call_id"], error_message, {"payload": payload, "call": call})
            errors.append(
                {
                    "call_id": call["call_id"],
                    "target": call["target"],
                    "metric_id": call["metric_id"],
                    "entity": call["entity"],
                    "start_date": call["start_date"],
                    "end_date": call["end_date"],
                    "error": error_message,
                }
            )
            metric_failed.add(call["target"])
        request_log.append(
            {
                "call_id": call["call_id"],
                "MetricId": call["metric_id"],
                "entity": call["entity"],
                "target": call["target"],
                "requested_entities": call.get("filter_values", []),
                "start_date": call["start_date"],
                "end_date": call["end_date"],
                "http_status": status,
                "duration_seconds": round(duration, 3),
                "records": records,
                "saved_path": saved_path,
                "sha256": sha,
                "attempt": 1,
                "error": error_message,
            }
        )
        if index < len(calls):
            time.sleep(1)

    frames = read_normalized_outputs(PILOT_ROOT)
    balance_md = build_balance_report(frames)
    hydro_md = build_hydro_report(frames)
    decision = decide_status(request_log, errors, schemas, network_blocked)

    write_csv(RUN_ROOT / "metricas_piloto.csv", request_log)
    (RUN_ROOT / "esquemas_respuestas.json").write_text(json.dumps(schemas, indent=2, ensure_ascii=False), encoding="utf-8")
    write_csv(RUN_ROOT / "validacion_unidades.csv", units)
    write_csv(RUN_ROOT / "validacion_cobertura.csv", coverage)
    write_csv(RUN_ROOT / "errores_piloto.csv", errors, ["call_id", "target", "metric_id", "entity", "start_date", "end_date", "error"])
    (RUN_ROOT / "validacion_balance.md").write_text(balance_md + "\n\n" + hydro_md, encoding="utf-8")
    (RUN_ROOT / "comando_ejecutado.txt").write_text("python scripts/11_ejecutar_piloto_xm.py\n", encoding="utf-8")
    summary = {
        "status": decision,
        "period": [PILOT_START, PILOT_END],
        "http_limit": MAX_HTTP_REQUESTS,
        "requests_planned": len(calls),
        "requests_made": len(request_log),
        "requests_ok": sum(1 for row in request_log if row["http_status"] == "OK"),
        "requests_failed": sum(1 for row in request_log if str(row["http_status"]).startswith("ERROR")),
        "metrics_ok": sorted({row["target"] for row in request_log if row["http_status"] == "OK"}),
        "metrics_failed": sorted({row["target"] for row in request_log if str(row["http_status"]).startswith("ERROR")}),
        "pilot_root": str(PILOT_ROOT.relative_to(ROOT)),
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    (RUN_ROOT / "resumen_piloto.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    (RUN_ROOT / "conclusion_piloto.md").write_text(build_conclusion(summary, errors, schemas), encoding="utf-8")
    return summary


def decide_status(request_log: list[dict[str, Any]], errors: list[dict[str, Any]], schemas: dict[str, Any], network_blocked: bool) -> str:
    if network_blocked and not any(row["http_status"] == "OK" for row in request_log):
        return "PILOT_BLOCKED_NETWORK"
    if not any(row["http_status"] == "OK" for row in request_log):
        return "PILOT_BLOCKED_API"
    essential = {"demanda_sin_diaria", "generacion_real_total", "volumen_util_energia_sin", "aportes_energia_sin"}
    if not essential.issubset(set(schemas)):
        return "PILOT_BLOCKED_SCHEMA"
    if errors:
        return "PILOT_VALIDATED_WITH_FIXES"
    if "disponibilidad_declarada_recurso" in schemas:
        return "PILOT_VALIDATED_WITH_FIXES"
    return "PILOT_VALIDATED"


def daily_sum(frame, value_col="Value_GWh"):
    import pandas as pd

    if frame is None or frame.empty or value_col not in frame.columns:
        return pd.DataFrame(columns=["day", value_col])
    temp = frame.copy()
    temp["day"] = pd.to_datetime(temp["Date"], errors="coerce").dt.date.astype(str)
    return temp.groupby("day", as_index=False)[value_col].sum()


def build_balance_report(frames: dict[str, Any]) -> str:
    import pandas as pd

    pieces = {}
    mapping = {
        "gene_sistema_gwh": "generacion_real_total",
        "gene_recurso_gwh": "generacion_real_por_recurso",
        "demasin_gwh": "demanda_sin_diaria",
        "demareal_gwh": "demanda_real_sistema_horaria",
        "impo_gwh": "importaciones_energia_sistema",
        "expo_gwh": "exportaciones_energia_sistema",
    }
    for out_col, target in mapping.items():
        col = daily_sum(frames.get(target)).rename(columns={"Value_GWh": out_col, "day": "fecha"})
        pieces[out_col] = col
    base = None
    for col in pieces.values():
        base = col if base is None else base.merge(col, on="fecha", how="outer")
    if base is None or base.empty or "fecha" not in base.columns:
        return "# Validacion de balance electrico\n\nNo hay datos suficientes para balance."
    for col in mapping:
        if col not in base.columns:
            base[col] = 0.0
    base["dif_gene_sistema_demasin_gwh"] = base["gene_sistema_gwh"] - base["demasin_gwh"]
    base["dif_rel_gene_sistema_demasin"] = base["dif_gene_sistema_demasin_gwh"] / base["demasin_gwh"].replace({0: pd.NA})
    lines = [
        "# Validacion de balance electrico",
        "",
        "Comparacion diagnostica; no se fuerza igualdad porque las definiciones pueden incluir perdidas, generacion no despachada centralmente, autogeneracion, cogeneracion, consumos auxiliares e intercambios.",
        "",
        "```csv\n" + base.round(6).to_csv(index=False) + "```",
    ]
    return "\n".join(lines)


def build_hydro_report(frames: dict[str, Any]) -> str:
    import pandas as pd

    vol = daily_sum(frames.get("volumen_util_energia_sin"))
    cap = daily_sum(frames.get("capacidad_util_energia_sin"))
    if vol.empty or cap.empty:
        return "# Validacion hidrologica\n\nNo hay volumen/capacidad sistema suficientes."
    merged = vol.merge(cap, on="day", suffixes=("_volumen", "_capacidad"))
    merged["porcentaje_energetico"] = merged["Value_GWh_volumen"] / merged["Value_GWh_capacidad"]
    lines = [
        "# Validacion hidrologica",
        "",
        "El porcentaje energetico se calcula como VoluUtilDiarEner / CapaUtilDiarEner. Sirve para contrastar contra embalses_manu, sin exigir correspondencia exacta.",
        "",
        "```csv\n" + merged.round(6).to_csv(index=False) + "```",
    ]
    return "\n".join(lines)


def build_conclusion(summary: dict[str, Any], errors: list[dict[str, Any]], schemas: dict[str, Any]) -> str:
    status = summary["status"]
    dispo = schemas.get("disponibilidad_declarada_recurso", {})
    dispo_note = "No se recibio esquema de DispoDeclarada."
    if dispo:
        dispo_note = (
            f"DispoDeclarada catalogada como {dispo.get('unit_catalog')}; "
            f"magnitud inferida: {dispo.get('unit_inferred_by_magnitude')}; "
            "no se corrige automaticamente el catalogo."
        )
    return f"""# Conclusion piloto XM

Estado: **{status}**

- Solicitudes planeadas: {summary['requests_planned']}
- Solicitudes realizadas: {summary['requests_made']}
- Exitosas: {summary['requests_ok']}
- Fallidas: {summary['requests_failed']}
- Periodo: {summary['period'][0]} a {summary['period'][1]}

## DispoDeclarada

{dispo_note}

## Errores

{json.dumps(errors, ensure_ascii=False, indent=2)}

No se inicia ninguna descarga adicional despues de esta decision.
"""


def prior_network_error(out_dir: Path, call_id: str) -> str:
    checkpoint = load_checkpoint(out_dir)
    for item in checkpoint.get("errors", []):
        if item.get("call_id") != call_id:
            continue
        error = str(item.get("error", ""))
        if any(token in error.lower() for token in ["winerror 10013", "socket no permitido", "urlopen error", "connection", "network"]):
            return error
    return ""


def main() -> int:
    summary = execute_pilot()
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
