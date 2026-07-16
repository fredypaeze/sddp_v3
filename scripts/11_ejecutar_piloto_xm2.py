from __future__ import annotations

import argparse
import csv
import ctypes
import json
import os
import subprocess
import sys
import time
import urllib.error
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from minenergia_sddp.data.xm_catalog import build_call_plan, build_metric_definitions
from minenergia_sddp.data.xm_checkpoints import (
    is_completed,
    load_checkpoint,
    mark_completed,
    mark_error,
    sha256_file,
    versioned_path,
)
from minenergia_sddp.data.xm_client import XMClient, payload_for_call, save_json
from minenergia_sddp.data.xm_pilot import derive_units_contextual, normalize_xm_response, read_normalized_outputs, schema_summary

PILOT_START = "2026-06-01"
PILOT_END = "2026-06-07"
MAX_HTTP_REQUESTS = 100
ORIGINAL_PILOT_ROOT = ROOT / "data/raw/xm/pilot_20260601_20260607"
PILOT_ROOT = ROOT / "data/raw/xm/pilot_20260601_20260607_retry1"
RUN_ROOT = ROOT / "outputs/run_008"

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

NETWORK_ERROR_TOKENS = (
    "winerror 10013",
    "socket no permitido",
    "forbidden by its access permissions",
    "permiso de acceso",
    "permissionerror",
    "permission denied",
    "bloqueo local",
    "local block",
    "blocked by local",
    "urlopen error [winerror 10013]",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Reintento seguro del piloto XM 2026-06-01 a 2026-06-07. "
            "Por defecto no abre red; HTTP requiere --execute."
        )
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Muestra el plan y registra run_008 sin abrir sockets.")
    mode.add_argument("--execute", action="store_true", help="Autoriza solicitudes HTTPS del piloto retry1.")
    parser.add_argument(
        "--retry-network-errors",
        action="store_true",
        help="Ignora solo errores previos de red/local socket para reintentar esos lotes.",
    )
    parser.add_argument("--resume", action="store_true", help="Continua sobre checkpoints existentes en retry1 sin repetir exitos.")
    parser.add_argument(
        "--max-http-requests",
        type=positive_int,
        default=MAX_HTTP_REQUESTS,
        help="Limite solicitado de HTTP; el limite efectivo nunca supera 100.",
    )
    return parser


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("--max-http-requests debe ser mayor que cero")
    return parsed


def effective_http_limit(value: int) -> int:
    return min(MAX_HTTP_REQUESTS, value)


def pilot_calls() -> list[dict[str, Any]]:
    metrics = [metric for metric in build_metric_definitions(end_date=PILOT_END) if metric.target in PILOT_TARGETS]
    patched = []
    for metric in metrics:
        if metric.start_date:
            patched.append(metric.__class__(**{**metric.__dict__, "start_date": PILOT_START, "end_date": PILOT_END}))
        else:
            patched.append(metric)
    calls = [call for call in build_call_plan(patched) if call["target"] in PILOT_TARGETS]
    if len(calls) > MAX_HTTP_REQUESTS:
        raise RuntimeError(f"El piloto excede {MAX_HTTP_REQUESTS} solicitudes: {len(calls)}")
    return calls


def pilot_output_dir(call: dict[str, Any], root: Path = PILOT_ROOT) -> Path:
    return root / call["target"]


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> Path:
    target = report_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not fieldnames:
        keys: list[str] = []
        for row in rows:
            for key in row:
                if key not in keys:
                    keys.append(key)
        fieldnames = keys
    with target.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            item = {key: row.get(key, "") for key in fieldnames}
            for key, value in item.items():
                if isinstance(value, (list, dict)):
                    item[key] = json.dumps(value, ensure_ascii=False)
            writer.writerow(item)
    return target


def write_text_report(path: Path, text: str) -> Path:
    target = report_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target


