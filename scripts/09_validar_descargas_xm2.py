from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from minenergia_sddp.data.xm_checkpoints import load_checkpoint, sha256_file
from minenergia_sddp.data.xm_pilot import derive_units_contextual, normalize_xm_response, resolve_effective_unit

DEFAULT_START_DATE = "2023-01-01"
DEFAULT_END_DATE = "2026-07-13"
DEFAULT_RUN_DIR = "outputs/run_010"
AUTHORIZED_TARGETS = (
    "demanda_real_sistema_horaria",
    "demanda_sin_diaria",
    "generacion_real_total",
    "importaciones_energia_sistema",
    "exportaciones_energia_sistema",
)
FILENAME_RE = re.compile(r"^(?P<target>.+)__(?P<start>\d{4}-\d{2}-\d{2})__(?P<end>\d{4}-\d{2}-\d{2})__b(?P<batch>\d{3})(?:_v\d{3})?\.json$")
STATUSES = {
    "validated": "HISTORICAL_BLOCK_VALIDATED",
    "warnings": "HISTORICAL_BLOCK_VALIDATED_WITH_WARNINGS",
    "blocked": "HISTORICAL_BLOCK_BLOCKED",
}


@dataclass(frozen=True)
class TargetSpec:
    target: str
    metric_id: str
    entity: str
    periodicity: str
    unit: str
    output_domain: str

    @property
    def raw_dir(self) -> Path:
        return ROOT / "data/raw/xm" / self.output_domain / self.target

    @property
    def entity_column(self) -> str:
        if self.periodicity == "HourlyEntities":
            return "HourlyEntities"
        if self.periodicity == "DailyEntities":
            return "DailyEntities"
        return self.periodicity

    @property
    def expected_frequency(self) -> str:
        return "hourly" if self.periodicity == "HourlyEntities" else "daily"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Valida descargas historicas XM ya existentes, sin red ni consolidacion.")
    parser.add_argument("--target", action="append", choices=AUTHORIZED_TARGETS, help="Target autorizado a validar. Puede repetirse.")
    parser.add_argument("--start-date", default=DEFAULT_START_DATE)
    parser.add_argument("--end-date", default=DEFAULT_END_DATE)
    parser.add_argument("--dry-run", action="store_true", help="Muestra plan y termina sin escribir reportes.")
    parser.add_argument("--run-dir", default=DEFAULT_RUN_DIR, help="Directorio de salida; por defecto outputs/run_010.")
    return parser


def load_specs() -> dict[str, TargetSpec]:
    data = json.loads((ROOT / "config/xm_metrics.json").read_text(encoding="utf-8-sig"))
    specs: dict[str, TargetSpec] = {}
    for item in data.get("metrics", []):
        target = item.get("target")
        if target in AUTHORIZED_TARGETS:
            specs[target] = TargetSpec(
                target=target,
                metric_id=item["metric_id"],
                entity=item["entity"],
                periodicity=item["periodicity"],
                unit=item["unit"],
                output_domain=item["output_domain"],
            )
    missing = sorted(set(AUTHORIZED_TARGETS) - set(specs))
    if missing:
        raise RuntimeError(f"Faltan targets autorizados en config/xm_metrics.json: {missing}")
    return specs


def parse_date(value: str) -> datetime.date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def date_windows(start: str, end: str, step_days: int = 30) -> list[tuple[str, str]]:
    start_date = parse_date(start)
    end_date = parse_date(end)
    if end_date < start_date:
        raise ValueError("end-date debe ser mayor o igual a start-date")
    windows: list[tuple[str, str]] = []
    current = start_date
    while current <= end_date:
        close = min(current + timedelta(days=step_days - 1), end_date)
        windows.append((current.isoformat(), close.isoformat()))
        current = close + timedelta(days=1)
    return windows


def selected_targets(args: argparse.Namespace) -> list[str]:
    return args.target or list(AUTHORIZED_TARGETS)


