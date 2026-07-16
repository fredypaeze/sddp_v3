from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import re
import subprocess
import sys
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from minenergia_sddp.data.xm_checkpoints import sha256_file

DEFAULT_START_DATE = "2023-01-01"
DEFAULT_END_DATE = "2026-07-13"
DEFAULT_RUN_DIR = "outputs/run_012"
DEFAULT_OUTPUT_DIR = "data/processed/xm/system_historical_v2"
V1_DIR = ROOT / "data/processed/xm/system_historical_v1"

INTERCHANGE_TARGETS = {
    "importaciones_energia_sistema": {
        "domain": "intercambios",
        "metric_id": "ImpoEner",
        "entity": "Sistema",
        "periodicity": "HourlyEntities",
        "unit": "kWh",
        "value_col": "importaciones_gwh",
        "status_col": "importaciones_status",
        "imputed_col": "importaciones_imputed",
        "source_col": "fuente_importaciones",
    },
    "exportaciones_energia_sistema": {
        "domain": "intercambios",
        "metric_id": "ExpoEner",
        "entity": "Sistema",
        "periodicity": "HourlyEntities",
        "unit": "kWh",
        "value_col": "exportaciones_gwh",
        "status_col": "exportaciones_status",
        "imputed_col": "exportaciones_imputed",
        "source_col": "fuente_exportaciones",
    },
}

ALL_TARGETS = [
    "demanda_real_sistema_horaria",
    "demanda_sin_diaria",
    "generacion_real_total",
    "importaciones_energia_sistema",
    "exportaciones_energia_sistema",
]

