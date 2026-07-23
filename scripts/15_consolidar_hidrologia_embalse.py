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

from minenergia_sddp.data.xm_pilot import normalize_xm_response


DEFAULT_START_DATE = "2010-01-01"
DEFAULT_END_DATE = "2026-07-13"
DEFAULT_OUTPUT_BASE = "data/processed/xm/hydro_reservoir_historical"
DEFAULT_RUN_BASE = "outputs/run_015"

EXPECTED_RESERVOIRS = [
    "AGREGADO BOGOTA",
    "ALTOANCHICAYA",
    "AMANI",
    "BETANIA",
    "CALIMA1",
    "CHUZA",
    "EL QUIMBO",
    "ESMERALDA",
    "FLORIDA II",
    "GUAVIO",
    "ITUANGO",
    "MIRAFLORES",
    "MUNA",
    "PENOL",
    "PLAYAS",
    "PORCE II",
    "PORCE III",
    "PRADO",
    "PUNCHINA",
    "RIOGRANDE2",
    "SALVAJINA",
    "SAN LORENZO",
    "TOPOCORO",
    "TRONERAS",
    "URRA1",
]

TARGETS: dict[str, dict[str, str]] = {
    "volumen": {
        "target": "volumen_util_energia_embalse",
        "domain": "embalses",
        "metric_id": "VoluUtilDiarEner",
        "entity": "Embalse",
        "periodicity": "DailyEntities",
        "unit_catalog": "kWh",
        "kind": "energy",
    },
    "capacidad": {
        "target": "capacidad_util_energia_embalse",
        "domain": "embalses",
        "metric_id": "CapaUtilDiarEner",
        "entity": "Embalse",
        "periodicity": "DailyEntities",
        "unit_catalog": "kWh",
        "kind": "energy",
    },
    "porcentaje": {
        "target": "porcentaje_volumen_util_embalse",
        "domain": "embalses",
        "metric_id": "PorcVoluUtilDiar",
        "entity": "Embalse",
        "periodicity": "DailyEntities",
        "unit_catalog": "%",
        "kind": "fraction",
    },
}

EXPECTED_DEFAULT_PERIOD = {
    "json_files_per_target": 606,
    "records_by_label": {
        "volumen": 135467,
        "capacidad": 135957,
        "porcentaje": 135467,
    },
    "rows_union": 135957,
    "observed_reservoirs": 24,
    "catalog_without_data": ["FLORIDA II"],
    "incomplete_rows": 490,
    "negative_rows": 4,
    "model_ready_rows": 135463,
    "excluded_rows": 494,
    "official_pct_above_100": 7290,
    "volume_above_capacity": 7342,
}

CANONICAL_FILENAME_RE = re.compile(
    r"^(?P<target>.+)__(?P<start>\d{4}-\d{2}-\d{2})__(?P<end>\d{4}-\d{2}-\d{2})__b(?P<batch>\d{3})\.json$"
)

DAILY_COLUMNS = [
    "date",
    "reservoir_code",
    "reservoir_name",
    "volumen_util_energia_kwh",
    "volumen_util_energia_gwh",
    "capacidad_util_energia_kwh",
    "capacidad_util_energia_gwh",
    "porcentaje_volumen_util_oficial_raw",
    "porcentaje_volumen_util_oficial",
    "porcentaje_volumen_util_calculado",
    "diferencia_porcentajes_pp",
    "cambio_diario_volumen_gwh",
    "cambio_diario_capacidad_gwh",
    "source_file_volumen",
    "source_file_capacidad",
    "source_file_porcentaje",
    "quality_status",
    "quality_issues",
    "model_ready",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Consolida hidrologia energetica diaria por embalse desde JSON XM locales."
    )
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
    files: list[Path] = []
    for path in sorted(root.glob("*.json")):
        if path.name.startswith("_checkpoint"):
            continue
        match = CANONICAL_FILENAME_RE.match(path.name)
        if match and match.group("target") == spec["target"]:
            files.append(path)
    return files