def list_target_files(spec: TargetSpec) -> list[Path]:
    if not spec.raw_dir.exists():
        return []
    return sorted(path for path in spec.raw_dir.glob("*.json") if not path.name.startswith("_checkpoint"))


def checkpoint_completed(spec: TargetSpec) -> set[str]:
    checkpoint = load_checkpoint(spec.raw_dir)
    return set(checkpoint.get("completed", {}).keys())


def checkpoint_errors(spec: TargetSpec) -> list[dict[str, Any]]:
    return list(load_checkpoint(spec.raw_dir).get("errors", []))


def parse_window_from_name(path: Path) -> dict[str, Any]:
    match = FILENAME_RE.match(path.name)
    if not match:
        return {"valid_name": False, "target": "", "start": "", "end": "", "batch": ""}
    item = match.groupdict()
    item["valid_name"] = True
    return item


def exact_command_line(argv: list[str] | None = None) -> str:
    if argv is not None:
        return subprocess.list2cmdline([Path(sys.executable).name, "scripts/09_validar_descargas_xm2.py", *argv])
    return subprocess.list2cmdline([Path(sys.executable).name, *sys.argv])


def resolve_run_dir(path_text: str) -> Path:
    requested = ROOT / path_text
    if not requested.exists():
        return requested
    index = 2
    while True:
        candidate = requested.with_name(f"{requested.name}_v{index:03d}")
        if not candidate.exists():
            return candidate
        index += 1


def dry_run(args: argparse.Namespace, specs: dict[str, TargetSpec]) -> int:
    targets = selected_targets(args)
    expected = len(date_windows(args.start_date, args.end_date))
    print("Validacion historica XM dry-run")
    print(f"Periodo: {args.start_date} a {args.end_date}")
    print(f"Directorio de salida: {args.run_dir}")
    for target in targets:
        spec = specs[target]
        count = len(list_target_files(spec))
        print(f"{target}: ruta={spec.raw_dir.relative_to(ROOT)} json_encontrados={count} ventanas_esperadas={expected}")
    print("No se escribieron reportes.")
    return 0


def validation_error(rows: list[dict[str, Any]], severity: str, target: str, file_path: Path | None, code: str, message: str) -> None:
    rows.append(
        {
            "severity": severity,
            "target": target,
            "file": str(file_path.relative_to(ROOT)) if file_path else "",
            "code": code,
            "message": message,
        }
    )