FILENAME_RE = re.compile(r"^(?P<target>.+)__(?P<start>\d{4}-\d{2}-\d{2})__(?P<end>\d{4}-\d{2}-\d{2})__b(?P<batch>\d{3})(?:_v\d{3})?\.json$")
HOURS = [f"Hour{index:02d}" for index in range(1, 25)]
KNOWN_STATUSES = {"REPORTED_VALUE", "EXPLICIT_ZERO", "STRUCTURAL_ZERO_INFERRED"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audita faltantes horarios de importaciones y exportaciones XM.")
    parser.add_argument("--dry-run", action="store_true", help="Inspecciona insumos sin escribir reportes finales.")
    parser.add_argument("--execute", action="store_true", help="Autoriza escritura local de auditoria y, si procede, dataset v2.")
    parser.add_argument("--start-date", default=DEFAULT_START_DATE)
    parser.add_argument("--end-date", default=DEFAULT_END_DATE)
    parser.add_argument("--run-dir", default=DEFAULT_RUN_DIR)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    return parser


def load_consolidator() -> Any:
    path = ROOT / "scripts/10_consolidar_xm2.py"
    spec = importlib.util.spec_from_file_location("xm_consolidator_v1", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"No se pudo cargar {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def each_day(start: str, end: str) -> list[str]:
    current = parse_date(start)
    close = parse_date(end)
    result = []
    while current <= close:
        result.append(current.isoformat())
        current += timedelta(days=1)
    return result


def hour_number(hour: str) -> int:
    return int(str(hour).replace("Hour", ""))


def hour_timestamp(day: str, hour: str) -> str:
    return (pd.Timestamp(day) + pd.Timedelta(hours=hour_number(hour) - 1)).isoformat()


def versioned_path(path_text: str, *, dataset: bool = False) -> Path:
    requested = ROOT / path_text
    if not requested.exists():
        return requested
    if dataset and requested.name.endswith("_v2"):
        prefix = requested.name[:-1]
        index = 3
        while True:
            candidate = requested.parent / f"{prefix}{index}"
            if not candidate.exists():
                return candidate
            index += 1
    index = 2
    while True:
        candidate = requested.with_name(f"{requested.name}_v{index:03d}")
        if not candidate.exists():
            return candidate
        index += 1


def parse_file_window(path: Path) -> dict[str, Any]:
    match = FILENAME_RE.match(path.name)
    if not match:
        return {"target": "", "start": "", "end": "", "batch": "", "valid": False}
    data = match.groupdict()
    data["valid"] = True
    return data


def raw_dir_for(target: str) -> Path:
    spec = INTERCHANGE_TARGETS[target]
    return ROOT / "data/raw/xm" / spec["domain"] / target


def list_interchange_files(target: str) -> list[Path]:
    return sorted(path for path in raw_dir_for(target).glob("*.json") if not path.name.startswith("_checkpoint"))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def to_number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def extract_values_by_date(item: dict[str, Any]) -> tuple[str, dict[str, Any], bool]:
    entities = item.get("HourlyEntities")
    if not isinstance(entities, list) or not entities:
        return str(item.get("Date", "")), {}, False
    entity = entities[0]
    values = entity.get("Values", {}) if isinstance(entity, dict) else {}
    return str(item.get("Date", "")), values if isinstance(values, dict) else {}, True


def classify_raw_hour(raw_value: Any) -> tuple[str, float | None, str]:
    value = to_number(raw_value)
    if value is None:
        return "STRUCTURAL_ZERO_INFERRED", 0.0, "blank_hour_inside_valid_response"
    if value == 0:
        return "EXPLICIT_ZERO", 0.0, "explicit_zero"
    return "REPORTED_VALUE", value / 1_000_000.0, "reported_non_zero_value"


def classify_window(target: str, path: Path) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    spec = INTERCHANGE_TARGETS[target]
    window = parse_file_window(path)
    sha = sha256_file(path)
    rows: list[dict[str, Any]] = []
    missing_rows: list[dict[str, Any]] = []
    zero_rows: list[dict[str, Any]] = []
    empty_rows: list[dict[str, Any]] = []
    summary = {
        "target": target,
        "source_file": str(path.relative_to(ROOT)),
        "source_sha256": sha,
        "window_start": window.get("start", ""),
        "window_end": window.get("end", ""),
        "metric_id": "",
        "items": 0,
        "valid_response": False,
        "empty_window": False,
        "invalid_rows": 0,
    }
    try:
        data = read_json(path)
    except Exception as exc:
        summary["invalid_rows"] = 24 * len(each_day(window.get("start", DEFAULT_START_DATE), window.get("end", DEFAULT_END_DATE)))
        for day in each_day(window.get("start", DEFAULT_START_DATE), window.get("end", DEFAULT_END_DATE)):
            for hour in HOURS:
                row = base_classification_row(target, spec, path, sha, window, day, hour)
                row.update({"status": "UNKNOWN_MISSING_OR_INVALID", "value_gwh": pd.NA, "imputed": False, "reason": f"invalid_json:{exc}"})
                rows.append(row)
                missing_rows.append(row)
        return rows, summary, missing_rows, zero_rows
    metric = data.get("Metric", {}) if isinstance(data, dict) else {}
    summary["metric_id"] = metric.get("Id", "")
    items = data.get("Items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        summary["invalid_rows"] = 24 * len(each_day(window["start"], window["end"]))
        for day in each_day(window["start"], window["end"]):
            for hour in HOURS:
                row = base_classification_row(target, spec, path, sha, window, day, hour)
                row.update({"status": "UNKNOWN_MISSING_OR_INVALID", "value_gwh": pd.NA, "imputed": False, "reason": "items_not_list"})
                rows.append(row)
                missing_rows.append(row)
        return rows, summary, missing_rows, zero_rows
    summary["items"] = len(items)
    summary["valid_response"] = True
    if len(items) == 0:
        summary["empty_window"] = True
        empty = {
            "target": target,
            "metric_id": summary["metric_id"],
            "source_file": summary["source_file"],
            "source_sha256": sha,
            "window_start": window["start"],
            "window_end": window["end"],
            "classification": "UNKNOWN_EMPTY_WINDOW",
        }
        empty_rows.append(empty)
        for day in each_day(window["start"], window["end"]):
            for hour in HOURS:
                row = base_classification_row(target, spec, path, sha, window, day, hour)
                row.update({"status": "UNKNOWN_EMPTY_WINDOW", "value_gwh": pd.NA, "imputed": False, "reason": "empty_items_window"})
                rows.append(row)
                missing_rows.append(row)
        return rows, summary, missing_rows, zero_rows
    by_date: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        day, values, ok = extract_values_by_date(item)
        if ok and day:
            by_date[day] = values
    for day in each_day(window["start"], window["end"]):
        if day not in by_date:
            for hour in HOURS:
                row = base_classification_row(target, spec, path, sha, window, day, hour)
                row.update({"status": "STRUCTURAL_ZERO_INFERRED", "value_gwh": 0.0, "imputed": True, "reason": "missing_day_inside_valid_non_empty_response"})
                rows.append(row)
                missing_rows.append(row)
            continue
        values = by_date[day]
        for hour in HOURS:
            row = base_classification_row(target, spec, path, sha, window, day, hour)
            if hour not in values:
                row.update({"status": "UNKNOWN_MISSING_OR_INVALID", "value_gwh": pd.NA, "imputed": False, "reason": "missing_hour_key"})
                rows.append(row)
                missing_rows.append(row)
                continue
            status, value_gwh, reason = classify_raw_hour(values.get(hour))
            row.update({"status": status, "value_gwh": value_gwh, "imputed": status == "STRUCTURAL_ZERO_INFERRED", "reason": reason})
            rows.append(row)
            if status == "STRUCTURAL_ZERO_INFERRED":
                missing_rows.append(row)
            if status == "EXPLICIT_ZERO":
                zero_rows.append(row)
    return rows, summary, missing_rows, zero_rows


def base_classification_row(
    target: str,
    spec: dict[str, Any],
    path: Path,
    sha: str,
    window: dict[str, Any],
    day: str,
    hour: str,
) -> dict[str, Any]:
    return {
        "target": target,
        "metric_id": spec["metric_id"],
        "entity": spec["entity"],
        "periodicity": spec["periodicity"],
        "unit_catalog": spec["unit"],
        "unit_effective": spec["unit"],
        "fecha": day,
        "hora_xm": hour,
        "timestamp": hour_timestamp(day, hour),
        "source_file": str(path.relative_to(ROOT)),
        "source_sha256": sha,
        "window_start": window.get("start", ""),
        "window_end": window.get("end", ""),
    }


def audit_interchanges() -> dict[str, Any]:
    classifications: list[dict[str, Any]] = []
    windows: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    zeros: list[dict[str, Any]] = []
    empty: list[dict[str, Any]] = []
    for target in INTERCHANGE_TARGETS:
        for path in list_interchange_files(target):
            rows, summary, missing_rows, zero_rows = classify_window(target, path)
            classifications.extend(rows)
            windows.append(summary)
            missing.extend(missing_rows)
            zeros.extend(zero_rows)
            if summary.get("empty_window"):
                empty.extend(
                    {
                        "target": target,
                        "source_file": summary["source_file"],
                        "source_sha256": summary["source_sha256"],
                        "window_start": summary["window_start"],
                        "window_end": summary["window_end"],
                        "classification": "UNKNOWN_EMPTY_WINDOW",
                    }
                    for _ in [0]
                )
    class_df = pd.DataFrame(classifications)
    return {
        "classification": class_df,
        "windows": pd.DataFrame(windows),
        "missing": pd.DataFrame(missing),
        "zeros": pd.DataFrame(zeros),
        "empty": pd.DataFrame(empty),
        "patterns": {target: pattern_summary(target, class_df, pd.DataFrame(windows)) for target in INTERCHANGE_TARGETS},
    }


def run_lengths(items: list[str]) -> list[int]:
    lengths: list[int] = []
    current = 0
    previous: pd.Timestamp | None = None
    for item in sorted(pd.to_datetime(items, errors="coerce").dropna().unique()):
        stamp = pd.Timestamp(item)
        if previous is None or stamp == previous + pd.Timedelta(days=1):
            current += 1
        else:
            lengths.append(current)
            current = 1
        previous = stamp
    if current:
        lengths.append(current)
    return lengths


def pattern_summary(target: str, class_df: pd.DataFrame, windows_df: pd.DataFrame) -> dict[str, Any]:
    subset = class_df[class_df["target"].eq(target)].copy()
    win = windows_df[windows_df["target"].eq(target)].copy()
    value = pd.to_numeric(subset["value_gwh"], errors="coerce")
    reported_hours_by_day = subset[subset["status"].isin(["REPORTED_VALUE", "EXPLICIT_ZERO"])].groupby("fecha").size()
    expected_days = len(each_day(DEFAULT_START_DATE, DEFAULT_END_DATE))
    days_with_records = int((reported_hours_by_day > 0).sum())
    hours_dist = Counter(reported_hours_by_day.astype(int).to_dict().values())
    days_1_23 = int(sum(count for hours, count in hours_dist.items() if 1 <= int(hours) <= 23))
    days_24 = int(hours_dist.get(24, 0))
    days_0 = expected_days - days_with_records
    absent = subset[subset["status"].isin(["STRUCTURAL_ZERO_INFERRED", "UNKNOWN_EMPTY_WINDOW", "UNKNOWN_MISSING_OR_INVALID"])]
    absent_days = sorted(absent.loc[absent["status"].ne("STRUCTURAL_ZERO_INFERRED") | absent["reason"].str.contains("missing_day|empty", na=False), "fecha"].unique().tolist())
    return {
        "target": target,
        "files_total": int(len(list_interchange_files(target))),
        "valid_windows": int(win["valid_response"].fillna(False).sum()) if not win.empty else 0,
        "empty_windows": int(win["empty_window"].fillna(False).sum()) if not win.empty else 0,
        "expected_days": expected_days,
        "days_with_records": days_with_records,
        "days_without_records": days_0,
        "expected_hours": int(len(subset)),
        "reported_hours": int(subset["status"].isin(["REPORTED_VALUE", "EXPLICIT_ZERO"]).sum()),
        "missing_hours": int(subset["status"].isin(["STRUCTURAL_ZERO_INFERRED", "UNKNOWN_EMPTY_WINDOW", "UNKNOWN_MISSING_OR_INVALID"]).sum()),
        "explicit_zeros": int(subset["status"].eq("EXPLICIT_ZERO").sum()),
        "positive_values": int((value > 0).sum()),
        "negative_values": int((value < 0).sum()),
        "min_gwh": float(value[value > 0].min()) if (value > 0).any() else None,
        "max_gwh": float(value.max()) if value.notna().any() else None,
        "mean_gwh": float(value[value > 0].mean()) if (value > 0).any() else None,
        "reported_hours_distribution_by_day": json.dumps(dict(sorted(hours_dist.items())), ensure_ascii=False),
        "days_with_0_hours": days_0,
        "days_with_1_23_hours": days_1_23,
        "days_with_24_hours": days_24,
        "max_consecutive_absent_days": max(run_lengths(absent_days), default=0),
        "max_consecutive_absent_hours": max_consecutive_absent_hours(subset),
    }


def max_consecutive_absent_hours(subset: pd.DataFrame) -> int:
    ordered = subset.sort_values(["fecha", "hora_xm"])
    max_run = 0
    current = 0
    for status in ordered["status"]:
        if status in {"STRUCTURAL_ZERO_INFERRED", "UNKNOWN_EMPTY_WINDOW", "UNKNOWN_MISSING_OR_INVALID"}:
            current += 1
            max_run = max(max_run, current)
        else:
            current = 0
    return max_run


def decide_policy(audit: dict[str, Any]) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    warnings: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    class_df = audit["classification"]
    for target in INTERCHANGE_TARGETS:
        subset = class_df[class_df["target"].eq(target)]
        if subset.empty:
            errors.append({"code": "NO_CLASSIFICATION", "target": target, "message": "No hay clasificacion horaria"})
        if not subset["status"].eq("REPORTED_VALUE").any():
            errors.append({"code": "NO_REPORTED_VALUES", "target": target, "message": "No hay valores positivos reportados"})
        if subset["status"].eq("EXPLICIT_ZERO").any():
            warnings.append({"code": "EXPLICIT_ZERO_PRESENT", "target": target, "message": "Hay ceros explicitos; revisar antes de generalizar ausencias"})
    empty = audit["empty"]
    if not empty.empty:
        warnings.append({"code": "UNKNOWN_EMPTY_WINDOWS", "target": "importaciones_energia_sistema", "message": f"{len(empty)} ventanas completas se mantienen desconocidas"})
    invalid = class_df[class_df["status"].eq("UNKNOWN_MISSING_OR_INVALID")]
    if not invalid.empty:
        errors.append({"code": "INVALID_MISSING_ROWS", "message": f"{len(invalid)} horas con estructura invalida"})
    if errors:
        return "STRUCTURAL_ZERO_POLICY_BLOCKED", warnings, errors
    if warnings:
        return "STRUCTURAL_ZERO_POLICY_VALIDATED_WITH_WARNINGS", warnings, errors
    return "STRUCTURAL_ZERO_POLICY_VALIDATED", warnings, errors


def load_v1_frames() -> dict[str, pd.DataFrame]:
    module = load_consolidator()
    frames, _, _ = module.load_all_sources()
    deduped: dict[str, pd.DataFrame] = {}
    for target, frame in frames.items():
        clean, _, conflicts = module.split_duplicates(target, frame)
        if not conflicts.empty:
            raise RuntimeError(f"Duplicados conflictivos en {target}")
        deduped[target] = clean
    return deduped


def build_policy_file(status: str) -> dict[str, Any]:
    rules = []
    for target, spec in INTERCHANGE_TARGETS.items():
        rules.append(
            {
                "target": target,
                "metric_id": spec["metric_id"],
                "entity": spec["entity"],
                "periodicity": spec["periodicity"],
                "missing_record_policy": "STRUCTURAL_ZERO_INFERRED_ONLY_INSIDE_VALID_NON_EMPTY_RESPONSE",
                "empty_window_policy": "UNKNOWN_EMPTY_WINDOW",
                "explicit_zero_policy": "PRESERVE_AS_EXPLICIT_ZERO",
                "structural_zero_conditions": [
                    "JSON valido",
                    "Items no vacio en la ventana",
                    "MetricId esperado",
                    "estructura horaria Hour01-Hour24 presente o dia omitido dentro de ventana valida",
                    "valor horario vacio o dia omitido sin error de descarga",
                    "no aplicar a ventanas completas Items: []",
                ],
                "evidence_period": f"{DEFAULT_START_DATE} a {DEFAULT_END_DATE}",
                "evidence_run": "outputs/run_012",
                "status": status,
                "rationale": "Las respuestas no vacias usan matriz Hour01-Hour24 con cadenas vacias para horas sin intercambio y omiten dias completos sin valores; los valores reportados son positivos y las ventanas completamente vacias se conservan como desconocidas.",
            }
        )
    return {"policies": rules}


def build_interchange_piece(class_df: pd.DataFrame, target: str) -> pd.DataFrame:
    spec = INTERCHANGE_TARGETS[target]
    subset = class_df[class_df["target"].eq(target)].copy()
    piece = subset[["fecha", "hora_xm", "value_gwh", "status", "imputed", "source_file"]].rename(
        columns={
            "value_gwh": spec["value_col"],
            "status": spec["status_col"],
            "imputed": spec["imputed_col"],
            "source_file": spec["source_col"],
        }
    )
    return piece


def target_piece(frame: pd.DataFrame, value_col: str, reported_col: str, source_col: str) -> pd.DataFrame:
    piece = frame[["Date", "Hour", "Value_GWh", "source_file"]].copy()
    piece = piece.rename(columns={"Date": "fecha", "Hour": "hora_xm", "Value_GWh": value_col, "source_file": source_col})
    piece[reported_col] = piece[value_col].notna()
    return piece


def build_hourly_v2(frames: dict[str, pd.DataFrame], class_df: pd.DataFrame) -> pd.DataFrame:
    demand = target_piece(frames["demanda_real_sistema_horaria"], "demanda_real_gwh", "demanda_real_reportada", "fuente_demanda")
    generation = target_piece(frames["generacion_real_total"], "generacion_total_gwh", "generacion_reportada", "fuente_generacion")
    hourly = demand.merge(generation, on=["fecha", "hora_xm"], how="outer")
    hourly = hourly.merge(build_interchange_piece(class_df, "importaciones_energia_sistema"), on=["fecha", "hora_xm"], how="outer")
    hourly = hourly.merge(build_interchange_piece(class_df, "exportaciones_energia_sistema"), on=["fecha", "hora_xm"], how="outer")
    for col in ["demanda_real_reportada", "generacion_reportada"]:
        hourly[col] = hourly[col].fillna(False).astype(bool)
    for target in INTERCHANGE_TARGETS.values():
        hourly[target["imputed_col"]] = hourly[target["imputed_col"]].fillna(False).astype(bool)
    hourly["timestamp"] = [hour_timestamp(day, hour) for day, hour in zip(hourly["fecha"], hourly["hora_xm"])]
    net_mask = hourly[["generacion_total_gwh", "importaciones_gwh", "exportaciones_gwh"]].notna().all(axis=1)
    hourly["generacion_neta_intercambios_gwh"] = pd.NA
    hourly.loc[net_mask, "generacion_neta_intercambios_gwh"] = (
        hourly.loc[net_mask, "generacion_total_gwh"] + hourly.loc[net_mask, "importaciones_gwh"] - hourly.loc[net_mask, "exportaciones_gwh"]
    )
    hourly["balance_calculable"] = hourly[["demanda_real_gwh", "generacion_total_gwh", "importaciones_gwh", "exportaciones_gwh"]].notna().all(axis=1)
    hourly["balance_quality_flag"] = "COMPLETE"
    hourly.loc[hourly[["importaciones_status", "exportaciones_status"]].isin(["UNKNOWN_EMPTY_WINDOW", "UNKNOWN_MISSING_OR_INVALID"]).any(axis=1), "balance_quality_flag"] = "UNKNOWN_INTERCHANGE"
    columns = [
        "fecha",
        "hora_xm",
        "timestamp",
        "demanda_real_gwh",
        "generacion_total_gwh",
        "importaciones_gwh",
        "importaciones_status",
        "importaciones_imputed",
        "exportaciones_gwh",
        "exportaciones_status",
        "exportaciones_imputed",
        "generacion_neta_intercambios_gwh",
        "demanda_real_reportada",
        "generacion_reportada",
        "balance_calculable",
        "balance_quality_flag",
        "fuente_demanda",
        "fuente_generacion",
        "fuente_importaciones",
        "fuente_exportaciones",
    ]
    return hourly[columns].sort_values(["fecha", "hora_xm"]).reset_index(drop=True)


def daily_sum_known(hourly: pd.DataFrame, value_col: str, status_col: str) -> pd.DataFrame:
    known = hourly[status_col].isin(KNOWN_STATUSES)
    temp = hourly.copy()
    temp.loc[~known, value_col] = pd.NA
    grouped = temp.groupby("fecha", as_index=False).agg(
        value=(value_col, lambda s: s.sum(min_count=1)),
        known_hours=(status_col, lambda s: int(s.isin(KNOWN_STATUSES).sum())),
        unknown_hours=(status_col, lambda s: int(s.isin(["UNKNOWN_EMPTY_WINDOW", "UNKNOWN_MISSING_OR_INVALID"]).sum())),
        structural_zeros=(status_col, lambda s: int(s.eq("STRUCTURAL_ZERO_INFERRED").sum())),
    )
    return grouped


def build_daily_v2(frames: dict[str, pd.DataFrame], hourly: pd.DataFrame, start_date: str, end_date: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    days = pd.DataFrame({"fecha": each_day(start_date, end_date)})
    demand_sin = frames["demanda_sin_diaria"].copy()
    demand_sin["fecha"] = pd.to_datetime(demand_sin["Date"], errors="coerce").dt.date.astype(str)
    demand_sin = demand_sin.groupby("fecha", as_index=False)["Value_GWh"].sum().rename(columns={"Value_GWh": "demanda_sin_gwh"})
    base_hourly = hourly.groupby("fecha", as_index=False).agg(
        demanda_real_gwh=("demanda_real_gwh", lambda s: s.sum(min_count=1)),
        generacion_total_gwh=("generacion_total_gwh", lambda s: s.sum(min_count=1)),
        horas_demanda_real=("demanda_real_reportada", "sum"),
        horas_generacion=("generacion_reportada", "sum"),
    )
    imp = daily_sum_known(hourly, "importaciones_gwh", "importaciones_status").rename(
        columns={"value": "importaciones_gwh", "known_hours": "horas_importaciones", "unknown_hours": "horas_importaciones_unknown", "structural_zeros": "ceros_estructurales_importaciones"}
    )
    exp = daily_sum_known(hourly, "exportaciones_gwh", "exportaciones_status").rename(
        columns={"value": "exportaciones_gwh", "known_hours": "horas_exportaciones", "unknown_hours": "horas_exportaciones_unknown", "structural_zeros": "ceros_estructurales_exportaciones"}
    )
    daily = days.merge(demand_sin, on="fecha", how="left").merge(base_hourly, on="fecha", how="left").merge(imp, on="fecha", how="left").merge(exp, on="fecha", how="left")
    daily["demanda_sin_reportada"] = daily["demanda_sin_gwh"].notna()
    daily["demanda_real_completa"] = daily["horas_demanda_real"].eq(24)
    daily["generacion_completa"] = daily["horas_generacion"].eq(24)
    daily["importaciones_completas"] = daily["horas_importaciones"].eq(24) & daily["horas_importaciones_unknown"].eq(0)
    daily["exportaciones_completas"] = daily["horas_exportaciones"].eq(24) & daily["horas_exportaciones_unknown"].eq(0)
    complete_net = daily[["generacion_total_gwh", "importaciones_gwh", "exportaciones_gwh"]].notna().all(axis=1)
    daily["generacion_neta_intercambios_gwh"] = pd.NA
    daily.loc[complete_net, "generacion_neta_intercambios_gwh"] = (
        daily.loc[complete_net, "generacion_total_gwh"] + daily.loc[complete_net, "importaciones_gwh"] - daily.loc[complete_net, "exportaciones_gwh"]
    )
    diff_dem = daily[["demanda_real_gwh", "demanda_sin_gwh"]].notna().all(axis=1)
    daily["diferencia_demareal_demasin_gwh"] = pd.NA
    daily.loc[diff_dem, "diferencia_demareal_demasin_gwh"] = daily.loc[diff_dem, "demanda_real_gwh"] - daily.loc[diff_dem, "demanda_sin_gwh"]
    daily["diferencia_demareal_demasin_pct"] = daily["diferencia_demareal_demasin_gwh"] / daily["demanda_sin_gwh"]
    balance_mask = daily[["generacion_neta_intercambios_gwh", "demanda_sin_gwh"]].notna().all(axis=1)
    daily["diferencia_balance_gwh"] = pd.NA
    daily.loc[balance_mask, "diferencia_balance_gwh"] = daily.loc[balance_mask, "generacion_neta_intercambios_gwh"] - daily.loc[balance_mask, "demanda_sin_gwh"]
    daily["diferencia_balance_pct"] = daily["diferencia_balance_gwh"] / daily["demanda_sin_gwh"]
    daily["datos_completos_balance"] = (
        daily["demanda_sin_reportada"] & daily["generacion_completa"] & daily["importaciones_completas"] & daily["exportaciones_completas"]
    )
    excluded = build_exclusions(daily)
    ready = daily[daily["datos_completos_balance"]].copy()
    return daily, ready, excluded


def build_exclusions(daily: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in daily.iterrows():
        reasons = []
        if not bool(row["demanda_sin_reportada"]):
            reasons.append("demanda_sin_no_reportada")
        if not bool(row["generacion_completa"]):
            reasons.append("generacion_incompleta")
        if not bool(row["importaciones_completas"]):
            reasons.append("importaciones_unknown_empty_window")
        if not bool(row["exportaciones_completas"]):
            reasons.append("exportaciones_unknown_or_incompletas")
        if not bool(row["datos_completos_balance"]):
            reasons.append("balance_no_calculable")
        if reasons:
            rows.append({"fecha": row["fecha"], "motivo_exclusion": ";".join(reasons)})
    return pd.DataFrame(rows)


def balance_variant(hourly: pd.DataFrame, frames: dict[str, pd.DataFrame], variant: str) -> pd.DataFrame:
    temp = hourly.copy()
    if variant == "STRICT_OBSERVED_ONLY":
        observed_imports = temp["importaciones_status"].isin(["REPORTED_VALUE", "EXPLICIT_ZERO"])
        observed_exports = temp["exportaciones_status"].isin(["REPORTED_VALUE", "EXPLICIT_ZERO"])
        temp.loc[~observed_imports, "importaciones_gwh"] = pd.NA
        temp.loc[~observed_exports, "exportaciones_gwh"] = pd.NA
        temp.loc[~observed_imports, "importaciones_status"] = "UNKNOWN_MISSING_OR_INVALID"
        temp.loc[~observed_exports, "exportaciones_status"] = "UNKNOWN_MISSING_OR_INVALID"
    elif variant == "UNSAFE_ALL_MISSING_ZERO":
        missing_imports = temp["importaciones_status"].isin(["UNKNOWN_EMPTY_WINDOW", "UNKNOWN_MISSING_OR_INVALID"])
        missing_exports = temp["exportaciones_status"].isin(["UNKNOWN_EMPTY_WINDOW", "UNKNOWN_MISSING_OR_INVALID"])
        temp["importaciones_gwh"] = temp["importaciones_gwh"].fillna(0.0)
        temp["exportaciones_gwh"] = temp["exportaciones_gwh"].fillna(0.0)
        temp.loc[missing_imports, "importaciones_status"] = "STRUCTURAL_ZERO_INFERRED"
        temp.loc[missing_exports, "exportaciones_status"] = "STRUCTURAL_ZERO_INFERRED"
    daily, _, _ = build_daily_v2(frames, temp, DEFAULT_START_DATE, DEFAULT_END_DATE)
    result = daily[["fecha", "demanda_sin_gwh", "demanda_real_gwh", "generacion_total_gwh", "importaciones_gwh", "exportaciones_gwh", "diferencia_demareal_demasin_pct", "diferencia_balance_gwh", "diferencia_balance_pct"]].copy()
    result["variant"] = variant
    return result


def variant_stats(frame: pd.DataFrame, variant: str) -> dict[str, Any]:
    rel = pd.to_numeric(frame["diferencia_balance_pct"], errors="coerce").abs()
    abs_gwh = pd.to_numeric(frame["diferencia_balance_gwh"], errors="coerce").abs()
    top = frame.assign(abs_rel=rel).sort_values("abs_rel", ascending=False).head(10)
    return {
        "variant": variant,
        "calculable_days": int(rel.notna().sum()),
        "mean_abs_gwh": float(abs_gwh.mean()) if abs_gwh.notna().any() else None,
        "mean_abs_relative": float(rel.mean()) if rel.notna().any() else None,
        "median_abs_relative": float(rel.quantile(0.50)) if rel.notna().any() else None,
        "p90_abs_relative": float(rel.quantile(0.90)) if rel.notna().any() else None,
        "p95_abs_relative": float(rel.quantile(0.95)) if rel.notna().any() else None,
        "p99_abs_relative": float(rel.quantile(0.99)) if rel.notna().any() else None,
        "days_abs_gt_1pct": int((rel > 0.01).sum()),
        "days_abs_gt_2pct": int((rel > 0.02).sum()),
        "days_abs_gt_5pct": int((rel > 0.05).sum()),
        "largest_diff_dates": json.dumps(top[["fecha", "diferencia_balance_pct"]].to_dict("records"), ensure_ascii=False),
    }


def write_csv(path: Path, frame_or_rows: Any) -> None:
    if path.exists():
        raise FileExistsError(f"No se sobrescribe {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(frame_or_rows, pd.DataFrame):
        frame_or_rows.to_csv(path, index=False, encoding="utf-8")
        return
    rows = list(frame_or_rows)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(row.get(key), ensure_ascii=False) if isinstance(row.get(key), (dict, list)) else row.get(key, "") for key in fields})


def write_json(path: Path, data: Any) -> None:
    if path.exists():
        raise FileExistsError(f"No se sobrescribe {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def try_parquet(path: Path, frame: pd.DataFrame, warnings: list[dict[str, Any]]) -> bool:
    try:
        frame.to_parquet(path, index=False)
        return True
    except Exception as exc:
        warnings.append({"code": "PARQUET_UNAVAILABLE", "message": f"No se genero {path.name}: {exc}"})
        return False


def data_dictionary() -> list[dict[str, str]]:
    return [
        {"dataset": "system_hourly", "column": "importaciones_status/exportaciones_status", "description": "Estado horario: REPORTED_VALUE, EXPLICIT_ZERO, STRUCTURAL_ZERO_INFERRED, UNKNOWN_EMPTY_WINDOW o UNKNOWN_MISSING_OR_INVALID"},
        {"dataset": "system_hourly", "column": "importaciones_imputed/exportaciones_imputed", "description": "True solo cuando el valor es STRUCTURAL_ZERO_INFERRED"},
        {"dataset": "system_hourly", "column": "balance_quality_flag", "description": "COMPLETE si no hay UNKNOWN en intercambios; UNKNOWN_INTERCHANGE en caso contrario"},
        {"dataset": "system_daily_model_ready", "column": "todas", "description": "Dias sin UNKNOWN y con balance calculable"},
    ]


def write_dataset_v2(
    output_dir: Path,
    frames: dict[str, pd.DataFrame],
    audit: dict[str, Any],
    policy: dict[str, Any],
    warnings: list[dict[str, Any]],
) -> dict[str, Any]:
    class_df = audit["classification"]
    by_target = output_dir / "by_target"
    for target in ALL_TARGETS:
        write_csv(by_target / f"{target}.csv", frames[target])
    hourly = build_hourly_v2(frames, class_df)
    daily, ready, excluded = build_daily_v2(frames, hourly, DEFAULT_START_DATE, DEFAULT_END_DATE)
    structural = class_df[class_df["status"].eq("STRUCTURAL_ZERO_INFERRED")].copy()
    write_csv(output_dir / "system_hourly.csv", hourly)
    write_csv(output_dir / "system_daily_all.csv", daily)
    write_csv(output_dir / "system_daily_model_ready.csv", ready)
    write_csv(output_dir / "system_daily_excluded.csv", excluded)
    write_csv(output_dir / "data_dictionary.csv", data_dictionary())
    write_csv(output_dir / "source_manifest.csv", source_manifest(frames))
    write_csv(output_dir / "excluded_dates.csv", excluded)
    write_csv(output_dir / "empty_windows.csv", audit["empty"])
    write_csv(output_dir / "structural_zeros.csv", structural)
    parquet_files = []
    for name, frame in [("system_hourly", hourly), ("system_daily_all", daily), ("system_daily_model_ready", ready), ("system_daily_excluded", excluded)]:
        parquet_path = output_dir / f"{name}.parquet"
        if try_parquet(parquet_path, frame, warnings):
            parquet_files.append(str(parquet_path.relative_to(ROOT)))
    manifest = {
        "dataset_version": output_dir.name,
        "requested_period": [DEFAULT_START_DATE, DEFAULT_END_DATE],
        "effective_period": [str(daily["fecha"].min()), str(daily["fecha"].max())],
        "targets": ALL_TARGETS,
        "rows_by_output": {
            "system_hourly": int(len(hourly)),
            "system_daily_all": int(len(daily)),
            "system_daily_model_ready": int(len(ready)),
            "system_daily_excluded": int(len(excluded)),
        },
        "records_by_target": {target: int(len(frames[target])) for target in ALL_TARGETS},
        "structural_zeros": int(len(structural)),
        "unknown_values": int(class_df["status"].isin(["UNKNOWN_EMPTY_WINDOW", "UNKNOWN_MISSING_OR_INVALID"]).sum()),
        "policy": policy,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source_sha256": source_manifest(frames),
        "warnings": warnings,
        "parquet_files": parquet_files,
    }
    write_json(output_dir / "dataset_manifest.json", manifest)
    (output_dir / "README.md").write_text(readme_v2(output_dir.name), encoding="utf-8")
    return {
        "hourly": hourly,
        "daily": daily,
        "ready": ready,
        "excluded": excluded,
        "structural": structural,
        "parquet_files": parquet_files,
    }


def source_manifest(frames: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for target, frame in frames.items():
        if frame.empty or "source_file" not in frame.columns:
            continue
        for source_file, group in frame.groupby("source_file"):
            rows.append(
                {
                    "target": target,
                    "source_file": source_file,
                    "source_sha256": group["source_sha256"].dropna().iloc[0] if "source_sha256" in group and not group["source_sha256"].dropna().empty else "",
                    "records": int(len(group)),
                }
            )
    return rows


def readme_v2(dataset_name: str) -> str:
    return f"""# XM Sistema historico {dataset_name}

Version con politica explicita de faltantes en importaciones y exportaciones.

- `STRUCTURAL_ZERO_INFERRED` se usa solo dentro de respuestas JSON validas y no vacias.
- `UNKNOWN_EMPTY_WINDOW` conserva ventanas completas `Items: []`; no se imputan como cero.
- `Hour01` se interpreta como la primera hora del dia y `Hour24` como la hora 23:00, sin asignar zona horaria.
"""


def write_policy(path: Path, policy: dict[str, Any]) -> None:
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8-sig"))
        if existing != policy:
            raise FileExistsError(f"No se sobrescribe politica existente distinta: {path}")
        return
    write_json(path, policy)


def execute(args: argparse.Namespace, command: str) -> dict[str, Any]:
    run_dir = versioned_path(args.run_dir)
    output_dir = versioned_path(args.output_dir, dataset=True)
    audit = audit_interchanges()
    status, warnings, errors = decide_policy(audit)
    frames = load_v1_frames()
    hourly_probe = build_hourly_v2(frames, audit["classification"])
    strict = balance_variant(hourly_probe, frames, "STRICT_OBSERVED_ONLY")
    structural = balance_variant(hourly_probe, frames, "CANDIDATE_STRUCTURAL_ZERO")
    unsafe = balance_variant(hourly_probe, frames, "UNSAFE_ALL_MISSING_ZERO")
    comparison = pd.DataFrame(
        [
            variant_stats(strict, "STRICT_OBSERVED_ONLY"),
            variant_stats(structural, "CANDIDATE_STRUCTURAL_ZERO"),
            variant_stats(unsafe, "UNSAFE_ALL_MISSING_ZERO"),
        ]
    )
    dataset_info: dict[str, Any] = {}
    policy = build_policy_file(status)
    if status in {"STRUCTURAL_ZERO_POLICY_VALIDATED", "STRUCTURAL_ZERO_POLICY_VALIDATED_WITH_WARNINGS"}:
        write_policy(ROOT / "config/xm_missing_value_policy.json", policy)
        dataset_info = write_dataset_v2(output_dir, frames, audit, policy, warnings)
    run_dir.mkdir(parents=True, exist_ok=False)
    write_csv(run_dir / "patrones_importaciones.csv", [audit["patterns"]["importaciones_energia_sistema"]])
    write_csv(run_dir / "patrones_exportaciones.csv", [audit["patterns"]["exportaciones_energia_sistema"]])
    write_csv(run_dir / "horas_faltantes.csv", audit["missing"])
    write_csv(run_dir / "ceros_explicitos.csv", audit["zeros"])
    write_csv(run_dir / "ventanas_vacias.csv", audit["empty"])
    write_csv(run_dir / "clasificacion_horaria.csv", audit["classification"])
    write_csv(run_dir / "comparacion_politicas.csv", comparison)
    write_csv(run_dir / "balance_strict.csv", strict)
    write_csv(run_dir / "balance_structural_zero.csv", structural)
    write_csv(run_dir / "balance_all_missing_zero_diagnostic.csv", unsafe)
    write_csv(run_dir / "dias_excluidos.csv", dataset_info.get("excluded", pd.DataFrame()))
    write_csv(run_dir / "advertencias.csv", warnings)
    write_csv(run_dir / "errores.csv", errors)
    summary = build_summary(status, audit, comparison, dataset_info, output_dir if dataset_info else None, run_dir, warnings, errors)
    write_json(run_dir / "resumen_auditoria_intercambios.json", summary)
    (run_dir / "conclusion_politica_faltantes.md").write_text(conclusion(summary), encoding="utf-8")
    (run_dir / "comando_ejecutado.txt").write_text(command + "\n", encoding="utf-8")
    return summary


def build_summary(
    status: str,
    audit: dict[str, Any],
    comparison: pd.DataFrame,
    dataset_info: dict[str, Any],
    output_dir: Path | None,
    run_dir: Path,
    warnings: list[dict[str, Any]],
    errors: list[dict[str, Any]],
) -> dict[str, Any]:
    class_df = audit["classification"]
    before = comparison[comparison["variant"].eq("STRICT_OBSERVED_ONLY")].iloc[0].to_dict()
    after = comparison[comparison["variant"].eq("CANDIDATE_STRUCTURAL_ZERO")].iloc[0].to_dict()
    return {
        "status": status,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "run_dir": str(run_dir.relative_to(ROOT)),
        "processed_dir": str(output_dir.relative_to(ROOT)) if output_dir else "",
        "patterns": audit["patterns"],
        "explicit_zeros": int(class_df["status"].eq("EXPLICIT_ZERO").sum()),
        "missing_hours_by_target": class_df[class_df["status"].isin(["STRUCTURAL_ZERO_INFERRED", "UNKNOWN_EMPTY_WINDOW", "UNKNOWN_MISSING_OR_INVALID"])].groupby("target").size().astype(int).to_dict(),
        "empty_windows": int(len(audit["empty"])),
        "structural_zeros_inferred": int(class_df["status"].eq("STRUCTURAL_ZERO_INFERRED").sum()),
        "unknown_values_kept": int(class_df["status"].isin(["UNKNOWN_EMPTY_WINDOW", "UNKNOWN_MISSING_OR_INVALID"]).sum()),
        "model_ready_days": int(len(dataset_info.get("ready", []))) if dataset_info else 0,
        "excluded_days": int(len(dataset_info.get("excluded", []))) if dataset_info else 0,
        "balance_before_mean_abs_relative": before.get("mean_abs_relative"),
        "balance_after_mean_abs_relative": after.get("mean_abs_relative"),
        "comparison": comparison.to_dict("records"),
        "warnings": warnings,
        "errors": errors,
        "parquet_files": dataset_info.get("parquet_files", []),
    }


def conclusion(summary: dict[str, Any]) -> str:
    return f"""# Politica de faltantes en intercambios XM

Estado: **{summary['status']}**

- Ceros explicitos observados: {summary['explicit_zeros']}
- Ceros estructurales inferidos: {summary['structural_zeros_inferred']}
- Valores desconocidos conservados: {summary['unknown_values_kept']}
- Dias model-ready: {summary['model_ready_days']}
- Dias excluidos: {summary['excluded_days']}
- Directorio V2: `{summary['processed_dir']}`

Las ventanas completas `Items: []` permanecen como `UNKNOWN_EMPTY_WINDOW` y no se convierten en cero.
"""


def exact_command(argv: list[str] | None) -> str:
    if argv is not None:
        return subprocess.list2cmdline([Path(sys.executable).name, "scripts/12_auditar_intercambios_xm.py", *argv])
    return subprocess.list2cmdline([Path(sys.executable).name, *sys.argv])


def dry_run(args: argparse.Namespace) -> int:
    print("Auditoria XM intercambios dry-run")
    print(f"Periodo: {args.start_date} a {args.end_date}")
    for target in INTERCHANGE_TARGETS:
        print(f"{target}: ruta={raw_dir_for(target).relative_to(ROOT)} json={len(list_interchange_files(target))}")
    print(f"Run dir solicitado: {args.run_dir}")
    print(f"Output dir solicitado: {args.output_dir}")
    print("No se escribieron reportes ni datasets.")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.dry_run:
        return dry_run(args)
    if not args.execute:
        print("ERROR: use --execute para escribir la auditoria; sin --execute no se escribe.", file=sys.stderr)
        return 2
    summary = execute(args, exact_command(argv))
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary["status"] != "STRUCTURAL_ZERO_POLICY_BLOCKED" else 3


if __name__ == "__main__":
    raise SystemExit(main())