def parse_window(path: Path) -> dict[str, str]:
    match = CANONICAL_FILENAME_RE.match(path.name)
    if not match:
        return {
            "window_start": "",
            "window_end": "",
            "batch": "",
            "filename_valid": "False",
        }
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
    base = ROOT / base_text
    if not base.exists():
        return base
    index = 2
    while True:
        candidate = base.parent / f"{base.name}_v{index:03d}"
        if not candidate.exists():
            return candidate
        index += 1


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def safe_write_text(path: Path, text: str) -> None:
    if path.exists():
        raise FileExistsError(f"No se sobrescribe: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def safe_write_json(path: Path, data: Any) -> None:
    safe_write_text(path, json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n")


def safe_write_csv(
    path: Path,
    frame_or_rows: Any,
    columns: list[str] | None = None,
) -> None:
    if path.exists():
        raise FileExistsError(f"No se sobrescribe: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(frame_or_rows, pd.DataFrame):
        frame = frame_or_rows.copy()
        if columns is not None:
            frame = frame.reindex(columns=columns)
        frame.to_csv(path, index=False, encoding="utf-8")
        return

    rows = list(frame_or_rows)
    if rows:
        fieldnames = columns or sorted({key for row in rows for key in row})
    else:
        fieldnames = columns or []
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if fieldnames:
            writer.writeheader()
            writer.writerows(rows)


def safe_write_parquet(path: Path, frame: pd.DataFrame) -> None:
    if path.exists():
        raise FileExistsError(f"No se sobrescribe: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dataframe_digest(frame: pd.DataFrame) -> str:
    canonical = frame.copy()
    canonical = canonical.reindex(sorted(canonical.columns), axis=1)
    payload = canonical.to_csv(index=False, lineterminator="\n", na_rep="<NA>")
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def output_manifest_row(path: Path) -> dict[str, Any]:
    return {
        "file": str(path.relative_to(ROOT)),
        "bytes": path.stat().st_size,
        "sha256": file_sha256(path),
    }


def git_value(args: list[str]) -> str:
    try:
        completed = subprocess.run(
            ["git", "-c", f"safe.directory={ROOT.as_posix()}", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return ""
    return completed.stdout.strip() if completed.returncode == 0 else ""


def exact_command(argv: list[str] | None = None) -> str:
    values = [sys.executable, str(Path(__file__).resolve())]
    values.extend(sys.argv[1:] if argv is None else argv)
    return subprocess.list2cmdline(values)


def normalize_source_file(
    label: str,
    spec: dict[str, str],
    path: Path,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    source_hash = file_sha256(path)
    payload = read_json(path)
    response_metric_id = str(payload.get("Metric", {}).get("Id", ""))
    frame = normalize_xm_response(payload, spec["periodicity"])
    window = parse_window(path)
    source = {
        "logical_name": label,
        "target": spec["target"],
        "metric_id_expected": spec["metric_id"],
        "metric_id_response": response_metric_id,
        "metric_id_match": response_metric_id == spec["metric_id"],
        "entity": spec["entity"],
        "periodicity": spec["periodicity"],
        "unit_catalog": spec["unit_catalog"],
        "unit_effective": (
            "fraction_0_1; normalized_percent=value*100"
            if spec["kind"] == "fraction"
            else "kWh; GWh=value/1e6"
        ),
        "source_file": str(path.relative_to(ROOT)),
        "source_name": path.name,
        "source_sha256": source_hash,
        "records": int(len(frame)),
        **window,
    }
    if frame.empty:
        return frame, source

    required = {"Date", "code", "Value"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"{path.name}: faltan columnas normalizadas {sorted(missing)}")

    result = frame.copy()
    result["Date"] = pd.to_datetime(result["Date"], errors="coerce")
    result["code"] = result["code"].astype("string").str.strip()
    if "name" not in result:
        result["name"] = result["code"]
    result["name"] = result["name"].astype("string").str.strip()
    result["Value"] = pd.to_numeric(result["Value"], errors="coerce")
    result["source_file"] = source["source_file"]
    result["source_sha256"] = source_hash
    result["target"] = spec["target"]
    return result, source


def normalize_target(
    label: str,
    spec: dict[str, str],
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    frames: list[pd.DataFrame] = []
    sources: list[dict[str, Any]] = []
    for path in list_raw_files(spec):
        frame, source = normalize_source_file(label, spec, path)
        sources.append(source)
        if not frame.empty:
            frames.append(frame)
    combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return combined, sources


def target_pair_frame(
    label: str,
    spec: dict[str, str],
    frame: pd.DataFrame,
) -> pd.DataFrame:
    if spec["kind"] == "energy":
        value_columns = [
            f"{label}_util_energia_kwh",
            f"{label}_util_energia_gwh",
        ]
    else:
        value_columns = [
            "porcentaje_volumen_util_oficial_raw",
            "porcentaje_volumen_util_oficial",
        ]

    columns = [
        "date",
        "reservoir_code",
        "reservoir_name",
        *value_columns,
        f"source_file_{label}",
    ]
    if frame.empty:
        return pd.DataFrame(columns=columns)

    result = pd.DataFrame(
        {
            "date": pd.to_datetime(frame["Date"], errors="coerce").dt.strftime("%Y-%m-%d"),
            "reservoir_code": frame["code"].astype("string").str.strip(),
            "reservoir_name": frame["name"].astype("string").str.strip(),
            f"source_file_{label}": frame["source_file"].astype("string"),
        }
    )
    numeric = pd.to_numeric(frame["Value"], errors="coerce")
    if spec["kind"] == "energy":
        result[f"{label}_util_energia_kwh"] = numeric
        result[f"{label}_util_energia_gwh"] = numeric / 1_000_000.0
    else:
        result["porcentaje_volumen_util_oficial_raw"] = numeric
        result["porcentaje_volumen_util_oficial"] = numeric * 100.0
    return result[columns]


def duplicate_pairs(frame: pd.DataFrame, label: str) -> pd.DataFrame:
    columns = [
        "target",
        "date",
        "reservoir_code",
        "count",
        "distinct_values",
    ]
    if frame.empty:
        return pd.DataFrame(columns=columns)
    value_cols = [
        col
        for col in frame.columns
        if col not in {
            "date",
            "reservoir_code",
            "reservoir_name",
            f"source_file_{label}",
        }
    ]
    value_col = value_cols[0]
    grouped = (
        frame.groupby(["date", "reservoir_code"], dropna=False)
        .agg(count=(value_col, "size"), distinct_values=(value_col, "nunique"))
        .reset_index()
    )
    grouped = grouped.loc[grouped["count"] > 1].copy()
    grouped.insert(0, "target", TARGETS[label]["target"])
    return grouped[columns]


def build_daily_dataset(
    target_frames: dict[str, pd.DataFrame],
    start_date: str,
    end_date: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)

    pair_frames: dict[str, pd.DataFrame] = {}
    duplicates: list[pd.DataFrame] = []
    name_frames: list[pd.DataFrame] = []
    key_frames: list[pd.DataFrame] = []

    for label, spec in TARGETS.items():
        pair = target_pair_frame(label, spec, target_frames[label])
        pair = pair.loc[
            pd.to_datetime(pair["date"], errors="coerce").between(start, end)
        ].copy()
        dup = duplicate_pairs(pair, label)
        if not dup.empty:
            duplicates.append(dup)
        pair = pair.drop_duplicates(["date", "reservoir_code"], keep="first")
        pair_frames[label] = pair
        key_frames.append(pair[["date", "reservoir_code"]])
        name_frames.append(pair[["reservoir_code", "reservoir_name"]])

    if key_frames:
        keys = pd.concat(key_frames, ignore_index=True).drop_duplicates()
    else:
        keys = pd.DataFrame(columns=["date", "reservoir_code"])

    names = (
        pd.concat(name_frames, ignore_index=True)
        .dropna(subset=["reservoir_code"])
        .drop_duplicates("reservoir_code", keep="first")
        if name_frames
        else pd.DataFrame(columns=["reservoir_code", "reservoir_name"])
    )

    merged = keys.merge(names, on="reservoir_code", how="left", validate="many_to_one")
    for label, pair in pair_frames.items():
        value_cols = [
            col
            for col in pair.columns
            if col not in {"date", "reservoir_code", "reservoir_name"}
        ]
        merged = merged.merge(
            pair[["date", "reservoir_code", *value_cols]],
            on=["date", "reservoir_code"],
            how="left",
            validate="one_to_one",
        )

    merged["porcentaje_volumen_util_calculado"] = (
        merged["volumen_util_energia_gwh"]
        / merged["capacidad_util_energia_gwh"]
        * 100.0
    )
    merged["diferencia_porcentajes_pp"] = (
        merged["porcentaje_volumen_util_oficial"]
        - merged["porcentaje_volumen_util_calculado"]
    )

    merged["_date_dt"] = pd.to_datetime(merged["date"], errors="coerce")
    merged = merged.sort_values(["reservoir_code", "_date_dt"]).reset_index(drop=True)
    merged["cambio_diario_volumen_gwh"] = (
        merged.groupby("reservoir_code", dropna=False)["volumen_util_energia_gwh"].diff()
    )
    merged["cambio_diario_capacidad_gwh"] = (
        merged.groupby("reservoir_code", dropna=False)["capacidad_util_energia_gwh"].diff()
    )
    merged = merged.drop(columns=["_date_dt"])
    merged = apply_quality_rules(merged)

    dup_frame = (
        pd.concat(duplicates, ignore_index=True)
        if duplicates
        else pd.DataFrame(
            columns=[
                "target",
                "date",
                "reservoir_code",
                "count",
                "distinct_values",
            ]
        )
    )
    return merged.reindex(columns=DAILY_COLUMNS), dup_frame


def apply_quality_rules(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    issues_by_row: list[list[str]] = []
    status_by_row: list[str] = []
    model_ready: list[bool] = []

    required = [
        "date",
        "reservoir_code",
        "volumen_util_energia_gwh",
        "capacidad_util_energia_gwh",
        "porcentaje_volumen_util_oficial",
        "source_file_volumen",
        "source_file_capacidad",
        "source_file_porcentaje",
    ]

    for _, row in result.iterrows():
        blocking: list[str] = []
        warnings: list[str] = []

        if any(pd.isna(row.get(col)) or row.get(col) == "" for col in required):
            blocking.append("INCOMPLETO_METRICAS_REQUERIDAS")

        volume = row.get("volumen_util_energia_gwh")
        capacity = row.get("capacidad_util_energia_gwh")
        pct_official = row.get("porcentaje_volumen_util_oficial")
        pct_calculated = row.get("porcentaje_volumen_util_calculado")
        difference = row.get("diferencia_porcentajes_pp")

        if pd.notna(volume) and volume < 0:
            blocking.append("VOLUMEN_NEGATIVO")
        if pd.notna(capacity) and capacity <= 0:
            blocking.append("CAPACIDAD_NO_POSITIVA")
        if pd.notna(pct_official) and pct_official < 0:
            blocking.append("PORCENTAJE_OFICIAL_NEGATIVO")

        relation_inconsistent = False
        if pd.notna(volume) and pd.notna(capacity) and volume > capacity:
            relation_inconsistent = True
        if pd.notna(pct_official) and pct_official > 100:
            relation_inconsistent = True
        if pd.notna(pct_calculated) and pct_calculated > 100:
            relation_inconsistent = True
        if relation_inconsistent:
            warnings.append("INCONSISTENCIA_RELACION_VOLUMEN_CAPACIDAD")

        if pd.notna(difference) and abs(float(difference)) > 0.01:
            warnings.append("DIFERENCIA_PORCENTAJE_OFICIAL_CALCULADO")

        issues = list(dict.fromkeys([*blocking, *warnings]))
        issues_by_row.append(issues)
        if blocking:
            status_by_row.append("ERROR")
            model_ready.append(False)
        elif warnings:
            status_by_row.append("WARNING")
            model_ready.append(True)
        else:
            status_by_row.append("OK")
            model_ready.append(True)

    result["quality_issues"] = [";".join(issues) for issues in issues_by_row]
    result["quality_status"] = status_by_row
    result["model_ready"] = model_ready
    return result


def source_coverage_rows(
    sources: list[dict[str, Any]],
    target_frames: dict[str, pd.DataFrame],
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    is_default = (
        args.start_date == DEFAULT_START_DATE
        and args.end_date == DEFAULT_END_DATE
    )
    rows: list[dict[str, Any]] = []
    for label, spec in TARGETS.items():
        target_sources = [
            row for row in sources if row["logical_name"] == label
        ]
        records = int(len(target_frames[label]))
        expected_files = (
            EXPECTED_DEFAULT_PERIOD["json_files_per_target"]
            if is_default
            else ""
        )
        expected_records = (
            EXPECTED_DEFAULT_PERIOD["records_by_label"][label]
            if is_default
            else ""
        )
        status = "INFO"
        if is_default:
            status = (
                "OK"
                if len(target_sources) == expected_files
                and records == expected_records
                and all(row["metric_id_match"] for row in target_sources)
                else "ERROR"
            )
        rows.append(
            {
                "label": label,
                "target": spec["target"],
                "json_files": len(target_sources),
                "expected_json_files": expected_files,
                "records": records,
                "expected_records": expected_records,
                "metric_id_mismatches": sum(
                    not bool(row["metric_id_match"]) for row in target_sources
                ),
                "status": status,
            }
        )
    return rows


def reservoir_coverage(daily: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for code in EXPECTED_RESERVOIRS:
        subset = daily.loc[daily["reservoir_code"] == code]
        if subset.empty:
            rows.append(
                {
                    "reservoir_code": code,
                    "catalog_status": "ACTIVE",
                    "observed": False,
                    "date_min": "",
                    "date_max": "",
                    "rows_union": 0,
                    "rows_volume": 0,
                    "rows_capacity": 0,
                    "rows_percentage": 0,
                    "model_ready_rows": 0,
                    "excluded_rows": 0,
                    "status": "ENTIDAD_CATALOGO_SIN_REPORTE_METRICA",
                }
            )
            continue

        rows.append(
            {
                "reservoir_code": code,
                "catalog_status": "ACTIVE",
                "observed": True,
                "date_min": subset["date"].min(),
                "date_max": subset["date"].max(),
                "rows_union": int(len(subset)),
                "rows_volume": int(subset["volumen_util_energia_gwh"].notna().sum()),
                "rows_capacity": int(subset["capacidad_util_energia_gwh"].notna().sum()),
                "rows_percentage": int(
                    subset["porcentaje_volumen_util_oficial"].notna().sum()
                ),
                "model_ready_rows": int(subset["model_ready"].sum()),
                "excluded_rows": int((~subset["model_ready"]).sum()),
                "status": "OBSERVED",
            }
        )
    return pd.DataFrame(rows)


def duplicate_summary(duplicates: pd.DataFrame) -> dict[str, Any]:
    return {
        "duplicate_pairs": int(len(duplicates)),
        "conflicting_duplicate_pairs": (
            int((duplicates["distinct_values"] > 1).sum())
            if not duplicates.empty
            else 0
        ),
    }


def build_validation_rows(
    daily: pd.DataFrame,
    duplicates: pd.DataFrame,
    coverage_sources: list[dict[str, Any]],
    reservoir_cov: pd.DataFrame,
    args: argparse.Namespace,
) -> dict[str, list[dict[str, Any]]]:
    is_default = (
        args.start_date == DEFAULT_START_DATE
        and args.end_date == DEFAULT_END_DATE
    )
    duplicate_info = duplicate_summary(duplicates)
    observed = int(daily["reservoir_code"].nunique())
    catalog_without_data = sorted(
        reservoir_cov.loc[~reservoir_cov["observed"], "reservoir_code"].tolist()
    )

    keys = [
        {
            "dataset": "hydro_reservoir_daily_all",
            "rows": int(len(daily)),
            "unique_date_reservoir_pairs": int(
                daily[["date", "reservoir_code"]].drop_duplicates().shape[0]
            ),
            "duplicate_pairs_dataset": int(
                daily.duplicated(["date", "reservoir_code"]).sum()
            ),
            **duplicate_info,
            "union_one_to_one": bool(
                daily.duplicated(["date", "reservoir_code"]).sum() == 0
                and duplicates.empty
            ),
        }
    ]

    checks: list[dict[str, Any]] = []

    def add_check(
        check: str,
        value: Any,
        expected: Any,
        *,
        status: str,
        severity: str,
    ) -> None:
        checks.append(
            {
                "check": check,
                "value": value,
                "expected": expected,
                "status": status,
                "severity": severity,
            }
        )

    add_check(
        "period_start",
        str(daily["date"].min()),
        args.start_date,
        status="OK" if str(daily["date"].min()) == args.start_date else "ERROR",
        severity="BLOCKING",
    )
    add_check(
        "period_end",
        str(daily["date"].max()),
        args.end_date,
        status="OK" if str(daily["date"].max()) == args.end_date else "ERROR",
        severity="BLOCKING",
    )
    add_check(
        "duplicate_pairs",
        duplicate_info["duplicate_pairs"],
        0,
        status="OK" if duplicate_info["duplicate_pairs"] == 0 else "ERROR",
        severity="BLOCKING",
    )
    add_check(
        "observed_reservoirs",
        observed,
        EXPECTED_DEFAULT_PERIOD["observed_reservoirs"] if is_default else "",
        status=(
            "OK"
            if not is_default
            or observed == EXPECTED_DEFAULT_PERIOD["observed_reservoirs"]
            else "ERROR"
        ),
        severity="BLOCKING",
    )
    add_check(
        "catalog_without_data",
        "|".join(catalog_without_data),
        "|".join(EXPECTED_DEFAULT_PERIOD["catalog_without_data"])
        if is_default
        else "",
        status=(
            "OK"
            if not is_default
            or catalog_without_data
            == EXPECTED_DEFAULT_PERIOD["catalog_without_data"]
            else "ERROR"
        ),
        severity="BLOCKING",
    )

    metrics = {
        "rows_union": int(len(daily)),
        "incomplete_rows": int(
            daily["quality_issues"].str.contains(
                "INCOMPLETO_METRICAS_REQUERIDAS", na=False
            ).sum()
        ),
        "negative_rows": int(
            (
                (daily["volumen_util_energia_gwh"] < 0)
                | (daily["porcentaje_volumen_util_oficial"] < 0)
            ).sum()
        ),
        "model_ready_rows": int(daily["model_ready"].sum()),
        "excluded_rows": int((~daily["model_ready"]).sum()),
        "official_pct_above_100": int(
            (daily["porcentaje_volumen_util_oficial"] > 100).sum()
        ),
        "volume_above_capacity": int(
            (
                daily["volumen_util_energia_gwh"]
                > daily["capacidad_util_energia_gwh"]
            ).sum()
        ),
    }
    for name, value in metrics.items():
        expected = EXPECTED_DEFAULT_PERIOD[name] if is_default else ""
        add_check(
            name,
            value,
            expected,
            status=(
                "OK"
                if not is_default or value == EXPECTED_DEFAULT_PERIOD[name]
                else "ERROR"
            ),
            severity=(
                "BLOCKING"
                if name in {"rows_union", "model_ready_rows", "excluded_rows"}
                else "CONTROLLED"
            ),
        )

    comparable = daily.dropna(
        subset=[
            "porcentaje_volumen_util_oficial",
            "porcentaje_volumen_util_calculado",
        ]
    )
    max_diff = float(comparable["diferencia_porcentajes_pp"].abs().max())
    add_check(
        "max_abs_official_calculated_difference_pp",
        max_diff,
        "<=0.01",
        status="OK" if max_diff <= 0.01 else "ERROR",
        severity="BLOCKING",
    )

    return {
        "coverage_sources": coverage_sources,
        "keys": keys,
        "checks": checks,
    }


def issue_counts(daily: pd.DataFrame) -> dict[str, int]:
    counts: dict[str, int] = {}
    for text in daily["quality_issues"].fillna(""):
        if not text:
            continue
        for issue in text.split(";"):
            counts[issue] = counts.get(issue, 0) + 1
    return dict(sorted(counts.items()))


def build_quality_summary(
    daily: pd.DataFrame,
    validations: dict[str, list[dict[str, Any]]],
    duplicates: pd.DataFrame,
    reservoir_cov: pd.DataFrame,
) -> dict[str, Any]:
    blocking_failures = [
        row
        for group in validations.values()
        for row in group
        if row.get("status") == "ERROR"
        and row.get("severity", "BLOCKING") == "BLOCKING"
    ]
    comparable = daily.dropna(
        subset=[
            "porcentaje_volumen_util_oficial",
            "porcentaje_volumen_util_calculado",
        ]
    )
    return {
        "status": (
            "OK"
            if not blocking_failures and duplicates.empty
            else "ERROR"
        ),
        "rows": int(len(daily)),
        "unique_date_reservoir_pairs": int(
            daily[["date", "reservoir_code"]].drop_duplicates().shape[0]
        ),
        "observed_reservoirs": int(daily["reservoir_code"].nunique()),
        "catalog_reservoirs": len(EXPECTED_RESERVOIRS),
        "catalog_without_data": reservoir_cov.loc[
            ~reservoir_cov["observed"], "reservoir_code"
        ].tolist(),
        "model_ready_rows": int(daily["model_ready"].sum()),
        "excluded_rows": int((~daily["model_ready"]).sum()),
        "quality_status_counts": daily["quality_status"].value_counts(
            dropna=False
        ).to_dict(),
        "quality_issue_counts": issue_counts(daily),
        "min_official_pct": float(
            daily["porcentaje_volumen_util_oficial"].min()
        ),
        "max_official_pct": float(
            daily["porcentaje_volumen_util_oficial"].max()
        ),
        "mean_official_pct": float(
            daily["porcentaje_volumen_util_oficial"].mean()
        ),
        "mean_abs_official_calculated_difference_pp": float(
            comparable["diferencia_porcentajes_pp"].abs().mean()
        ),
        "max_abs_official_calculated_difference_pp": float(
            comparable["diferencia_porcentajes_pp"].abs().max()
        ),
        "capacity_change_events": int(
            daily["cambio_diario_capacidad_gwh"].dropna().ne(0).sum()
        ),
        "blocking_validation_failures": len(blocking_failures),
    }


def capacity_changes(daily: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "date",
        "reservoir_code",
        "reservoir_name",
        "capacidad_util_energia_gwh",
        "cambio_diario_capacidad_gwh",
        "quality_status",
        "model_ready",
    ]
    changes = daily.loc[
        daily["cambio_diario_capacidad_gwh"].notna()
        & daily["cambio_diario_capacidad_gwh"].ne(0),
        cols,
    ].copy()
    changes["abs_cambio_diario_capacidad_gwh"] = (
        changes["cambio_diario_capacidad_gwh"].abs()
    )
    return changes.sort_values(
        "abs_cambio_diario_capacidad_gwh",
        ascending=False,
    ).reset_index(drop=True)


def volume_events(daily: pd.DataFrame, ascending: bool) -> pd.DataFrame:
    cols = [
        "date",
        "reservoir_code",
        "reservoir_name",
        "volumen_util_energia_gwh",
        "cambio_diario_volumen_gwh",
        "quality_status",
        "model_ready",
    ]
    events = daily.loc[
        daily["cambio_diario_volumen_gwh"].notna(),
        cols,
    ].copy()
    return events.sort_values(
        "cambio_diario_volumen_gwh",
        ascending=ascending,
    ).reset_index(drop=True)


def percentage_inconsistencies(daily: pd.DataFrame) -> pd.DataFrame:
    mask = (
        (daily["porcentaje_volumen_util_oficial"] < 0)
        | (daily["porcentaje_volumen_util_oficial"] > 100)
        | (
            daily["volumen_util_energia_gwh"]
            > daily["capacidad_util_energia_gwh"]
        )
    )
    cols = [
        "date",
        "reservoir_code",
        "reservoir_name",
        "volumen_util_energia_gwh",
        "capacidad_util_energia_gwh",
        "porcentaje_volumen_util_oficial_raw",
        "porcentaje_volumen_util_oficial",
        "porcentaje_volumen_util_calculado",
        "diferencia_porcentajes_pp",
        "quality_status",
        "quality_issues",
        "model_ready",
    ]
    return daily.loc[mask, cols].sort_values(
        ["reservoir_code", "date"]
    ).reset_index(drop=True)


def missing_metric_pairs(daily: pd.DataFrame) -> pd.DataFrame:
    mask = daily["quality_issues"].str.contains(
        "INCOMPLETO_METRICAS_REQUERIDAS",
        na=False,
    )
    return daily.loc[mask, DAILY_COLUMNS].reset_index(drop=True)


def data_dictionary_rows() -> list[dict[str, str]]:
    descriptions = {
        "date": "Fecha operativa XM en calendario local.",
        "reservoir_code": "Codigo/nombre normalizado del embalse reportado por XM.",
        "reservoir_name": "Nombre descriptivo del embalse reportado por XM.",
        "volumen_util_energia_kwh": "Volumen util energetico por embalse en kWh, valor original XM.",
        "volumen_util_energia_gwh": "Volumen util energetico por embalse en GWh = kWh / 1.000.000.",
        "capacidad_util_energia_kwh": "Capacidad util energetica por embalse en kWh, valor original XM.",
        "capacidad_util_energia_gwh": "Capacidad util energetica por embalse en GWh = kWh / 1.000.000.",
        "porcentaje_volumen_util_oficial_raw": "Valor crudo de PorcVoluUtilDiar entregado por XM como fraccion decimal.",
        "porcentaje_volumen_util_oficial": "Porcentaje oficial normalizado = valor crudo XM * 100.",
        "porcentaje_volumen_util_calculado": "Volumen util / capacidad util * 100 para el mismo embalse y fecha.",
        "diferencia_porcentajes_pp": "Porcentaje oficial menos porcentaje calculado, en puntos porcentuales.",
        "cambio_diario_volumen_gwh": "Diferencia respecto al registro inmediatamente anterior del mismo embalse; nulo si falta alguno de los valores.",
        "cambio_diario_capacidad_gwh": "Diferencia respecto al registro inmediatamente anterior del mismo embalse; nulo si falta alguno de los valores.",
        "source_file_volumen": "JSON fuente de volumen utilizado para la pareja fecha-embalse.",
        "source_file_capacidad": "JSON fuente de capacidad utilizado para la pareja fecha-embalse.",
        "source_file_porcentaje": "JSON fuente de porcentaje oficial utilizado para la pareja fecha-embalse.",
        "quality_status": "OK, WARNING o ERROR segun reglas de calidad por fila.",
        "quality_issues": "Codigos de calidad separados por punto y coma.",
        "model_ready": "True cuando la fila tiene las metricas requeridas y no presenta una condicion bloqueante.",
    }
    return [
        {
            "dataset": "hydro_reservoir_daily_all",
            "column": column,
            "description": descriptions[column],
        }
        for column in DAILY_COLUMNS
    ]


def build_readme(
    dataset_name: str,
    args: argparse.Namespace,
    quality: dict[str, Any],
) -> str:
    return f"""# Hidrologia energetica por embalse {dataset_name}

Dataset diario por embalse construido exclusivamente desde JSON historicos XM locales.

- Periodo solicitado: {args.start_date} a {args.end_date}
- Filas union fecha-embalse: {quality['rows']}
- Embalses observados: {quality['observed_reservoirs']} de {quality['catalog_reservoirs']}
- Entidades del catalogo sin reporte: {', '.join(quality['catalog_without_data']) or 'ninguna'}
- Filas model-ready: {quality['model_ready_rows']}
- Filas excluidas: {quality['excluded_rows']}
- Unidad energetica original: kWh
- Conversion energetica: GWh = kWh / 1.000.000
- PorcVoluUtilDiar: XM entrega fraccion decimal; porcentaje oficial = valor crudo * 100
- Contraste: porcentaje calculado = volumen util / capacidad util * 100

Politica de calidad:

- Los valores negativos y las filas incompletas no ingresan al subconjunto model-ready.
- Los valores superiores a 100 % no se recortan ni se reemplazan.
- Las relaciones volumen mayor que capacidad se preservan y se marcan como
  INCONSISTENCIA_RELACION_VOLUMEN_CAPACIDAD; no bloquean model-ready.
- FLORIDA II se registra como ENTIDAD_CATALOGO_SIN_REPORTE_METRICA.
- Los JSON fuente no se modifican.
"""


def dry_run(args: argparse.Namespace) -> int:
    output_dir = versioned_dataset_path(args.output_base)
    run_dir = versioned_run_path(args.run_base)
    print("Consolidacion hidrologia por embalse dry-run")
    print(f"Periodo: {args.start_date} a {args.end_date}")
    print(f"Dataset propuesto: {output_dir.relative_to(ROOT)}")
    print(f"Run propuesto: {run_dir.relative_to(ROOT)}")
    for label, spec in TARGETS.items():
        print(
            f"{label}: target={spec['target']} "
            f"ruta={raw_dir_for(spec).relative_to(ROOT)} "
            f"json_canonicos={len(list_raw_files(spec))}"
        )
    print("No se escribieron datasets ni reportes.")
    return 0


def consolidate(
    args: argparse.Namespace,
    command: str,
) -> dict[str, Any]:
    output_dir = versioned_dataset_path(args.output_base)
    run_dir = versioned_run_path(args.run_base)
    if output_dir.exists() or run_dir.exists():
        raise FileExistsError(
            "La version calculada ya existe; reintente para recalcular version libre."
        )
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

    daily, duplicates = build_daily_dataset(
        target_frames,
        args.start_date,
        args.end_date,
    )
    ready = daily.loc[daily["model_ready"]].copy()
    excluded = daily.loc[~daily["model_ready"]].copy()
    source_coverage = source_coverage_rows(
        sources,
        target_frames,
        args,
    )
    reservoir_cov = reservoir_coverage(daily)
    validations = build_validation_rows(
        daily,
        duplicates,
        source_coverage,
        reservoir_cov,
        args,
    )
    quality = build_quality_summary(
        daily,
        validations,
        duplicates,
        reservoir_cov,
    )

    validation_errors = [
        row
        for group in validations.values()
        for row in group
        if row.get("status") == "ERROR"
    ]
    warning_summary = [
        {"issue": issue, "rows": count}
        for issue, count in issue_counts(daily).items()
        if issue in {
            "INCONSISTENCIA_RELACION_VOLUMEN_CAPACIDAD",
            "DIFERENCIA_PORCENTAJE_OFICIAL_CALCULADO",
        }
    ]

    safe_write_csv(
        output_dir / "hydro_reservoir_daily_all.csv",
        daily,
        DAILY_COLUMNS,
    )
    safe_write_csv(
        output_dir / "hydro_reservoir_daily_model_ready.csv",
        ready,
        DAILY_COLUMNS,
    )
    safe_write_csv(
        output_dir / "hydro_reservoir_daily_excluded.csv",
        excluded,
        DAILY_COLUMNS,
    )
    safe_write_parquet(
        output_dir / "hydro_reservoir_daily_all.parquet",
        daily[DAILY_COLUMNS],
    )
    safe_write_parquet(
        output_dir / "hydro_reservoir_daily_model_ready.parquet",
        ready[DAILY_COLUMNS],
    )
    safe_write_parquet(
        output_dir / "hydro_reservoir_daily_excluded.parquet",
        excluded[DAILY_COLUMNS],
    )
    safe_write_csv(output_dir / "source_manifest.csv", sources)
    safe_write_csv(
        output_dir / "data_dictionary.csv",
        data_dictionary_rows(),
    )
    safe_write_csv(
        output_dir / "reservoir_coverage.csv",
        reservoir_cov,
    )
    safe_write_csv(
        output_dir / "catalog_entities_without_data.csv",
        reservoir_cov.loc[~reservoir_cov["observed"]].copy(),
    )
    safe_write_csv(
        output_dir / "missing_metric_pairs.csv",
        missing_metric_pairs(daily),
    )
    safe_write_csv(
        output_dir / "percentage_inconsistencies.csv",
        percentage_inconsistencies(daily),
    )
    safe_write_json(output_dir / "quality_summary.json", quality)

    cap_changes = capacity_changes(daily)
    volume_decreases = volume_events(daily, ascending=True)
    volume_increases = volume_events(daily, ascending=False)
    safe_write_csv(output_dir / "capacity_changes.csv", cap_changes)
    safe_write_csv(
        output_dir / "largest_volume_increases.csv",
        volume_increases,
    )
    safe_write_csv(
        output_dir / "largest_volume_decreases.csv",
        volume_decreases,
    )

    output_files = sorted(
        path for path in output_dir.glob("**/*") if path.is_file()
    )
    output_hashes = [output_manifest_row(path) for path in output_files]
    manifest = {
        "dataset_version": output_dir.name,
        "run_version": run_dir.name,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "command": command,
        "git_branch": git_value(["branch", "--show-current"]),
        "git_head": git_value(["rev-parse", "HEAD"]),
        "requested_period": [args.start_date, args.end_date],
        "effective_period": [
            str(daily["date"].min()),
            str(daily["date"].max()),
        ],
        "targets": [spec["target"] for spec in TARGETS.values()],
        "canonical_json_source_files": len(sources),
        "source_sha256": sources,
        "output_sha256": output_hashes,
        "dataset_digest_sha256": dataframe_digest(
            daily[DAILY_COLUMNS]
        ),
        "rows_by_output": {
            "hydro_reservoir_daily_all": int(len(daily)),
            "hydro_reservoir_daily_model_ready": int(len(ready)),
            "hydro_reservoir_daily_excluded": int(len(excluded)),
        },
        "quality_summary": quality,
    }
    safe_write_json(output_dir / "dataset_manifest.json", manifest)
    safe_write_text(
        output_dir / "README.md",
        build_readme(output_dir.name, args, quality),
    )

    output_files = sorted(
        path for path in output_dir.glob("**/*") if path.is_file()
    )
    output_hashes = [output_manifest_row(path) for path in output_files]

    source_hashes_after: list[dict[str, Any]] = []
    for row in source_hashes_before:
        path = ROOT / row["source_file"]
        source_hashes_after.append(
            {**row, "sha256": file_sha256(path)}
        )
    hashes_unchanged = (
        len(source_hashes_before) == len(source_hashes_after)
        and all(
            before["sha256"] == after["sha256"]
            for before, after in zip(
                source_hashes_before,
                source_hashes_after,
            )
        )
    )

    summary = {
        "status": quality["status"],
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "dataset_version": output_dir.name,
        "run_version": run_dir.name,
        "processed_dir": str(output_dir.relative_to(ROOT)),
        "run_dir": str(run_dir.relative_to(ROOT)),
        "rows_by_output": manifest["rows_by_output"],
        "period": manifest["effective_period"],
        "canonical_json_source_files": len(sources),
        "hashes_source_unchanged": hashes_unchanged,
        "validation_errors": len(validation_errors),
        "warnings": len(warning_summary),
        "quality_summary": quality,
    }
    safe_write_json(
        run_dir / "resumen_consolidacion_hidrologia_embalse.json",
        summary,
    )
    safe_write_csv(
        run_dir / "validacion_cobertura_fuentes.csv",
        validations["coverage_sources"],
    )
    safe_write_csv(
        run_dir / "validacion_claves.csv",
        validations["keys"],
    )
    safe_write_csv(
        run_dir / "validacion_controles.csv",
        validations["checks"],
    )
    safe_write_csv(
        run_dir / "validacion_cobertura_embalses.csv",
        reservoir_cov,
    )
    safe_write_csv(run_dir / "archivos_salida.csv", output_hashes)
    safe_write_csv(run_dir / "errores.csv", validation_errors)
    safe_write_csv(run_dir / "advertencias.csv", warning_summary)
    safe_write_csv(
        run_dir / "eventos_cambio_capacidad.csv",
        cap_changes,
    )
    safe_write_csv(
        run_dir / "eventos_cambio_volumen.csv",
        volume_events(daily, ascending=False),
    )
    safe_write_csv(
        run_dir / "hashes_fuentes_antes.csv",
        source_hashes_before,
    )
    safe_write_csv(
        run_dir / "hashes_fuentes_despues.csv",
        source_hashes_after,
    )
    safe_write_text(
        run_dir / "comando_ejecutado.txt",
        command + "\n",
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.dry_run:
        return dry_run(args)
    if not args.execute:
        print(
            "ERROR: use --execute para escribir el dataset consolidado; "
            "sin --execute no se escribe.",
            file=sys.stderr,
        )
        return 2
    summary = consolidate(args, exact_command(argv))
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary["status"] == "OK" else 3


if __name__ == "__main__":
    raise SystemExit(main())
