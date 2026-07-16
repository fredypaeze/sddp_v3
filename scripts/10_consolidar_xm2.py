from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from minenergia_sddp.data.xm_checkpoints import sha256_file
from minenergia_sddp.data.xm_pilot import derive_units_contextual, normalize_xm_response, resolve_effective_unit

DEFAULT_START_DATE = "2023-01-01"
DEFAULT_END_DATE = "2026-07-13"
DEFAULT_RUN_DIR = "outputs/run_011"
DEFAULT_OUTPUT_DIR = "data/processed/xm/system_historical_v1"
VALIDATION_RUN = ROOT / "outputs/run_010_v002"

TARGETS = {
    "demanda_real_sistema_horaria": {"domain": "demanda", "metric_id": "DemaReal", "entity": "Sistema", "periodicity": "HourlyEntities", "unit": "kWh"},
    "demanda_sin_diaria": {"domain": "demanda", "metric_id": "DemaSIN", "entity": "Sistema", "periodicity": "DailyEntities", "unit": "kWh"},
    "generacion_real_total": {"domain": "generacion", "metric_id": "Gene", "entity": "Sistema", "periodicity": "HourlyEntities", "unit": "kWh"},
    "importaciones_energia_sistema": {"domain": "intercambios", "metric_id": "ImpoEner", "entity": "Sistema", "periodicity": "HourlyEntities", "unit": "kWh"},
    "exportaciones_energia_sistema": {"domain": "intercambios", "metric_id": "ExpoEner", "entity": "Sistema", "periodicity": "HourlyEntities", "unit": "kWh"},
}
HOURLY_TARGETS = ["demanda_real_sistema_horaria", "generacion_real_total", "importaciones_energia_sistema", "exportaciones_energia_sistema"]
FILENAME_RE = re.compile(r"^(?P<target>.+)__(?P<start>\d{4}-\d{2}-\d{2})__(?P<end>\d{4}-\d{2}-\d{2})__b(?P<batch>\d{3})(?:_v\d{3})?\.json$")
SUBSTANTIVE_COLUMNS = ["Date", "Hour", "code", "Value", "Value_GWh", "target", "metric_id", "entity", "periodicity", "unit_catalog", "unit_effective"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Consolida localmente el bloque historico XM de Sistema ya validado.")
    parser.add_argument("--dry-run", action="store_true", help="Inspecciona el plan sin escribir datasets ni reportes finales.")
    parser.add_argument("--execute", action="store_true", help="Autoriza escritura local de datasets consolidados y run report.")
    parser.add_argument("--start-date", default=DEFAULT_START_DATE)
    parser.add_argument("--end-date", default=DEFAULT_END_DATE)
    parser.add_argument("--run-dir", default=DEFAULT_RUN_DIR)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    return parser


def parse_date(value: str):
    return datetime.strptime(value, "%Y-%m-%d").date()


def date_windows(start: str, end: str, step_days: int = 30) -> list[tuple[str, str]]:
    current = parse_date(start)
    close_all = parse_date(end)
    windows = []
    while current <= close_all:
        close = min(current + timedelta(days=step_days - 1), close_all)
        windows.append((current.isoformat(), close.isoformat()))
        current = close + timedelta(days=1)
    return windows


def raw_dir_for(target: str) -> Path:
    return ROOT / "data/raw/xm" / TARGETS[target]["domain"] / target


def list_raw_files(target: str) -> list[Path]:
    root = raw_dir_for(target)
    return sorted(path for path in root.glob("*.json") if not path.name.startswith("_checkpoint"))


def versioned_path(path_text: str, *, dataset: bool = False) -> Path:
    requested = ROOT / path_text
    if not requested.exists():
        return requested
    parent = requested.parent
    name = requested.name
    if dataset and name.endswith("_v1"):
        prefix = name[:-2]
        index = 2
        while True:
            candidate = parent / f"{prefix}v{index}"
            if not candidate.exists():
                return candidate
            index += 1
    index = 2
    while True:
        candidate = requested.with_name(f"{name}_v{index:03d}")
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


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def exact_command(argv: list[str] | None = None) -> str:
    if argv is not None:
        return subprocess.list2cmdline([Path(sys.executable).name, "scripts/10_consolidar_xm2.py", *argv])
    return subprocess.list2cmdline([Path(sys.executable).name, *sys.argv])


def git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "-c", "safe.directory=D:/Proyectos/minenergia/sddp_v3", "rev-parse", "HEAD"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def inspect_plan(start_date: str, end_date: str) -> dict[str, Any]:
    expected = len(date_windows(start_date, end_date))
    return {
        "period": [start_date, end_date],
        "expected_windows_per_target": expected,
        "targets": {
            target: {"raw_dir": str(raw_dir_for(target).relative_to(ROOT)), "json_files": len(list_raw_files(target))}
            for target in TARGETS
        },
        "validation_run": str(VALIDATION_RUN.relative_to(ROOT)),
    }


def dry_run(args: argparse.Namespace) -> int:
    plan = inspect_plan(args.start_date, args.end_date)
    print("Consolidacion XM Sistema dry-run")
    print(f"Periodo: {args.start_date} a {args.end_date}")
    print(f"Run dir solicitado: {args.run_dir}")
    print(f"Output dir solicitado: {args.output_dir}")
    print(f"Ventanas esperadas por target: {plan['expected_windows_per_target']}")
    for target, info in plan["targets"].items():
        print(f"{target}: ruta={info['raw_dir']} json={info['json_files']}")
    print("No se escribieron datasets ni reportes finales.")
    return 0


def normalize_file(target: str, path: Path) -> tuple[pd.DataFrame, dict[str, Any], dict[str, Any] | None]:
    spec = TARGETS[target]
    window = parse_file_window(path)
    sha = sha256_file(path)
    data = read_json(path)
    source = {
        "target": target,
        "source_file": str(path.relative_to(ROOT)),
        "source_sha256": sha,
        "window_start": window.get("start", ""),
        "window_end": window.get("end", ""),
        "metric_id": spec["metric_id"],
        "records": 0,
        "empty_items": False,
    }
    items = data.get("Items") if isinstance(data, dict) else data
    if isinstance(items, list) and not items:
        source["empty_items"] = True
        empty = {
            "target": target,
            "source_file": source["source_file"],
            "source_sha256": sha,
            "window_start": source["window_start"],
            "window_end": source["window_end"],
            "classification": "NO_REPORTED_VALUES",
        }
        return pd.DataFrame(), source, empty
    frame = normalize_xm_response(data, spec["periodicity"])
    frame = derive_units_contextual(frame, target=target, metric_id=spec["metric_id"], entity=spec["entity"], catalog_unit=spec["unit"])
    if frame.empty:
        source["empty_items"] = True
        return frame, source, {**source, "classification": "NO_REPORTED_VALUES"}
    frame["target"] = target
    frame["metric_id"] = spec["metric_id"]
    frame["entity"] = spec["entity"]
    frame["periodicity"] = spec["periodicity"]
    frame["source_file"] = source["source_file"]
    frame["source_sha256"] = sha
    frame["window_start"] = source["window_start"]
    frame["window_end"] = source["window_end"]
    source["records"] = int(len(frame))
    return frame, source, None


def load_all_sources() -> tuple[dict[str, pd.DataFrame], list[dict[str, Any]], list[dict[str, Any]]]:
    frames: dict[str, pd.DataFrame] = {}
    sources: list[dict[str, Any]] = []
    empty_windows: list[dict[str, Any]] = []
    for target in TARGETS:
        parts = []
        for path in list_raw_files(target):
            frame, source, empty = normalize_file(target, path)
            sources.append(source)
            if empty:
                empty_windows.append(empty)
            if not frame.empty:
                parts.append(frame)
        frames[target] = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    return frames, sources, empty_windows


def key_columns(target: str) -> list[str]:
    return ["Date", "Hour", "code"] if target in HOURLY_TARGETS else ["Date", "code"]


def split_duplicates(target: str, frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    keys = key_columns(target)
    if frame.empty:
        return frame, pd.DataFrame(), pd.DataFrame()
    duplicate_mask = frame.duplicated(subset=keys, keep=False)
    if not duplicate_mask.any():
        return frame.sort_values(keys).reset_index(drop=True), pd.DataFrame(), pd.DataFrame()
    duplicate_rows = frame.loc[duplicate_mask].copy()
    exact_cols = [col for col in SUBSTANTIVE_COLUMNS if col in duplicate_rows.columns]
    exact_duplicates = duplicate_rows.loc[duplicate_rows.duplicated(subset=exact_cols, keep=False)].copy()
    conflict_groups = []
    for _, group in duplicate_rows.groupby(keys, dropna=False):
        substantive = group[[col for col in ["Value", "Value_GWh"] if col in group.columns]].drop_duplicates()
        if len(substantive) > 1:
            conflict_groups.append(group)
    conflicts = pd.concat(conflict_groups, ignore_index=True) if conflict_groups else pd.DataFrame()
    if not conflicts.empty:
        return frame, exact_duplicates, conflicts
    deduped = frame.drop_duplicates(subset=exact_cols, keep="first").sort_values(keys).reset_index(drop=True)
    return deduped, exact_duplicates, conflicts


def hour_number(hour_value: Any) -> int | None:
    match = re.search(r"(\d{1,2})", str(hour_value))
    if not match:
        return None
    number = int(match.group(1))
    return number if 1 <= number <= 24 else None


def add_timestamp(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["hora_xm"] = result["Hour"]
    nums = result["Hour"].apply(hour_number)
    dates = pd.to_datetime(result["Date"], errors="coerce")
    result["timestamp"] = [
        (date + pd.Timedelta(hours=int(num) - 1)).isoformat() if pd.notna(date) and num else ""
        for date, num in zip(dates, nums)
    ]
    return result


def hourly_piece(frame: pd.DataFrame, value_col: str, reported_col: str, source_col: str) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["Date", "Hour", value_col, reported_col, source_col])
    piece = frame[["Date", "Hour", "code", "Value_GWh", "source_file"]].copy()
    piece = piece.rename(columns={"Value_GWh": value_col, "source_file": source_col})
    piece[reported_col] = piece[value_col].notna()
    return piece[["Date", "Hour", "code", value_col, reported_col, source_col]]


def build_system_hourly(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    base = hourly_piece(frames["demanda_real_sistema_horaria"], "demanda_real_gwh", "demanda_real_reportada", "fuente_demanda")
    base = base.rename(columns={"code": "code"})
    pieces = [
        hourly_piece(frames["generacion_real_total"], "generacion_total_gwh", "generacion_reportada", "fuente_generacion"),
        hourly_piece(frames["importaciones_energia_sistema"], "importaciones_gwh", "importaciones_reportadas", "fuente_importaciones"),
        hourly_piece(frames["exportaciones_energia_sistema"], "exportaciones_gwh", "exportaciones_reportadas", "fuente_exportaciones"),
    ]
    merged = base
    for piece in pieces:
        merged = merged.merge(piece, on=["Date", "Hour", "code"], how="outer")
    for col in ["demanda_real_reportada", "generacion_reportada", "importaciones_reportadas", "exportaciones_reportadas"]:
        merged[col] = merged[col].fillna(False).astype(bool)
    complete_balance = merged[["generacion_total_gwh", "importaciones_gwh", "exportaciones_gwh"]].notna().all(axis=1)
    merged["generacion_neta_intercambios_gwh"] = pd.NA
    merged.loc[complete_balance, "generacion_neta_intercambios_gwh"] = (
        merged.loc[complete_balance, "generacion_total_gwh"]
        + merged.loc[complete_balance, "importaciones_gwh"]
        - merged.loc[complete_balance, "exportaciones_gwh"]
    )
    merged["datos_completos_balance"] = merged[["demanda_real_gwh", "generacion_total_gwh", "importaciones_gwh", "exportaciones_gwh"]].notna().all(axis=1)
    merged = add_timestamp(merged)
    merged = merged.rename(columns={"Date": "fecha"})
    columns = [
        "fecha", "hora_xm", "timestamp", "demanda_real_gwh", "generacion_total_gwh", "importaciones_gwh", "exportaciones_gwh",
        "generacion_neta_intercambios_gwh", "demanda_real_reportada", "generacion_reportada", "importaciones_reportadas",
        "exportaciones_reportadas", "datos_completos_balance", "fuente_demanda", "fuente_generacion", "fuente_importaciones", "fuente_exportaciones",
    ]
    return merged[columns].sort_values(["fecha", "hora_xm"]).reset_index(drop=True)


def aggregate_daily_from_hourly(hourly: pd.DataFrame) -> pd.DataFrame:
    agg = hourly.groupby("fecha", as_index=False).agg(
        demanda_real_gwh=("demanda_real_gwh", "sum"),
        generacion_total_gwh=("generacion_total_gwh", "sum"),
        importaciones_gwh=("importaciones_gwh", "sum"),
        exportaciones_gwh=("exportaciones_gwh", "sum"),
        horas_demanda_real=("demanda_real_reportada", "sum"),
        horas_generacion=("generacion_reportada", "sum"),
        horas_importaciones=("importaciones_reportadas", "sum"),
        horas_exportaciones=("exportaciones_reportadas", "sum"),
    )
    for value_col, hour_col in [
        ("demanda_real_gwh", "horas_demanda_real"),
        ("generacion_total_gwh", "horas_generacion"),
        ("importaciones_gwh", "horas_importaciones"),
        ("exportaciones_gwh", "horas_exportaciones"),
    ]:
        agg.loc[agg[hour_col].eq(0), value_col] = pd.NA
    return agg


def build_system_daily(frames: dict[str, pd.DataFrame], hourly: pd.DataFrame, start_date: str, end_date: str) -> pd.DataFrame:
    days = pd.DataFrame({"fecha": pd.date_range(start_date, end_date, freq="D").date.astype(str)})
    demand_sin = frames["demanda_sin_diaria"].copy()
    demand_sin["fecha"] = pd.to_datetime(demand_sin["Date"], errors="coerce").dt.date.astype(str)
    demand_sin = demand_sin.groupby("fecha", as_index=False)["Value_GWh"].sum().rename(columns={"Value_GWh": "demanda_sin_gwh"})
    daily = days.merge(demand_sin, on="fecha", how="left").merge(aggregate_daily_from_hourly(hourly), on="fecha", how="left")
    daily["demanda_sin_reportada"] = daily["demanda_sin_gwh"].notna()
    daily["demanda_real_completa"] = daily["horas_demanda_real"].eq(24)
    daily["generacion_completa"] = daily["horas_generacion"].eq(24)
    daily["importaciones_completas"] = daily["horas_importaciones"].eq(24)
    daily["exportaciones_completas"] = daily["horas_exportaciones"].eq(24)
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
    daily["datos_completos_balance"] = daily[["demanda_sin_reportada", "generacion_completa", "importaciones_completas", "exportaciones_completas"]].all(axis=1)
    daily["advertencias_dia"] = ""
    daily.loc[~daily["importaciones_completas"], "advertencias_dia"] = "importaciones_incompletas_o_no_reportadas"
    return daily


def exclusions(daily: pd.DataFrame) -> pd.DataFrame:
    reasons = []
    for _, row in daily.iterrows():
        items = []
        if not bool(row["demanda_sin_reportada"]):
            items.append("demanda_sin_no_reportada")
        if not bool(row["generacion_completa"]):
            items.append("generacion_incompleta")
        if not bool(row["importaciones_completas"]):
            items.append("importaciones_no_reportadas_o_incompletas")
        if not bool(row["exportaciones_completas"]):
            items.append("exportaciones_incompletas")
        if not bool(row["datos_completos_balance"]):
            items.append("balance_no_calculable")
        if items:
            reasons.append({"fecha": row["fecha"], "motivo_exclusion": ";".join(items)})
    return pd.DataFrame(reasons)


def validate_keys(name: str, frame: pd.DataFrame, keys: list[str]) -> dict[str, Any]:
    return {"dataset": name, "rows": int(len(frame)), "duplicate_keys": int(frame.duplicated(subset=keys).sum()), "unique_keys": int(frame[keys].drop_duplicates().shape[0]) if not frame.empty else 0}


def write_csv(path: Path, frame_or_rows: Any) -> None:
    if path.exists():
        raise FileExistsError(f"No se sobrescribe {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(frame_or_rows, pd.DataFrame):
        frame_or_rows.to_csv(path, index=False, encoding="utf-8")
    else:
        rows = list(frame_or_rows)
        fields = []
        for row in rows:
            for key in row:
                if key not in fields:
                    fields.append(key)
        with path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                writer.writerow({key: json.dumps(row.get(key), ensure_ascii=False) if isinstance(row.get(key), (list, dict)) else row.get(key, "") for key in fields})


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


def balance_stats(daily: pd.DataFrame) -> dict[str, Any]:
    dem = pd.to_numeric(daily["diferencia_demareal_demasin_pct"], errors="coerce").abs()
    bal = pd.to_numeric(daily["diferencia_balance_pct"], errors="coerce").abs()
    return {
        "mean_abs_dema_real_vs_dema_sin_rel": float(dem.mean()),
        "mean_abs_balance_rel": float(bal.mean()),
        "balance_abs_error_p50": float(bal.quantile(0.50)),
        "balance_abs_error_p95": float(bal.quantile(0.95)),
        "balance_abs_error_p99": float(bal.quantile(0.99)),
        "days_balance_abs_gt_1pct": int((bal > 0.01).sum()),
        "days_balance_abs_gt_2pct": int((bal > 0.02).sum()),
        "days_balance_abs_gt_5pct": int((bal > 0.05).sum()),
    }


def build_readme(output_dir: Path, dataset_name: str) -> str:
    return f"""# XM Sistema historico {dataset_name}

Periodo: {DEFAULT_START_DATE} a {DEFAULT_END_DATE}

Convencion horaria: `Hour01` se representa como la primera hora del dia y se convierte a `timestamp` sin zona horaria como fecha 00:00. `Hour24` se representa como fecha 23:00. No se altera la zona horaria por falta de evidencia adicional.

Las importaciones con ventanas `Items: []` se conservan como evidencia en `empty_windows.csv`; no se imputan como cero.
"""


def data_dictionary() -> list[dict[str, str]]:
    return [
        {"dataset": "system_hourly", "column": "fecha", "description": "Fecha XM local reportada"},
        {"dataset": "system_hourly", "column": "hora_xm", "description": "Etiqueta horaria XM Hour01..Hour24"},
        {"dataset": "system_hourly", "column": "timestamp", "description": "Timestamp naive construido como fecha + hora_xm-1"},
        {"dataset": "system_hourly", "column": "*_gwh", "description": "Energia en GWh derivada desde kWh / 1.000.000"},
        {"dataset": "system_daily_all", "column": "*_completa", "description": "Indica 24 horas reportadas o dato diario presente segun corresponda"},
        {"dataset": "system_daily_model_ready", "column": "todas", "description": "Dias con demanda SIN, generacion, importaciones y exportaciones suficientes para balance"},
    ]


def consolidate(args: argparse.Namespace, command: str) -> dict[str, Any]:
    output_dir = versioned_path(args.output_dir, dataset=True)
    run_dir = versioned_path(args.run_dir, dataset=False)
    frames, source_rows, empty_rows = load_all_sources()
    deduped: dict[str, pd.DataFrame] = {}
    exact_dups = []
    conflicts = []
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    for target, frame in frames.items():
        clean, exact, conflict = split_duplicates(target, frame)
        deduped[target] = clean
        if not exact.empty:
            exact_dups.extend(exact.to_dict("records"))
        if not conflict.empty:
            conflicts.extend(conflict.to_dict("records"))
            errors.append({"code": "CONFLICTING_DUPLICATES", "target": target, "message": f"{len(conflict)} filas duplicadas conflictivas"})
    if errors:
        status = "CONSOLIDATION_BLOCKED"
    else:
        by_target_dir = output_dir / "by_target"
        for target, frame in deduped.items():
            write_csv(by_target_dir / f"{target}.csv", frame)
        hourly = build_system_hourly(deduped)
        daily = build_system_daily(deduped, hourly, args.start_date, args.end_date)
        excluded = exclusions(daily)
        ready = daily.loc[daily["datos_completos_balance"]].copy()
        write_csv(output_dir / "system_hourly.csv", hourly)
        write_csv(output_dir / "system_daily_all.csv", daily)
        write_csv(output_dir / "system_daily_model_ready.csv", ready)
        write_csv(output_dir / "system_daily_excluded.csv", excluded)
        write_csv(output_dir / "source_manifest.csv", source_rows)
        write_csv(output_dir / "empty_windows.csv", empty_rows)
        write_csv(output_dir / "excluded_dates.csv", excluded)
        write_csv(output_dir / "data_dictionary.csv", data_dictionary())
        parquet_files = []
        for name, frame in [("system_hourly", hourly), ("system_daily_all", daily), ("system_daily_model_ready", ready), ("system_daily_excluded", excluded)]:
            parquet_path = output_dir / f"{name}.parquet"
            if try_parquet(parquet_path, frame, warnings):
                parquet_files.append(str(parquet_path.relative_to(ROOT)))
        output_files = sorted(str(path.relative_to(ROOT)) for path in output_dir.glob("**/*") if path.is_file())
        stats = balance_stats(daily)
        manifest = {
            "dataset_version": output_dir.name,
            "requested_period": [args.start_date, args.end_date],
            "effective_period": [str(daily["fecha"].min()), str(daily["fecha"].max())],
            "targets": list(TARGETS),
            "source_files": len(source_rows),
            "json_count": len(source_rows),
            "source_sha256": [{"source_file": row["source_file"], "sha256": row["source_sha256"]} for row in source_rows],
            "records_by_target": {target: int(len(frame)) for target, frame in deduped.items()},
            "unit_catalog": "kWh",
            "unit_effective": "kWh",
            "conversion_formula": "Value_GWh = Value / 1.000.000",
            "rows_by_output": {"system_hourly": int(len(hourly)), "system_daily_all": int(len(daily)), "system_daily_model_ready": int(len(ready)), "system_daily_excluded": int(len(excluded))},
            "complete_days": int(len(ready)),
            "excluded_days": int(len(excluded)),
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "commit": git_commit(),
            "warnings": warnings + [{"code": "NO_REPORTED_VALUES", **row} for row in empty_rows],
        }
        write_json(output_dir / "dataset_manifest.json", manifest)
        (output_dir / "README.md").write_text(build_readme(output_dir, output_dir.name), encoding="utf-8")
        status = "CONSOLIDATION_VALIDATED_WITH_WARNINGS" if warnings or empty_rows or len(excluded) else "CONSOLIDATION_VALIDATED"
    if errors:
        hourly = pd.DataFrame(); daily = pd.DataFrame(); ready = pd.DataFrame(); excluded = pd.DataFrame(); parquet_files = []; output_files = [] ; stats = {}
    run_dir.mkdir(parents=True, exist_ok=False)
    output_rows = [{"path": item} for item in output_files]
    key_rows = []
    if not errors:
        key_rows = [validate_keys("system_hourly", hourly, ["fecha", "hora_xm"]), validate_keys("system_daily_all", daily, ["fecha"]), validate_keys("system_daily_model_ready", ready, ["fecha"])]
    coverage_rows = [{"target": target, "json_files": len(list_raw_files(target)), "records": int(len(deduped.get(target, pd.DataFrame()))), "date_min": str(deduped[target]["Date"].min()) if not deduped[target].empty else "", "date_max": str(deduped[target]["Date"].max()) if not deduped[target].empty else ""} for target in TARGETS]
    daily_stats_rows = [stats] if stats else []
    write_json(run_dir / "resumen_consolidacion.json", {
        "status": status,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "processed_dir": str(output_dir.relative_to(ROOT)),
        "run_dir": str(run_dir.relative_to(ROOT)),
        "json_by_target": {target: len(list_raw_files(target)) for target in TARGETS},
        "records_by_target": {target: int(len(deduped.get(target, pd.DataFrame()))) for target in TARGETS},
        "system_hourly_rows": int(len(hourly)) if not errors else 0,
        "system_daily_all_rows": int(len(daily)) if not errors else 0,
        "system_daily_model_ready_rows": int(len(ready)) if not errors else 0,
        "excluded_days": int(len(excluded)) if not errors else 0,
        "empty_windows": len(empty_rows),
        "exact_duplicates": len(exact_dups),
        "conflicting_duplicates": len(conflicts),
        "balance_stats": stats,
        "parquet_files": parquet_files,
    })
    write_csv(run_dir / "manifest_archivos_entrada.csv", source_rows)
    write_csv(run_dir / "archivos_salida.csv", output_rows)
    write_csv(run_dir / "duplicados_exactos.csv", exact_dups)
    write_csv(run_dir / "duplicados_conflictivos.csv", conflicts)
    write_csv(run_dir / "ventanas_vacias.csv", empty_rows)
    write_csv(run_dir / "dias_excluidos.csv", excluded if not errors else pd.DataFrame())
    write_csv(run_dir / "validacion_cobertura.csv", coverage_rows)
    write_csv(run_dir / "validacion_claves.csv", key_rows)
    write_csv(run_dir / "estadisticas_diarias.csv", daily_stats_rows)
    write_csv(run_dir / "balance_diario.csv", daily if not errors else pd.DataFrame())
    write_csv(run_dir / "advertencias.csv", warnings + [{"code": "NO_REPORTED_VALUES", **row} for row in empty_rows])
    write_csv(run_dir / "errores.csv", errors)
    (run_dir / "conclusion_consolidacion.md").write_text(conclusion(status, output_dir, len(ready) if not errors else 0, len(excluded) if not errors else 0, empty_rows, errors, warnings), encoding="utf-8")
    (run_dir / "comando_ejecutado.txt").write_text(command + "\n", encoding="utf-8")
    return json.loads((run_dir / "resumen_consolidacion.json").read_text(encoding="utf-8"))


def conclusion(status: str, output_dir: Path, ready_days: int, excluded_days: int, empty_rows: list[dict[str, Any]], errors: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> str:
    return f"""# Consolidacion historica XM Sistema

Estado: **{status}**

Directorio procesado: `{output_dir.relative_to(ROOT)}`

- Dias model-ready: {ready_days}
- Dias excluidos: {excluded_days}
- Ventanas vacias conservadas: {len(empty_rows)}
- Errores bloqueantes: {len(errors)}
- Advertencias: {len(warnings) + len(empty_rows)}

No se hicieron solicitudes HTTP, no se modificaron JSON crudos y no se consolidaron bloques adicionales.
"""


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.dry_run:
        return dry_run(args)
    if not args.execute:
        print("ERROR: use --execute para escribir datasets consolidados; sin --execute no se escribe.", file=sys.stderr)
        return 2
    summary = consolidate(args, exact_command(argv))
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary["status"] != "CONSOLIDATION_BLOCKED" else 3


if __name__ == "__main__":
    raise SystemExit(main())
