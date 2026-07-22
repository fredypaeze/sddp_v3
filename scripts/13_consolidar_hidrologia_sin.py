from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from minenergia_sddp.data.xm_checkpoints import sha256_file
from minenergia_sddp.data.xm_pilot import derive_units_contextual, normalize_xm_response


DEFAULT_START_DATE = "2010-01-01"
DEFAULT_END_DATE = "2026-07-13"
DEFAULT_OUTPUT_BASE = "data/processed/xm/hydro_system_historical"
DEFAULT_RUN_BASE = "outputs/run_013"

TARGETS: dict[str, dict[str, str]] = {
    "aportes": {
        "target": "aportes_energia_sin",
        "domain": "aportes",
        "metric_id": "AporEner",
        "entity": "Sistema",
        "periodicity": "DailyEntities",
        "unit": "kWh",
        "value_prefix": "aportes_energia",
    },
    "volumen": {
        "target": "volumen_util_energia_sin",
        "domain": "embalses",
        "metric_id": "VoluUtilDiarEner",
        "entity": "Sistema",
        "periodicity": "DailyEntities",
        "unit": "kWh",
        "value_prefix": "volumen_util_energia",
    },
    "capacidad": {
        "target": "capacidad_util_energia_sin",
        "domain": "embalses",
        "metric_id": "CapaUtilDiarEner",
        "entity": "Sistema",
        "periodicity": "DailyEntities",
        "unit": "kWh",
        "value_prefix": "capacidad_util_energia",
    },
}

FILENAME_RE = re.compile(
    r"^(?P<target>.+)__(?P<start>\d{4}-\d{2}-\d{2})__(?P<end>\d{4}-\d{2}-\d{2})__b(?P<batch>\d{3})(?:_v\d{3})?\.json$"
)