def write_json_report(path: Path, data: Any) -> Path:
    return write_text_report(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def report_path(path: Path) -> Path:
    if not path.exists():
        return path
    return versioned_path(path.parent, path.stem, path.suffix)


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def is_local_socket_block_message(message: str) -> bool:
    lowered = message.lower()
    if any(token in lowered for token in NETWORK_ERROR_TOKENS):
        return True
    if "urlopen error" in lowered and ("socket" in lowered or "permission" in lowered or "permiso" in lowered):
        return True
    if "socket" in lowered and ("permission" in lowered or "permiso" in lowered or "deneg" in lowered):
        return True
    return False


def is_network_block_error(error: object) -> bool:
    if isinstance(error, PermissionError):
        return True
    if isinstance(error, urllib.error.URLError):
        reason = getattr(error, "reason", "")
        return is_network_block_error(reason) or is_local_socket_block_message(str(error))
    return is_local_socket_block_message(str(error))


def checkpoint_errors(out_dir: Path, call_id: str) -> list[dict[str, Any]]:
    checkpoint = load_checkpoint(out_dir)
    return [item for item in checkpoint.get("errors", []) if item.get("call_id") == call_id]


def completed_source(call: dict[str, Any]) -> str:
    if is_completed(pilot_output_dir(call, ORIGINAL_PILOT_ROOT), call["call_id"]):
        return "run_007"
    if is_completed(pilot_output_dir(call, PILOT_ROOT), call["call_id"]):
        return "retry1"
    return ""


def prior_errors(call: dict[str, Any], include_retry: bool) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    for item in checkpoint_errors(pilot_output_dir(call, ORIGINAL_PILOT_ROOT), call["call_id"]):
        errors.append({"source": "run_007", **item})
    if include_retry:
        for item in checkpoint_errors(pilot_output_dir(call, PILOT_ROOT), call["call_id"]):
            errors.append({"source": "retry1", **item})
    return errors


def classify_prior_errors(call: dict[str, Any], include_retry: bool) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    network: list[dict[str, Any]] = []
    other: list[dict[str, Any]] = []
    for item in prior_errors(call, include_retry):
        (network if is_network_block_error(item.get("error", "")) else other).append(item)
    return network, other


def build_execution_plan(
    calls: list[dict[str, Any]],
    *,
    retry_network_errors: bool,
    resume: bool,
    max_http_requests: int,
) -> dict[str, Any]:
    limit = effective_http_limit(max_http_requests)
    planned: list[dict[str, Any]] = []
    skipped_completed: list[dict[str, Any]] = []
    blocked_network: list[dict[str, Any]] = []
    blocked_other: list[dict[str, Any]] = []
    ignored_network: list[dict[str, Any]] = []

    for call in calls:
        source = completed_source(call)
        if source:
            skipped_completed.append({**call, "skip_reason": f"completed_in_{source}"})
            continue
        network_errors, other_errors = classify_prior_errors(call, include_retry=resume)
        if other_errors:
            blocked_other.append({**call, "prior_errors": other_errors})
            continue
        if network_errors and not retry_network_errors:
            blocked_network.append({**call, "prior_errors": network_errors})
            continue
        if network_errors:
            ignored_network.extend({**call, "prior_error": item} for item in network_errors)
        planned.append(call)

    limited = planned[:limit]
    truncated = planned[limit:]
    return {
        "http_limit": limit,
        "total_calls": len(calls),
        "planned": limited,
        "planned_before_limit": planned,
        "truncated_by_limit": truncated,
        "skipped_completed": skipped_completed,
        "blocked_network": blocked_network,
        "blocked_other": blocked_other,
        "ignored_network": ignored_network,
    }


def exact_command_line(argv: list[str] | None = None) -> str:
    override = os.environ.get("XM_PILOT_COMMAND_LINE")
    if override:
        return override
    if os.name == "nt":
        try:
            ctypes.windll.kernel32.GetCommandLineW.restype = ctypes.c_wchar_p
            command = ctypes.windll.kernel32.GetCommandLineW()
            if command:
                return command
        except Exception:
            pass
    args = list(sys.argv if argv is None else [str(Path(__file__).relative_to(ROOT)), *argv])
    return subprocess.list2cmdline([Path(sys.executable).name, *args])


def checkpoint_paths(root: Path = PILOT_ROOT) -> list[str]:
    if not root.exists():
        return []
    return sorted(display_path(path) for path in root.glob("**/_checkpoint.json"))


def summarize_plan(args: argparse.Namespace, command_line: str, calls: list[dict[str, Any]], plan: dict[str, Any], mode: str) -> dict[str, Any]:
    return {
        "command": command_line,
        "mode": mode,
        "retry_network_errors": bool(args.retry_network_errors),
        "resume": bool(args.resume),
        "ignored_previous_network_errors": len(plan["ignored_network"]),
        "period": [PILOT_START, PILOT_END],
        "metrics": sorted({call["target"] for call in calls}),
        "http_limit": plan["http_limit"],
        "requests_total": plan["total_calls"],
        "requests_planned": len(plan["planned"]),
        "requests_planned_before_limit": len(plan["planned_before_limit"]),
        "requests_truncated_by_limit": len(plan["truncated_by_limit"]),
        "requests_skipped_completed": len(plan["skipped_completed"]),
        "requests_made": 0,
        "responses_valid": 0,
        "errors": len(plan["blocked_network"]) + len(plan["blocked_other"]),
        "checkpoints": checkpoint_paths(),
        "data_dir": display_path(PILOT_ROOT),
        "reports_dir": display_path(RUN_ROOT),
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }


def print_plan(summary: dict[str, Any]) -> None:
    print("Piloto XM retry1")
    print(f"Modo: {summary['mode']}")
    print(f"Fechas: {summary['period'][0]} a {summary['period'][1]}")
    print(f"Metricas: {len(summary['metrics'])}")
    print(f"Solicitudes planeadas: {summary['requests_planned']}")
    print(f"Solicitudes totales del piloto: {summary['requests_total']}")
    print(f"Maximo permitido: {summary['http_limit']}")
    print(f"Directorio de datos: {summary['data_dir']}")
    print(f"Directorio de reportes: {summary['reports_dir']}")
    print(f"Errores previos de red ignorados: {summary['ignored_previous_network_errors']}")


def register_run(
    *,
    summary: dict[str, Any],
    request_log: list[dict[str, Any]],
    errors: list[dict[str, Any]],
    plan: dict[str, Any],
) -> None:
    RUN_ROOT.mkdir(parents=True, exist_ok=True)
    write_text_report(RUN_ROOT / "comando_ejecutado.txt", summary["command"] + "\n")
    write_json_report(RUN_ROOT / "resumen_piloto_retry.json", summary)
    write_csv(RUN_ROOT / "plan_solicitudes.csv", plan_rows(plan))
    write_csv(RUN_ROOT / "metricas_piloto.csv", request_log)
    write_csv(
        RUN_ROOT / "errores_piloto.csv",
        errors,
        ["call_id", "target", "metric_id", "entity", "start_date", "end_date", "error", "source"],
    )
    write_csv(RUN_ROOT / "checkpoints_piloto.csv", [{"checkpoint": item} for item in summary.get("checkpoints", [])])


def plan_rows(plan: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, status in (
        ("planned", "PLANNED_HTTP"),
        ("truncated_by_limit", "SKIPPED_LIMIT"),
        ("skipped_completed", "SKIPPED_COMPLETED"),
        ("blocked_network", "BLOCKED_PREVIOUS_NETWORK_ERROR"),
        ("blocked_other", "BLOCKED_PREVIOUS_NON_NETWORK_ERROR"),
    ):
        for call in plan[key]:
            rows.append(
                {
                    "status": status,
                    "call_id": call["call_id"],
                    "target": call["target"],
                    "metric_id": call["metric_id"],
                    "entity": call["entity"],
                    "start_date": call["start_date"],
                    "end_date": call["end_date"],
                }
            )
    return rows


def dry_run(args: argparse.Namespace, command_line: str) -> dict[str, Any]:
    calls = pilot_calls()
    plan = build_execution_plan(
        calls,
        retry_network_errors=args.retry_network_errors,
        resume=args.resume,
        max_http_requests=args.max_http_requests,
    )
    summary = summarize_plan(args, command_line, calls, plan, "dry-run")
    print_plan(summary)
    register_run(summary=summary, request_log=[], errors=blocked_errors(plan), plan=plan)
    return summary


def blocked_errors(plan: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for call in [*plan["blocked_network"], *plan["blocked_other"]]:
        prior = call.get("prior_errors", [{}])[0]
        rows.append(
            {
                "call_id": call["call_id"],
                "target": call["target"],
                "metric_id": call["metric_id"],
                "entity": call["entity"],
                "start_date": call["start_date"],
                "end_date": call["end_date"],
                "error": prior.get("error", ""),
                "source": prior.get("source", ""),
            }
        )
    return rows


def execute_pilot(args: argparse.Namespace, command_line: str) -> dict[str, Any]:
    calls = pilot_calls()
    plan = build_execution_plan(
        calls,
        retry_network_errors=args.retry_network_errors,
        resume=args.resume,
        max_http_requests=args.max_http_requests,
    )
    if plan["blocked_network"]:
        first = plan["blocked_network"][0]
        message = (
            "Existen errores previos de red/local socket en run_007. "
            "Use --retry-network-errors para ignorar solo esos errores y reintentar fuera del sandbox. "
            f"Primer lote bloqueado: {first['call_id']}"
        )
        raise RuntimeError(message)
    if plan["blocked_other"]:
        first = plan["blocked_other"][0]
        raise RuntimeError(f"Existen errores previos no clasificados como red; no se ignoran: {first['call_id']}")

    RUN_ROOT.mkdir(parents=True, exist_ok=True)
    PILOT_ROOT.mkdir(parents=True, exist_ok=True)
    client = XMClient(execute=True, retries=3, backoff_seconds=[2, 5, 10], timeout=60)
    request_log: list[dict[str, Any]] = []
    schemas: dict[str, Any] = {}
    units: list[dict[str, Any]] = []
    coverage: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    metric_failed: set[str] = set()
    network_blocked = False

    for index, call in enumerate(plan["planned"], start=1):
        if call["target"] in metric_failed:
            continue
        if completed_source(call):
            continue
        out_dir = pilot_output_dir(call)
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
            normalized = derive_units_contextual(normalize_xm_response(data, call["periodicity"]), target=call["target"], metric_id=call["metric_id"], entity=call["entity"], catalog_unit=call["unit"])
            if normalized.empty:
                raise ValueError("Respuesta no vacia pero normalizacion produjo cero registros")
            norm_path = versioned_path(out_dir, f"{call['call_id']}__normalized", ".csv")
            normalized.to_csv(norm_path, index=False, encoding="utf-8")
            mark_completed(out_dir, call["call_id"], raw_path, rows=len(normalized))
            status = "OK"
            saved_path = str(raw_path.relative_to(ROOT))
            sha = sha256_file(raw_path)
            records = int(len(normalized))
            unit_summary = schema_summary(normalized, call["metric_id"], call["target"], call["unit"], call["entity"])
            schemas.setdefault(call["target"], unit_summary)
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
                    "entity": call["entity"],
                    "requested_entities": call.get("filter_count", 0) or 1,
                    "records": records,
                    "date_min": unit_summary.get("date_min", ""),
                    "date_max": unit_summary.get("date_max", ""),
                }
            )
        except Exception as exc:
            duration = time.perf_counter() - started
            error_message = str(exc)
            status = "ERROR"
            network_blocked = network_blocked or is_network_block_error(exc) or is_network_block_error(error_message)
            mark_error(out_dir, call["call_id"], error_message, {"payload": payload, "call": call})
            errors.append(error_row(call, error_message, "retry1"))
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
        if index < len(plan["planned"]):
            time.sleep(1)

    frames = read_normalized_outputs(PILOT_ROOT)
    summary = summarize_plan(args, command_line, calls, plan, "execute")
    summary.update(
        {
            "status": decide_status(request_log, errors, schemas, network_blocked),
            "requests_made": len(request_log),
            "responses_valid": sum(1 for row in request_log if row["http_status"] == "OK"),
            "requests_failed": sum(1 for row in request_log if str(row["http_status"]).startswith("ERROR")),
            "metrics_ok": sorted({row["target"] for row in request_log if row["http_status"] == "OK"}),
            "metrics_failed": sorted({row["target"] for row in request_log if str(row["http_status"]).startswith("ERROR")}),
            "checkpoints": checkpoint_paths(),
        }
    )
    register_run(summary=summary, request_log=request_log, errors=errors, plan=plan)
    write_json_report(RUN_ROOT / "esquemas_respuestas.json", schemas)
    write_csv(RUN_ROOT / "validacion_unidades.csv", units)
    write_csv(RUN_ROOT / "validacion_cobertura.csv", coverage)
    write_text_report(RUN_ROOT / "validacion_balance.md", build_balance_report(frames) + "\n\n" + build_hydro_report(frames))
    write_text_report(RUN_ROOT / "conclusion_piloto.md", build_conclusion(summary, errors, schemas))
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return summary


def error_row(call: dict[str, Any], error: str, source: str) -> dict[str, Any]:
    return {
        "call_id": call["call_id"],
        "target": call["target"],
        "metric_id": call["metric_id"],
        "entity": call["entity"],
        "start_date": call["start_date"],
        "end_date": call["end_date"],
        "error": error,
        "source": source,
    }


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


def daily_sum(frame: Any, value_col: str = "Value_GWh") -> Any:
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
    return "\n".join(
        [
            "# Validacion de balance electrico",
            "",
            "Comparacion diagnostica; no se fuerza igualdad porque las definiciones pueden incluir perdidas, generacion no despachada centralmente, autogeneracion, cogeneracion, consumos auxiliares e intercambios.",
            "",
            "```csv\n" + base.round(6).to_csv(index=False) + "```",
        ]
    )


def build_hydro_report(frames: dict[str, Any]) -> str:
    vol = daily_sum(frames.get("volumen_util_energia_sin"))
    cap = daily_sum(frames.get("capacidad_util_energia_sin"))
    if vol.empty or cap.empty:
        return "# Validacion hidrologica\n\nNo hay volumen/capacidad sistema suficientes."
    merged = vol.merge(cap, on="day", suffixes=("_volumen", "_capacidad"))
    merged["porcentaje_energetico"] = merged["Value_GWh_volumen"] / merged["Value_GWh_capacidad"]
    return "\n".join(
        [
            "# Validacion hidrologica",
            "",
            "El porcentaje energetico se calcula como VoluUtilDiarEner / CapaUtilDiarEner. Sirve para contrastar contra embalses_manu, sin exigir correspondencia exacta.",
            "",
            "```csv\n" + merged.round(6).to_csv(index=False) + "```",
        ]
    )


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
    return f"""# Conclusion piloto XM retry1

Estado: **{status}**

- Solicitudes planeadas: {summary['requests_planned']}
- Solicitudes realizadas: {summary['requests_made']}
- Exitosas: {summary['responses_valid']}
- Fallidas: {summary.get('requests_failed', 0)}
- Periodo: {summary['period'][0]} a {summary['period'][1]}

## DispoDeclarada

{dispo_note}

## Errores

{json.dumps(errors, ensure_ascii=False, indent=2)}

No se inicia ninguna descarga adicional despues de esta decision.
"""


def main(argv: list[str] | None = None, command_line: str | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    command = command_line or exact_command_line(argv)
    try:
        if args.execute:
            execute_pilot(args, command)
        else:
            dry_run(args, command)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