def validate_file(path: Path, spec: TargetSpec, errors: list[dict[str, Any]]) -> tuple[dict[str, Any], pd.DataFrame]:
    parsed = parse_window_from_name(path)
    row: dict[str, Any] = {
        "target": spec.target,
        "file": str(path.relative_to(ROOT)),
        "filename_valid": parsed["valid_name"],
        "window_start": parsed.get("start", ""),
        "window_end": parsed.get("end", ""),
        "batch": parsed.get("batch", ""),
        "sha256": "",
        "json_valid": False,
        "non_empty": False,
        "metric_id_expected": spec.metric_id,
        "metric_id_received": "",
        "entity_expected": spec.entity,
        "entity_received": "Sistema",
        "periodicity": spec.periodicity,
        "unit_catalog": spec.unit,
        "unit_effective": "",
        "unit_override_applied": False,
        "derived_column_expected": "",
        "columns": [],
        "records": 0,
        "date_min": "",
        "date_max": "",
        "dates_inside_window": False,
        "schema_received": "",
        "numeric_values": 0,
        "nulls": 0,
        "duplicates": 0,
        "negative_values": 0,
        "value_min": None,
        "value_max": None,
        "granularity_expected": spec.expected_frequency,
        "granularity_ok": False,
    }
    if not parsed["valid_name"]:
        validation_error(errors, "ERROR", spec.target, path, "BAD_FILENAME", "Nombre de archivo no coincide con target__start__end__bNNN.json")
    elif parsed["target"] != spec.target:
        validation_error(errors, "ERROR", spec.target, path, "TARGET_MISMATCH", f"Archivo apunta a {parsed['target']}")
    row["sha256"] = sha256_file(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        row["json_valid"] = True
    except Exception as exc:
        validation_error(errors, "ERROR", spec.target, path, "INVALID_JSON", str(exc))
        return row, pd.DataFrame()
    if data in (None, [], {}):
        validation_error(errors, "ERROR", spec.target, path, "EMPTY_JSON", "Respuesta vacia")
        return row, pd.DataFrame()
    row["non_empty"] = True
    if isinstance(data, dict) and any(key.lower() in {"error", "errors", "exception"} for key in data):
        validation_error(errors, "ERROR", spec.target, path, "SERIALIZED_ERROR", "El JSON contiene claves de error")
    metric = data.get("Metric", {}) if isinstance(data, dict) else {}
    row["metric_id_received"] = str(metric.get("Id", ""))
    if row["metric_id_received"] and row["metric_id_received"] != spec.metric_id:
        validation_error(errors, "ERROR", spec.target, path, "METRIC_MISMATCH", f"Metric.Id={row['metric_id_received']}")
    items = data.get("Items") if isinstance(data, dict) else data
    if isinstance(items, list) and not items:
        resolution = resolve_effective_unit(spec.target, spec.metric_id, spec.entity, spec.unit)
        row["unit_effective"] = resolution["unit_effective"]
        row["unit_override_applied"] = resolution["unit_override_applied"]
        row["derived_column_expected"] = resolution.get("derived_column", "")
        row["schema_received"] = "[]"
        if parsed["valid_name"]:
            row["date_min"] = parsed["start"]
            row["date_max"] = parsed["end"]
            row["dates_inside_window"] = True
        validation_error(errors, "WARNING", spec.target, path, "EMPTY_ITEMS", "Respuesta valida sin Items; se interpreta como ventana sin valores reportados")
        return row, pd.DataFrame()
    top_columns = list(pd.DataFrame(items if isinstance(items, list) else []).columns) if isinstance(items, list) else []
    row["schema_received"] = json.dumps(top_columns, ensure_ascii=False)
    if spec.entity_column not in top_columns:
        validation_error(errors, "ERROR", spec.target, path, "SCHEMA_MISSING_ENTITY_COLUMN", f"Falta {spec.entity_column}")
    frame = normalize_xm_response(data, spec.periodicity)
    if frame.empty:
        validation_error(errors, "ERROR", spec.target, path, "NORMALIZED_EMPTY", "Normalizacion en memoria produjo cero registros")
        return row, frame
    normalized = derive_units_contextual(frame, target=spec.target, metric_id=spec.metric_id, entity=spec.entity, catalog_unit=spec.unit)
    resolution = resolve_effective_unit(spec.target, spec.metric_id, spec.entity, spec.unit)
    row["unit_effective"] = resolution["unit_effective"]
    row["unit_override_applied"] = resolution["unit_override_applied"]
    row["derived_column_expected"] = resolution.get("derived_column", "")
    row["columns"] = json.dumps(list(normalized.columns), ensure_ascii=False)
    row["records"] = int(len(normalized))
    raw_values = normalized["Value"] if "Value" in normalized.columns else pd.Series(dtype=float)
    values = pd.to_numeric(raw_values, errors="coerce")
    row["numeric_values"] = int(values.notna().sum())
    row["nulls"] = int(normalized.isna().sum().sum())
    key_cols = [col for col in ["Date", "Hour", "code"] if col in normalized.columns]
    row["duplicates"] = int(normalized.duplicated(subset=key_cols).sum()) if key_cols else int(normalized.duplicated().sum())
    row["negative_values"] = int((values < 0).sum())
    row["value_min"] = float(values.min()) if values.notna().any() else None
    row["value_max"] = float(values.max()) if values.notna().any() else None
    if row["numeric_values"] == 0:
        validation_error(errors, "ERROR", spec.target, path, "NO_NUMERIC_VALUES", "No hay valores numericos")
    raw_dates = normalized["Date"] if "Date" in normalized.columns else pd.Series(dtype=object)
    dates = pd.to_datetime(raw_dates, errors="coerce")
    if dates.notna().any():
        row["date_min"] = str(dates.min().date())
        row["date_max"] = str(dates.max().date())
        if parsed["valid_name"]:
            start = parse_date(parsed["start"])
            end = parse_date(parsed["end"])
            row["dates_inside_window"] = bool(dates.dt.date.ge(start).all() and dates.dt.date.le(end).all())
            if not row["dates_inside_window"]:
                validation_error(errors, "ERROR", spec.target, path, "DATE_OUT_OF_WINDOW", "Fechas fuera de ventana del archivo")
    else:
        validation_error(errors, "ERROR", spec.target, path, "NO_DATES", "No hay fechas parseables")
    if spec.periodicity == "HourlyEntities":
        row["granularity_ok"] = "Hour" in normalized.columns and normalized["Hour"].notna().any()
    else:
        row["granularity_ok"] = "Hour" not in normalized.columns
    if not row["granularity_ok"]:
        validation_error(errors, "ERROR", spec.target, path, "BAD_GRANULARITY", f"Granularidad esperada {spec.expected_frequency}")
    derived = resolution.get("derived_column", "")
    if derived and derived not in normalized.columns:
        validation_error(errors, "ERROR", spec.target, path, "MISSING_DERIVED_COLUMN", f"Falta {derived}")
    if spec.unit == "kWh" and derived == "Value_GWh" and derived in normalized.columns:
        check = (normalized[derived] - values / 1_000_000.0).abs().max()
        if pd.notna(check) and float(check) > 1e-9:
            validation_error(errors, "ERROR", spec.target, path, "BAD_KWH_CONVERSION", "Value_GWh no coincide con Value/1e6")
    return row, normalized


def expected_call_id(target: str, window: tuple[str, str]) -> str:
    return f"{target}__{window[0]}__{window[1]}__b001"


def coverage_for_target(
    spec: TargetSpec,
    files: list[Path],
    expected: list[tuple[str, str]],
    manifest_rows: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    expected_ids = {expected_call_id(spec.target, window): window for window in expected}
    found: dict[str, list[Path]] = {}
    for path in files:
        parsed = parse_window_from_name(path)
        if parsed["valid_name"] and parsed["target"] == spec.target:
            found.setdefault(path.stem, []).append(path)
    completed = checkpoint_completed(spec)
    checkpoint_errs = checkpoint_errors(spec)
    missing = []
    for call_id, (start, end) in expected_ids.items():
        if call_id not in found:
            missing.append({"target": spec.target, "call_id": call_id, "window_start": start, "window_end": end})
    duplicates = []
    for call_id, paths in found.items():
        if len(paths) > 1:
            for path in paths:
                parsed = parse_window_from_name(path)
                duplicates.append({"target": spec.target, "call_id": call_id, "window_start": parsed["start"], "window_end": parsed["end"], "file": str(path.relative_to(ROOT))})
    intervals = sorted((parse_date(w[0]), parse_date(w[1])) for w in expected)
    overlaps = 0
    gaps = 0
    for previous, current in zip(intervals, intervals[1:]):
        if current[0] <= previous[1]:
            overlaps += 1
        if current[0] > previous[1] + timedelta(days=1):
            gaps += 1
    target_rows = [row for row in manifest_rows if row["target"] == spec.target]
    dates_min = [row["date_min"] for row in target_rows if row.get("date_min")]
    dates_max = [row["date_max"] for row in target_rows if row.get("date_max")]
    summary = {
        "target": spec.target,
        "metric_id": spec.metric_id,
        "periodicity": spec.periodicity,
        "unit_catalog": spec.unit,
        "windows_expected": len(expected),
        "windows_found": len(found),
        "windows_completed_checkpoint": len(completed.intersection(expected_ids)),
        "windows_missing": len(missing),
        "windows_duplicated": len(duplicates),
        "overlaps": overlaps,
        "temporal_gaps": gaps,
        "first_effective_date": min(dates_min) if dates_min else "",
        "last_effective_date": max(dates_max) if dates_max else "",
        "total_records": sum(int(row.get("records") or 0) for row in target_rows),
        "file_count": len(files),
        "checkpoint_errors": len(checkpoint_errs),
        "covers_full_period": len(missing) == 0 and len(found) == len(expected_ids),
    }
    return summary, missing, duplicates


def schemas_by_target(specs: dict[str, TargetSpec], frames: dict[str, list[pd.DataFrame]]) -> dict[str, Any]:
    result = {}
    for target, target_frames in frames.items():
        spec = specs[target]
        combined = pd.concat(target_frames, ignore_index=True) if target_frames else pd.DataFrame()
        resolution = resolve_effective_unit(target, spec.metric_id, spec.entity, spec.unit)
        expected_cols = {"Date", "Id", "code", "name", "Value", "unit_catalog", "unit_effective", "unit_override_applied", "override_reason"}
        if spec.periodicity == "HourlyEntities":
            expected_cols.add("Hour")
        derived = resolution.get("derived_column")
        if derived:
            expected_cols.add(derived)
        actual = set(combined.columns)
        result[target] = {
            "metric_id": spec.metric_id,
            "periodicity": spec.periodicity,
            "unit_catalog": spec.unit,
            "unit_effective": resolution["unit_effective"],
            "derived_column_expected": derived,
            "columns_real": sorted(actual),
            "columns_missing": sorted(expected_cols - actual),
            "columns_unexpected": sorted(actual - expected_cols),
        }
    return result


def stats_by_target(frames: dict[str, list[pd.DataFrame]], specs: dict[str, TargetSpec]) -> list[dict[str, Any]]:
    rows = []
    for target, items in sorted(frames.items()):
        frame = pd.concat(items, ignore_index=True)
        spec = specs[target]
        resolution = resolve_effective_unit(target, spec.metric_id, spec.entity, spec.unit)
        derived = resolution.get("derived_column", "")
        values = pd.to_numeric(frame.get(derived), errors="coerce") if derived else pd.Series(dtype=float)
        dates = pd.to_datetime(frame.get("Date"), errors="coerce")
        rows.append(
            {
                "target": target,
                "metric_id": spec.metric_id,
                "unit_catalog": spec.unit,
                "unit_effective": resolution["unit_effective"],
                "derived_column": derived,
                "records": int(len(frame)),
                "date_min": str(dates.min().date()) if dates.notna().any() else "",
                "date_max": str(dates.max().date()) if dates.notna().any() else "",
                "nulls": int(frame.isna().sum().sum()),
                "duplicates": int(frame.duplicated(subset=[col for col in ["Date", "Hour", "code"] if col in frame.columns]).sum()),
                "value_min": float(values.min()) if values.notna().any() else None,
                "value_max": float(values.max()) if values.notna().any() else None,
                "value_mean": float(values.mean()) if values.notna().any() else None,
            }
        )
    return rows


def daily_series(frame: pd.DataFrame, target: str) -> pd.DataFrame:
    if frame.empty or "Value_GWh" not in frame.columns:
        return pd.DataFrame(columns=["Date", target])
    temp = frame.copy()
    temp["Date"] = pd.to_datetime(temp["Date"], errors="coerce").dt.date.astype(str)
    return temp.groupby("Date", as_index=False)["Value_GWh"].sum().rename(columns={"Value_GWh": target})


def preliminary_balance(frames: dict[str, list[pd.DataFrame]], start_date: str, end_date: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    combined = {target: pd.concat(items, ignore_index=True) for target, items in frames.items() if items}
    all_days = pd.DataFrame({"Date": pd.date_range(start_date, end_date, freq="D").date.astype(str)})
    mapping = {
        "demanda_sin_diaria": "DemaSIN_GWh",
        "demanda_real_sistema_horaria": "DemaReal_GWh",
        "generacion_real_total": "Gene_GWh",
        "importaciones_energia_sistema": "ImpoEner_GWh",
        "exportaciones_energia_sistema": "ExpoEner_GWh",
    }
    base = all_days
    for target, col in mapping.items():
        piece = daily_series(combined.get(target, pd.DataFrame()), col)
        base = base.merge(piece, on="Date", how="left")
    for exchange_col in ["ImpoEner_GWh", "ExpoEner_GWh"]:
        if exchange_col in base.columns:
            base[exchange_col] = base[exchange_col].fillna(0.0)
    base["diff_dema_real_vs_dema_sin_gwh"] = base["DemaReal_GWh"] - base["DemaSIN_GWh"]
    base["diff_dema_real_vs_dema_sin_rel"] = base["diff_dema_real_vs_dema_sin_gwh"] / base["DemaSIN_GWh"]
    base["gene_plus_impo_minus_expo_gwh"] = base["Gene_GWh"] + base["ImpoEner_GWh"] - base["ExpoEner_GWh"]
    base["diff_balance_vs_dema_sin_gwh"] = base["gene_plus_impo_minus_expo_gwh"] - base["DemaSIN_GWh"]
    base["diff_balance_vs_dema_sin_rel"] = base["diff_balance_vs_dema_sin_gwh"] / base["DemaSIN_GWh"]
    base["atypical_daily_closure"] = base["diff_balance_vs_dema_sin_rel"].abs() > 0.20
    summary = {
        "days_expected": int(len(base)),
        "days_available_all_series": int(base[list(mapping.values())].notna().all(axis=1).sum()),
        "days_missing_any_series": int((~base[list(mapping.values())].notna().all(axis=1)).sum()),
        "atypical_daily_closures": int(base["atypical_daily_closure"].sum()),
        "mean_abs_dema_real_vs_dema_sin_rel": float(base["diff_dema_real_vs_dema_sin_rel"].abs().mean()),
        "mean_abs_balance_vs_dema_sin_rel": float(base["diff_balance_vs_dema_sin_rel"].abs().mean()),
    }
    return base.to_dict("records"), summary


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    if path.exists():
        raise FileExistsError(f"No se sobrescribe archivo existente: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            item = {key: row.get(key, "") for key in fieldnames}
            for key, value in item.items():
                if isinstance(value, (list, dict)):
                    item[key] = json.dumps(value, ensure_ascii=False)
            writer.writerow(item)


def write_json(path: Path, data: Any) -> None:
    if path.exists():
        raise FileExistsError(f"No se sobrescribe archivo existente: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def conclusion_text(status: str, summary: dict[str, Any], balance_summary: dict[str, Any], blocking_errors: int, warnings: int) -> str:
    return f"""# Validacion descargas historicas XM run_010

Estado: **{status}**

Periodo validado: {summary['start_date']} a {summary['end_date']}

- Targets: {', '.join(summary['targets'])}
- Archivos JSON: {summary['files_found']}
- Ventanas esperadas por target: {summary['windows_expected_per_target']}
- Ventanas faltantes: {summary['missing_windows']}
- Ventanas duplicadas: {summary['duplicated_windows']}
- Errores bloqueantes: {blocking_errors}
- Advertencias: {warnings}

## Balance preliminar

La comparacion diaria es diagnostica y no fuerza igualdad fisica; las definiciones pueden incluir perdidas, generacion no cubierta u otros componentes.

- Dias con todas las series: {balance_summary['days_available_all_series']}
- Dias con alguna serie faltante: {balance_summary['days_missing_any_series']}
- Cierres diarios atipicos: {balance_summary['atypical_daily_closures']}

No se hicieron solicitudes HTTP, no se descargaron datos y no se consolido ningun dataset.
"""


def validate(args: argparse.Namespace, specs: dict[str, TargetSpec], command: str) -> dict[str, Any]:
    targets = selected_targets(args)
    expected = date_windows(args.start_date, args.end_date)
    run_dir = resolve_run_dir(args.run_dir)
    manifest: list[dict[str, Any]] = []
    coverage_rows: list[dict[str, Any]] = []
    missing_rows: list[dict[str, Any]] = []
    duplicate_rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    frames: dict[str, list[pd.DataFrame]] = {}
    for target in targets:
        spec = specs[target]
        files = list_target_files(spec)
        for path in files:
            row, frame = validate_file(path, spec, errors)
            manifest.append(row)
            if not frame.empty:
                frames.setdefault(target, []).append(derive_units_contextual(frame, target=target, metric_id=spec.metric_id, entity=spec.entity, catalog_unit=spec.unit))
        coverage, missing, duplicates = coverage_for_target(spec, files, expected, manifest)
        coverage_rows.append(coverage)
        missing_rows.extend(missing)
        duplicate_rows.extend(duplicates)
        if missing:
            validation_error(errors, "ERROR", target, None, "MISSING_WINDOWS", f"{len(missing)} ventanas faltantes")
        if duplicates:
            validation_error(errors, "ERROR", target, None, "DUPLICATED_WINDOWS", f"{len(duplicates)} ventanas duplicadas")
        if checkpoint_errors(spec):
            validation_error(errors, "ERROR", target, None, "CHECKPOINT_ERRORS", f"{len(checkpoint_errors(spec))} errores en checkpoint")
    schemas = schemas_by_target(specs, frames)
    for target, schema in schemas.items():
        if schema["columns_missing"]:
            validation_error(errors, "ERROR", target, None, "MISSING_COLUMNS", json.dumps(schema["columns_missing"]))
    stats_rows = stats_by_target(frames, specs)
    balance_rows, balance_summary = preliminary_balance(frames, args.start_date, args.end_date)
    blocking = sum(1 for item in errors if item["severity"] == "ERROR")
    warnings = sum(1 for item in errors if item["severity"] == "WARNING")
    if blocking:
        status = STATUSES["blocked"]
    elif warnings or balance_summary["atypical_daily_closures"]:
        status = STATUSES["warnings"]
    else:
        status = STATUSES["validated"]
    summary = {
        "status": status,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "command": command,
        "start_date": args.start_date,
        "end_date": args.end_date,
        "run_dir": str(run_dir.relative_to(ROOT)),
        "targets": targets,
        "files_found": len(manifest),
        "windows_expected_per_target": len(expected),
        "missing_windows": len(missing_rows),
        "duplicated_windows": len(duplicate_rows),
        "blocking_errors": blocking,
        "warnings": warnings,
        "balance_preliminar": balance_summary,
    }
    run_dir.mkdir(parents=True, exist_ok=False)
    write_json(run_dir / "resumen_validacion.json", summary)
    write_csv(run_dir / "manifest_archivos.csv", manifest)
    write_csv(run_dir / "cobertura_por_target.csv", coverage_rows)
    write_json(run_dir / "esquemas_por_target.json", schemas)
    write_csv(run_dir / "ventanas_faltantes.csv", missing_rows, ["target", "call_id", "window_start", "window_end"])
    write_csv(run_dir / "ventanas_duplicadas.csv", duplicate_rows)
    write_csv(run_dir / "errores_validacion.csv", errors, ["severity", "target", "file", "code", "message"])
    write_csv(run_dir / "estadisticas_por_target.csv", stats_rows)
    write_csv(run_dir / "balance_preliminar_diario.csv", balance_rows)
    (run_dir / "conclusion_validacion.md").write_text(conclusion_text(status, summary, balance_summary, blocking, warnings), encoding="utf-8")
    (run_dir / "comando_ejecutado.txt").write_text(command + "\n", encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    specs = load_specs()
    if args.dry_run:
        return dry_run(args, specs)
    summary = validate(args, specs, exact_command_line(argv))
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())