DAILY_COLUMNS = [
    "date",
    "aportes_energia_kwh",
    "aportes_energia_gwh",
    "volumen_util_energia_kwh",
    "volumen_util_energia_gwh",
    "capacidad_util_energia_kwh",
    "capacidad_util_energia_gwh",
    "porcentaje_volumen_util_calculado",
    "cambio_diario_volumen_gwh",
    "cambio_diario_capacidad_gwh",
    "source_file_aportes",
    "source_file_volumen",
    "source_file_capacidad",
    "quality_status",
    "quality_issues",
    "model_ready",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Consolida hidrologia energetica agregada del SIN desde JSON XM locales.")
    parser.add_argument("--dry-run", action="store_true", help="Inspecciona entradas y versiones sin escribir.")
    parser.add_argument("--execute", action="store_true", help="Autoriza escritura local versionada.")
    parser.add_argument("--start-date", default=DEFAULT_START_DATE)
    parser.add_argument("--end-date", default=DEFAULT_END_DATE)
    parser.add_argument("--output-base", default=DEFAULT_OUTPUT_BASE)
    parser.add_argument("--run-base", default=DEFAULT_RUN_BASE)
    return parser


def raw_dir_for(spec: dict[str, str]) -> Path:
    return ROOT / "data/raw/xm" / spec["domain"] / spec["target"]


def list_raw_files(spec: dict[str, str]) -> list[Path]:
    root = raw_dir_for(spec)
    return sorted(path for path in root.glob("*.json") if not path.name.startswith("_checkpoint"))


def parse_window(path: Path) -> dict[str, str]:
    match = FILENAME_RE.match(path.name)
    if not match:
        return {"window_start": "", "window_end": "", "batch": "", "filename_valid": "False"}
    groups = match.groupdict()
    return {
        "window_start": groups["start"],
        "window_end": groups["end"],
        "batch": groups["batch"],
        "filename_valid": "True",
    }


def versioned_dataset_path(base_text: str) -> Path:
    base = ROOT / base_text
    parent = base.parent
    stem = base.name
    index = 1
    while True:
        candidate = parent / f"{stem}_v{index}"
        if not candidate.exists():
            return candidate
        index += 1


def versioned_run_path(base_text: str) -> Path:
    requested = ROOT / base_text
    if not requested.exists():
        return requested
    index = 2
    while True:
        candidate = requested.with_name(f"{requested.name}_v{index:03d}")
        if not candidate.exists():
            return candidate
        index += 1


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def safe_write_text(path: Path, text: str) -> None:
    if path.exists():
        raise FileExistsError(f"No se sobrescribe archivo existente: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def safe_write_json(path: Path, data: Any) -> None:
    safe_write_text(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def safe_write_csv(path: Path, frame_or_rows: Any, columns: list[str] | None = None) -> None:
    if path.exists():
        raise FileExistsError(f"No se sobrescribe archivo existente: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(frame_or_rows, pd.DataFrame):
        frame = frame_or_rows.copy()
        if columns is not None:
            for col in columns:
                if col not in frame.columns:
                    frame[col] = pd.NA
            frame = frame[columns]
        frame.to_csv(path, index=False, encoding="utf-8")
        return
    rows = list(frame_or_rows)
    fields = columns or []
    if not fields:
        for row in rows:
            for key in row:
                if key not in fields:
                    fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: json.dumps(row.get(key), ensure_ascii=False) if isinstance(row.get(key), (dict, list)) else row.get(key, "")
                    for key in fields
                }
            )


def safe_write_parquet(path: Path, frame: pd.DataFrame) -> None:
    if path.exists():
        raise FileExistsError(f"No se sobrescribe archivo existente: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)


def file_sha256(path: Path) -> str:
    return sha256_file(path)


def dataframe_digest(frame: pd.DataFrame) -> str:
    ordered = frame.copy()
    text = ordered.to_csv(index=False, lineterminator="\n")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def output_manifest_row(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.relative_to(ROOT)),
        "name": path.name,
        "bytes": path.stat().st_size,
        "sha256": file_sha256(path),
    }


def git_value(args: list[str]) -> str:
    try:
        result = subprocess.run(
            ["git", "-c", "safe.directory=D:/Proyectos/minenergia/sddp_v3", *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def exact_command(argv: list[str] | None = None) -> str:
    if argv is None:
        return subprocess.list2cmdline([Path(sys.executable).name, *sys.argv])
    return subprocess.list2cmdline([Path(sys.executable).name, "scripts/13_consolidar_hidrologia_sin.py", *argv])


def normalize_source_file(label: str, spec: dict[str, str], path: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    source_hash = file_sha256(path)
    data = read_json(path)
    frame = normalize_xm_response(data, spec["periodicity"])
    frame = derive_units_contextual(
        frame,
        target=spec["target"],
        metric_id=spec["metric_id"],
        entity=spec["entity"],
        catalog_unit=spec["unit"],
    )
    window = parse_window(path)
    source = {
        "logical_name": label,
        "target": spec["target"],
        "metric_id": spec["metric_id"],
        "entity": spec["entity"],
        "periodicity": spec["periodicity"],
        "unit_catalog": spec["unit"],
        "unit_effective": spec["unit"],
        "source_file": str(path.relative_to(ROOT)),
        "source_name": path.name,
        "source_sha256": source_hash,
        "records": int(len(frame)),
        **window,
    }
    if frame.empty:
        return frame, source
    frame["source_file"] = source["source_file"]
    frame["source_sha256"] = source_hash
    frame["target"] = spec["target"]
    return frame, source


def normalize_target(label: str, spec: dict[str, str]) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    frames: list[pd.DataFrame] = []
    sources: list[dict[str, Any]] = []
    for path in list_raw_files(spec):
        frame, source = normalize_source_file(label, spec, path)
        sources.append(source)
        if not frame.empty:
            frames.append(frame)
    combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return combined, sources


def target_daily_frame(label: str, spec: dict[str, str], frame: pd.DataFrame) -> pd.DataFrame:
    prefix = spec["value_prefix"]
    columns = ["date", f"{prefix}_kwh", f"{prefix}_gwh", f"source_file_{label}"]
    if frame.empty:
        return pd.DataFrame(columns=columns)
    result = frame.copy()
    result["date"] = pd.to_datetime(result["Date"], errors="coerce").dt.date.astype(str)
    result[f"{prefix}_kwh"] = pd.to_numeric(result["Value"], errors="coerce")
    result[f"{prefix}_gwh"] = pd.to_numeric(result["Value_GWh"], errors="coerce")
    result = result.rename(columns={"source_file": f"source_file_{label}"})
    return result[columns]


def duplicate_dates(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty or "date" not in frame.columns:
        return pd.DataFrame(columns=["date", "count"])
    counts = frame.groupby("date").size().reset_index(name="count")
    return counts.loc[counts["count"] > 1].copy()


def build_daily_dataset(target_frames: dict[str, pd.DataFrame], start_date: str, end_date: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    days = pd.DataFrame({"date": pd.date_range(start_date, end_date, freq="D").date.astype(str)})
    duplicates: list[pd.DataFrame] = []
    merged = days
    for label, spec in TARGETS.items():
        daily = target_daily_frame(label, spec, target_frames[label])
        dup = duplicate_dates(daily)
        if not dup.empty:
            dup["target"] = spec["target"]
            duplicates.append(dup[["target", "date", "count"]])
        deduped = daily.drop_duplicates(subset=["date"], keep="first")
        merged = merged.merge(deduped, on="date", how="left", validate="one_to_one")
    merged["porcentaje_volumen_util_calculado"] = (
        merged["volumen_util_energia_gwh"] / merged["capacidad_util_energia_gwh"] * 100.0
    )
    merged = merged.sort_values("date").reset_index(drop=True)
    merged["cambio_diario_volumen_gwh"] = merged["volumen_util_energia_gwh"].diff()
    merged["cambio_diario_capacidad_gwh"] = merged["capacidad_util_energia_gwh"].diff()
    merged = apply_quality_rules(merged)
    dup_frame = pd.concat(duplicates, ignore_index=True) if duplicates else pd.DataFrame(columns=["target", "date", "count"])
    return merged[DAILY_COLUMNS], dup_frame


def apply_quality_rules(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    issues_by_row: list[list[str]] = []
    for _, row in result.iterrows():
        issues: list[str] = []
        required = [
            "date",
            "aportes_energia_kwh",
            "aportes_energia_gwh",
            "volumen_util_energia_kwh",
            "volumen_util_energia_gwh",
            "capacidad_util_energia_kwh",
            "capacidad_util_energia_gwh",
            "porcentaje_volumen_util_calculado",
            "source_file_aportes",
            "source_file_volumen",
            "source_file_capacidad",
        ]
        for col in required:
            if pd.isna(row.get(col)) or row.get(col) == "":
                issues.append(f"missing_{col}")
        if pd.notna(row.get("aportes_energia_gwh")) and row["aportes_energia_gwh"] < 0:
            issues.append("aportes_negativos")
        if pd.notna(row.get("volumen_util_energia_gwh")) and row["volumen_util_energia_gwh"] < 0:
            issues.append("volumen_negativo")
        if pd.notna(row.get("capacidad_util_energia_gwh")) and row["capacidad_util_energia_gwh"] <= 0:
            issues.append("capacidad_no_positiva")
        if pd.notna(row.get("volumen_util_energia_gwh")) and pd.notna(row.get("capacidad_util_energia_gwh")):
            if row["volumen_util_energia_gwh"] > row["capacidad_util_energia_gwh"]:
                issues.append("volumen_mayor_que_capacidad")
        if pd.notna(row.get("porcentaje_volumen_util_calculado")):
            pct = row["porcentaje_volumen_util_calculado"]
            if pct < 0 or pct > 100:
                issues.append("porcentaje_fuera_de_rango")
        issues_by_row.append(issues)
    result["quality_issues"] = [";".join(issues) for issues in issues_by_row]
    result["quality_status"] = ["OK" if not issues else "ERROR" for issues in issues_by_row]
    result["model_ready"] = result["quality_status"].eq("OK")
    return result


def validation_rows(daily: pd.DataFrame, duplicates: pd.DataFrame, sources: list[dict[str, Any]], args: argparse.Namespace) -> dict[str, list[dict[str, Any]]]:
    main_cols = [
        "aportes_energia_kwh",
        "aportes_energia_gwh",
        "volumen_util_energia_kwh",
        "volumen_util_energia_gwh",
        "capacidad_util_energia_kwh",
        "capacidad_util_energia_gwh",
        "porcentaje_volumen_util_calculado",
    ]
    coverage = []
    for label, spec in TARGETS.items():
        target_sources = [row for row in sources if row["logical_name"] == label]
        records = sum(int(row["records"]) for row in target_sources)
        coverage.append(
            {
                "target": spec["target"],
                "json_files": len(target_sources),
                "records": records,
                "expected_json_files": 202,
                "expected_records": 6038,
                "date_min": str(daily["date"].min()) if not daily.empty else "",
                "date_max": str(daily["date"].max()) if not daily.empty else "",
                "status": "OK" if len(target_sources) == 202 and records == 6038 else "ERROR",
            }
        )
    keys = [
        {
            "dataset": "hydro_system_daily_all",
            "rows": int(len(daily)),
            "unique_dates": int(daily["date"].nunique()) if "date" in daily else 0,
            "duplicate_dates": int(daily.duplicated(subset=["date"]).sum()) if "date" in daily else 0,
            "target_duplicate_dates": int(len(duplicates)),
            "union_one_to_one": bool(len(duplicates) == 0 and len(daily) == daily["date"].nunique()),
        }
    ]
    ranges = [
        {"check": "period_start", "value": str(daily["date"].min()), "expected": args.start_date, "status": "OK" if str(daily["date"].min()) == args.start_date else "ERROR"},
        {"check": "period_end", "value": str(daily["date"].max()), "expected": args.end_date, "status": "OK" if str(daily["date"].max()) == args.end_date else "ERROR"},
        {"check": "rows", "value": int(len(daily)), "expected": 6038, "status": "OK" if len(daily) == 6038 else "ERROR"},
        {"check": "nulls_main", "value": int(daily[main_cols].isna().sum().sum()), "expected": 0, "status": "OK" if int(daily[main_cols].isna().sum().sum()) == 0 else "ERROR"},
        {"check": "aportes_non_negative", "value": int((daily["aportes_energia_gwh"] < 0).sum()), "expected": 0, "status": "OK" if int((daily["aportes_energia_gwh"] < 0).sum()) == 0 else "ERROR"},
        {"check": "volumen_non_negative", "value": int((daily["volumen_util_energia_gwh"] < 0).sum()), "expected": 0, "status": "OK" if int((daily["volumen_util_energia_gwh"] < 0).sum()) == 0 else "ERROR"},
        {"check": "capacidad_positive", "value": int((daily["capacidad_util_energia_gwh"] <= 0).sum()), "expected": 0, "status": "OK" if int((daily["capacidad_util_energia_gwh"] <= 0).sum()) == 0 else "ERROR"},
        {"check": "volumen_le_capacidad", "value": int((daily["volumen_util_energia_gwh"] > daily["capacidad_util_energia_gwh"]).sum()), "expected": 0, "status": "OK" if int((daily["volumen_util_energia_gwh"] > daily["capacidad_util_energia_gwh"]).sum()) == 0 else "ERROR"},
        {"check": "pct_between_0_100", "value": int(((daily["porcentaje_volumen_util_calculado"] < 0) | (daily["porcentaje_volumen_util_calculado"] > 100)).sum()), "expected": 0, "status": "OK" if int(((daily["porcentaje_volumen_util_calculado"] < 0) | (daily["porcentaje_volumen_util_calculado"] > 100)).sum()) == 0 else "ERROR"},
        {"check": "model_ready_days", "value": int(daily["model_ready"].sum()), "expected": 6038, "status": "OK" if int(daily["model_ready"].sum()) == 6038 else "ERROR"},
        {"check": "excluded_days", "value": int((~daily["model_ready"]).sum()), "expected": 0, "status": "OK" if int((~daily["model_ready"]).sum()) == 0 else "ERROR"},
    ]
    return {"coverage": coverage, "keys": keys, "ranges": ranges}


def build_quality_summary(daily: pd.DataFrame, ranges: list[dict[str, Any]], duplicates: pd.DataFrame) -> dict[str, Any]:
    errors = [row for row in ranges if row["status"] == "ERROR"]
    return {
        "status": "OK" if not errors and duplicates.empty and daily["quality_status"].eq("OK").all() else "ERROR",
        "rows": int(len(daily)),
        "unique_dates": int(daily["date"].nunique()),
        "model_ready_days": int(daily["model_ready"].sum()),
        "excluded_days": int((~daily["model_ready"]).sum()),
        "quality_status_counts": daily["quality_status"].value_counts(dropna=False).to_dict(),
        "min_pct": float(daily["porcentaje_volumen_util_calculado"].min()),
        "max_pct": float(daily["porcentaje_volumen_util_calculado"].max()),
        "mean_pct": float(daily["porcentaje_volumen_util_calculado"].mean()),
        "capacity_change_days": int(daily["cambio_diario_capacidad_gwh"].dropna().ne(0).sum()),
        "blocking_errors": len(errors) + int(len(duplicates)),
    }


def capacity_changes(daily: pd.DataFrame) -> pd.DataFrame:
    cols = ["date", "capacidad_util_energia_gwh", "cambio_diario_capacidad_gwh", "quality_status", "model_ready"]
    changes = daily.loc[daily["cambio_diario_capacidad_gwh"].notna() & daily["cambio_diario_capacidad_gwh"].ne(0), cols].copy()
    changes["abs_cambio_diario_capacidad_gwh"] = changes["cambio_diario_capacidad_gwh"].abs()
    return changes.sort_values("abs_cambio_diario_capacidad_gwh", ascending=False).reset_index(drop=True)


def volume_events(daily: pd.DataFrame, ascending: bool) -> pd.DataFrame:
    cols = ["date", "volumen_util_energia_gwh", "cambio_diario_volumen_gwh", "quality_status", "model_ready"]
    events = daily.loc[daily["cambio_diario_volumen_gwh"].notna(), cols].copy()
    return events.sort_values("cambio_diario_volumen_gwh", ascending=ascending).reset_index(drop=True)


def data_dictionary_rows() -> list[dict[str, str]]:
    descriptions = {
        "date": "Fecha operativa XM en calendario local.",
        "aportes_energia_kwh": "Aportes energeticos agregados del SIN en kWh, valor original XM.",
        "aportes_energia_gwh": "Aportes energeticos agregados del SIN en GWh = kWh / 1.000.000.",
        "volumen_util_energia_kwh": "Volumen util energetico agregado del SIN en kWh, valor original XM.",
        "volumen_util_energia_gwh": "Volumen util energetico agregado del SIN en GWh = kWh / 1.000.000.",
        "capacidad_util_energia_kwh": "Capacidad util energetica agregada del SIN en kWh, valor original XM.",
        "capacidad_util_energia_gwh": "Capacidad util energetica agregada del SIN en GWh = kWh / 1.000.000.",
        "porcentaje_volumen_util_calculado": "volumen_util_energia_gwh / capacidad_util_energia_gwh * 100 para la misma fecha.",
        "cambio_diario_volumen_gwh": "Diferencia diaria de volumen util energetico; nulo en la primera fecha.",
        "cambio_diario_capacidad_gwh": "Diferencia diaria de capacidad util energetica; nulo en la primera fecha.",
        "source_file_aportes": "JSON fuente de aportes usado para la fecha.",
        "source_file_volumen": "JSON fuente de volumen usado para la fecha.",
        "source_file_capacidad": "JSON fuente de capacidad usado para la fecha.",
        "quality_status": "OK, WARNING o ERROR segun reglas definidas del bloque.",
        "quality_issues": "Lista separada por punto y coma de reglas incumplidas.",
        "model_ready": "True si la fecha tiene cobertura y consistencia fisica basica validas.",
    }
    return [{"dataset": "hydro_system_daily_all", "column": col, "description": descriptions[col]} for col in DAILY_COLUMNS]


def build_readme(dataset_name: str, args: argparse.Namespace, quality: dict[str, Any]) -> str:
    return f"""# Hidrologia energetica SIN {dataset_name}

Dataset agregado diario del SIN construido desde JSON historicos XM locales.

- Periodo: {args.start_date} a {args.end_date}
- Unidad original/effectiva: kWh
- Conversion: GWh = kWh / 1.000.000
- Porcentaje: volumen util energetico diario / capacidad util energetica diaria * 100
- Filas: {quality['rows']}
- Dias model-ready: {quality['model_ready_days']}
- Dias excluidos: {quality['excluded_days']}

Los cambios diarios grandes de volumen o capacidad se reportan como eventos, pero no se clasifican automaticamente como advertencia o error.
"""


def dry_run(args: argparse.Namespace) -> int:
    output_dir = versioned_dataset_path(args.output_base)
    run_dir = versioned_run_path(args.run_base)
    print("Consolidacion hidrologia SIN dry-run")
    print(f"Periodo: {args.start_date} a {args.end_date}")
    print(f"Dataset propuesto: {output_dir.relative_to(ROOT)}")
    print(f"Run propuesto: {run_dir.relative_to(ROOT)}")
    for label, spec in TARGETS.items():
        print(f"{label}: target={spec['target']} ruta={raw_dir_for(spec).relative_to(ROOT)} json={len(list_raw_files(spec))}")
    print("No se escribieron datasets ni reportes.")
    return 0


def consolidate(args: argparse.Namespace, command: str) -> dict[str, Any]:
    output_dir = versioned_dataset_path(args.output_base)
    run_dir = versioned_run_path(args.run_base)
    if output_dir.exists() or run_dir.exists():
        raise FileExistsError("La version calculada ya existe; reintente para recalcular version libre.")
    run_dir.mkdir(parents=True, exist_ok=False)
    output_dir.mkdir(parents=True, exist_ok=False)

    source_hashes_before: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    target_frames: dict[str, pd.DataFrame] = {}
    for label, spec in TARGETS.items():
        files = list_raw_files(spec)
        for path in files:
            source_hashes_before.append(
                {
                    "logical_name": label,
                    "target": spec["target"],
                    "source_file": str(path.relative_to(ROOT)),
                    "source_name": path.name,
                    "sha256": file_sha256(path),
                    **parse_window(path),
                }
            )
        frame, target_sources = normalize_target(label, spec)
        target_frames[label] = frame
        sources.extend(target_sources)

    daily, duplicates = build_daily_dataset(target_frames, args.start_date, args.end_date)
    ready = daily.loc[daily["model_ready"]].copy()
    excluded = daily.loc[~daily["model_ready"]].copy()
    validations = validation_rows(daily, duplicates, sources, args)
    quality = build_quality_summary(daily, validations["ranges"], duplicates)
    warnings: list[dict[str, Any]] = []
    errors = [row for group in validations.values() for row in group if row.get("status") == "ERROR"]
    if not duplicates.empty:
        errors.extend(duplicates.to_dict("records"))

    safe_write_csv(output_dir / "hydro_system_daily_all.csv", daily, DAILY_COLUMNS)
    safe_write_csv(output_dir / "hydro_system_daily_model_ready.csv", ready, DAILY_COLUMNS)
    safe_write_csv(output_dir / "hydro_system_daily_excluded.csv", excluded, DAILY_COLUMNS)
    safe_write_parquet(output_dir / "hydro_system_daily_all.parquet", daily[DAILY_COLUMNS])
    safe_write_parquet(output_dir / "hydro_system_daily_model_ready.parquet", ready[DAILY_COLUMNS])
    safe_write_parquet(output_dir / "hydro_system_daily_excluded.parquet", excluded[DAILY_COLUMNS])
    safe_write_csv(output_dir / "source_manifest.csv", sources)
    safe_write_csv(output_dir / "data_dictionary.csv", data_dictionary_rows())
    safe_write_json(output_dir / "quality_summary.json", quality)
    cap_changes = capacity_changes(daily)
    volume_decreases = volume_events(daily, ascending=True)
    volume_increases = volume_events(daily, ascending=False)
    safe_write_csv(output_dir / "capacity_changes.csv", cap_changes)
    safe_write_csv(output_dir / "largest_volume_increases.csv", volume_increases)
    safe_write_csv(output_dir / "largest_volume_decreases.csv", volume_decreases)

    output_files = sorted(path for path in output_dir.glob("**/*") if path.is_file())
    output_hashes = [output_manifest_row(path) for path in output_files]
    manifest = {
        "dataset_version": output_dir.name,
        "run_version": run_dir.name,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "command": command,
        "git_branch": git_value(["branch", "--show-current"]),
        "git_head": git_value(["rev-parse", "HEAD"]),
        "requested_period": [args.start_date, args.end_date],
        "effective_period": [str(daily["date"].min()), str(daily["date"].max())],
        "targets": [spec["target"] for spec in TARGETS.values()],
        "json_source_files": len(sources),
        "source_sha256": sources,
        "output_sha256": output_hashes,
        "dataset_digest_sha256": dataframe_digest(daily[DAILY_COLUMNS]),
        "rows_by_output": {
            "hydro_system_daily_all": int(len(daily)),
            "hydro_system_daily_model_ready": int(len(ready)),
            "hydro_system_daily_excluded": int(len(excluded)),
        },
        "quality_summary": quality,
    }
    safe_write_json(output_dir / "dataset_manifest.json", manifest)
    safe_write_text(output_dir / "README.md", build_readme(output_dir.name, args, quality))

    # README and manifest are relevant outputs too; refresh output manifest for run evidence.
    output_files = sorted(path for path in output_dir.glob("**/*") if path.is_file())
    output_hashes = [output_manifest_row(path) for path in output_files]
    source_hashes_after = []
    for row in source_hashes_before:
        path = ROOT / row["source_file"]
        source_hashes_after.append({**row, "sha256": file_sha256(path)})
    hashes_unchanged = all(before["sha256"] == after["sha256"] for before, after in zip(source_hashes_before, source_hashes_after))

    safe_write_json(
        run_dir / "resumen_consolidacion_hidrologia.json",
        {
            "status": quality["status"],
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "dataset_version": output_dir.name,
            "run_version": run_dir.name,
            "processed_dir": str(output_dir.relative_to(ROOT)),
            "run_dir": str(run_dir.relative_to(ROOT)),
            "rows_by_output": manifest["rows_by_output"],
            "period": manifest["effective_period"],
            "json_source_files": len(sources),
            "hashes_source_unchanged": hashes_unchanged,
            "errors": len(errors),
            "warnings": len(warnings),
            "quality_summary": quality,
        },
    )
    safe_write_csv(run_dir / "validacion_cobertura.csv", validations["coverage"])
    safe_write_csv(run_dir / "validacion_claves.csv", validations["keys"])
    safe_write_csv(run_dir / "validacion_rangos.csv", validations["ranges"])
    safe_write_csv(run_dir / "archivos_salida.csv", output_hashes)
    safe_write_csv(run_dir / "errores.csv", errors)
    safe_write_csv(run_dir / "advertencias.csv", warnings)
    safe_write_csv(run_dir / "eventos_cambio_capacidad.csv", cap_changes)
    safe_write_csv(run_dir / "eventos_cambio_volumen.csv", volume_events(daily, ascending=False))
    safe_write_csv(run_dir / "hashes_fuentes_antes.csv", source_hashes_before)
    safe_write_csv(run_dir / "hashes_fuentes_despues.csv", source_hashes_after)
    safe_write_text(run_dir / "comando_ejecutado.txt", command + "\n")
    return json.loads((run_dir / "resumen_consolidacion_hidrologia.json").read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.dry_run:
        return dry_run(args)
    if not args.execute:
        print("ERROR: use --execute para escribir el dataset consolidado; sin --execute no se escribe.", file=sys.stderr)
        return 2
    summary = consolidate(args, exact_command(argv))
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary["status"] == "OK" else 3


if __name__ == "__main__":
    raise SystemExit(main())
