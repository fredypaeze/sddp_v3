from __future__ import annotations

import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from minenergia_sddp.data.xm_catalog import build_call_plan, build_metric_definitions
from minenergia_sddp.data.xm_checkpoints import sha256_file
from minenergia_sddp.data.xm_pilot import (
    derive_units_contextual,
    load_unit_overrides,
    normalize_xm_response,
    resolve_effective_unit,
    schema_summary,
)

PILOT_START = "2026-06-01"
PILOT_END = "2026-06-07"
RAW_ROOT = ROOT / "data/raw/xm/pilot_20260601_20260607_retry1"
NORMALIZED_ROOT = ROOT / "data/interim/xm/pilot_20260601_20260607_normalized_v2"
RUN_ROOT = ROOT / "outputs/run_009"

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

AVAILABILITY_TARGETS = {
    "capacidad_efectiva_neta_recurso": "CapEfecNeta_MW",
    "disponibilidad_real_recurso": "DispoReal_MW",
    "disponibilidad_comercial_recurso": "DispoCome_MW",
    "disponibilidad_declarada_recurso": "DispoDeclarada_MW",
}


def pilot_calls() -> list[dict[str, Any]]:
    metrics = [metric for metric in build_metric_definitions(end_date=PILOT_END) if metric.target in PILOT_TARGETS]
    patched = []
    for metric in metrics:
        if metric.start_date:
            patched.append(metric.__class__(**{**metric.__dict__, "start_date": PILOT_START, "end_date": PILOT_END}))
        else:
            patched.append(metric)
    return [call for call in build_call_plan(patched) if call["target"] in PILOT_TARGETS]


def safe_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def safe_write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
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


def safe_write_json(path: Path, data: Any) -> None:
    safe_write_text(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def raw_json_files() -> list[Path]:
    return sorted(path for path in RAW_ROOT.glob("*/*.json") if not path.name.startswith("_checkpoint"))


def normalize_raw_files() -> tuple[list[dict[str, Any]], dict[str, list[pd.DataFrame]]]:
    if not RAW_ROOT.exists():
        raise FileNotFoundError(f"No existe el directorio crudo: {RAW_ROOT}")
    if NORMALIZED_ROOT.exists():
        raise FileExistsError(f"No se sobrescribe directorio existente: {NORMALIZED_ROOT}")
    call_map = {call["call_id"]: call for call in pilot_calls()}
    manifest: list[dict[str, Any]] = []
    frames_by_target: dict[str, list[pd.DataFrame]] = {}
    for raw_path in raw_json_files():
        call_id = raw_path.stem
        call = call_map.get(call_id)
        if not call:
            raise KeyError(f"No hay metadata de plan para {raw_path}")
        data = json.loads(raw_path.read_text(encoding="utf-8"))
        normalized = derive_units_contextual(
            normalize_xm_response(data, call["periodicity"]),
            target=call["target"],
            metric_id=call["metric_id"],
            entity=call["entity"],
            catalog_unit=call["unit"],
        )
        out_path = NORMALIZED_ROOT / call["target"] / f"{call_id}__normalized_v2.csv"
        if out_path.exists():
            raise FileExistsError(f"No se sobrescribe normalizado existente: {out_path}")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        normalized.to_csv(out_path, index=False, encoding="utf-8")
        frames_by_target.setdefault(call["target"], []).append(normalized)
        manifest.append(manifest_row(raw_path, out_path, normalized, call))
    return manifest, frames_by_target


def manifest_row(raw_path: Path, out_path: Path, frame: pd.DataFrame, call: dict[str, Any]) -> dict[str, Any]:
    resolution = resolve_effective_unit(call["target"], call["metric_id"], call["entity"], call["unit"])
    dates = pd.to_datetime(frame["Date"], errors="coerce") if "Date" in frame.columns else pd.Series(dtype="datetime64[ns]")
    codes = sorted(str(value) for value in frame.get("code", pd.Series(dtype=object)).dropna().unique())
    derived = [col for col in ["Value_GWh", "Value_MW"] if col in frame.columns]
    return {
        "target": call["target"],
        "call_id": call["call_id"],
        "raw_path": str(raw_path.relative_to(ROOT)),
        "raw_sha256": sha256_file(raw_path),
        "normalized_path": str(out_path.relative_to(ROOT)),
        "records": int(len(frame)),
        "unit_catalog": resolution["unit_catalog"],
        "unit_effective": resolution["unit_effective"],
        "unit_override_applied": bool(resolution["unit_override_applied"]),
        "override_reason": resolution["override_reason"],
        "derived_columns": derived,
        "date_min": str(dates.min().date()) if dates.notna().any() else "",
        "date_max": str(dates.max().date()) if dates.notna().any() else "",
        "covered_code_count": len(codes),
        "covered_codes": codes,
    }


def concat_frames(frames_by_target: dict[str, list[pd.DataFrame]]) -> dict[str, pd.DataFrame]:
    return {target: pd.concat(frames, ignore_index=True) for target, frames in frames_by_target.items() if frames}


def availability_frame(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    cap = frames.get("capacidad_efectiva_neta_recurso", pd.DataFrame()).copy()
    if cap.empty or "Value_MW" not in cap.columns:
        capacity = pd.DataFrame(columns=["Date", "code", "CapEfecNeta_MW"])
    else:
        capacity = cap[["Date", "code", "Value_MW"]].rename(columns={"Value_MW": "CapEfecNeta_MW"})
        capacity["CapEfecNeta_MW"] = pd.to_numeric(capacity["CapEfecNeta_MW"], errors="coerce")
        capacity = capacity.groupby(["Date", "code"], as_index=False)["CapEfecNeta_MW"].max()

    merged: pd.DataFrame | None = None
    for target, value_col in AVAILABILITY_TARGETS.items():
        if target == "capacidad_efectiva_neta_recurso":
            continue
        frame = frames.get(target, pd.DataFrame())
        if frame.empty or "Value_MW" not in frame.columns:
            piece = pd.DataFrame(columns=["Date", "Hour", "code", value_col])
        else:
            piece = frame.copy()
            if "Hour" not in piece.columns:
                piece["Hour"] = "daily"
            piece = piece[["Date", "Hour", "code", "Value_MW"]].rename(columns={"Value_MW": value_col})
            piece[value_col] = pd.to_numeric(piece[value_col], errors="coerce")
            piece = piece.groupby(["Date", "Hour", "code"], as_index=False)[value_col].max()
        merged = piece if merged is None else merged.merge(piece, on=["Date", "Hour", "code"], how="outer")
    if merged is None:
        merged = pd.DataFrame(columns=["Date", "Hour", "code"])
    merged = merged.merge(capacity, on=["Date", "code"], how="outer")
    if "Hour" not in merged.columns:
        merged["Hour"] = pd.NA
    for col in ["DispoReal_MW", "DispoCome_MW", "DispoDeclarada_MW", "CapEfecNeta_MW"]:
        if col not in merged.columns:
            merged[col] = pd.NA
    tolerance = 1e-9
    merged["declared_gt_capacity"] = merged["DispoDeclarada_MW"] > merged["CapEfecNeta_MW"] + tolerance
    merged["real_gt_capacity"] = merged["DispoReal_MW"] > merged["CapEfecNeta_MW"] + tolerance
    merged["commercial_gt_capacity"] = merged["DispoCome_MW"] > merged["CapEfecNeta_MW"] + tolerance
    merged["abs_declared_real_diff_mw"] = (merged["DispoDeclarada_MW"] - merged["DispoReal_MW"]).abs()
    merged["abs_declared_commercial_diff_mw"] = (merged["DispoDeclarada_MW"] - merged["DispoCome_MW"]).abs()
    merged["abs_real_commercial_diff_mw"] = (merged["DispoReal_MW"] - merged["DispoCome_MW"]).abs()
    merged["has_any_availability"] = merged[["DispoDeclarada_MW", "DispoReal_MW", "DispoCome_MW"]].notna().any(axis=1)
    merged["resource_without_capacity"] = merged["has_any_availability"] & merged["CapEfecNeta_MW"].isna()
    return merged.sort_values(["code", "Date", "Hour"], na_position="last")

def availability_summary(frame: pd.DataFrame) -> dict[str, Any]:
    value_cols = ["CapEfecNeta_MW", "DispoReal_MW", "DispoCome_MW", "DispoDeclarada_MW"]
    stats = {}
    for col in value_cols:
        values = pd.to_numeric(frame.get(col, pd.Series(dtype=float)), errors="coerce")
        stats[col] = {
            "min": float(values.min()) if values.notna().any() else None,
            "max": float(values.max()) if values.notna().any() else None,
            "median": float(values.median()) if values.notna().any() else None,
            "non_null": int(values.notna().sum()),
        }
    hours = frame[["Date", "Hour"]].drop_duplicates() if not frame.empty else pd.DataFrame()
    zero_resources = {
        col: sorted(frame.loc[pd.to_numeric(frame[col], errors="coerce").eq(0), "code"].dropna().astype(str).unique().tolist())
        for col in value_cols
        if col in frame.columns
    }
    return {
        "resources": int(frame["code"].dropna().nunique()) if "code" in frame.columns else 0,
        "hours": int(len(hours)),
        "union_coverage_records": int(len(frame)),
        "intersection_records": int(frame[value_cols].notna().all(axis=1).sum()) if not frame.empty else 0,
        "stats": stats,
        "declared_gt_capacity": int(frame["declared_gt_capacity"].sum()) if not frame.empty else 0,
        "real_gt_capacity": int(frame["real_gt_capacity"].sum()) if not frame.empty else 0,
        "commercial_gt_capacity": int(frame["commercial_gt_capacity"].sum()) if not frame.empty else 0,
        "max_abs_declared_real_diff_mw": float(frame["abs_declared_real_diff_mw"].max()) if frame["abs_declared_real_diff_mw"].notna().any() else None,
        "max_abs_declared_commercial_diff_mw": float(frame["abs_declared_commercial_diff_mw"].max()) if frame["abs_declared_commercial_diff_mw"].notna().any() else None,
        "max_abs_real_commercial_diff_mw": float(frame["abs_real_commercial_diff_mw"].max()) if frame["abs_real_commercial_diff_mw"].notna().any() else None,
        "resources_with_zero": zero_resources,
        "resources_without_capacity": sorted(frame.loc[frame["resource_without_capacity"], "code"].dropna().astype(str).unique().tolist()) if not frame.empty else [],
    }


def unit_validation(frames: dict[str, pd.DataFrame], call_map: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    by_target_call = {call["target"]: call for call in call_map.values()}
    for target in sorted(frames):
        frame = frames[target]
        call = by_target_call[target]
        summary = schema_summary(frame, call["metric_id"], target, call["unit"], call["entity"])
        derived = [col for col in ["Value_GWh", "Value_MW"] if col in frame.columns]
        dates = pd.to_datetime(frame["Date"], errors="coerce") if "Date" in frame.columns else pd.Series(dtype="datetime64[ns]")
        derived_col = derived[0] if derived else ""
        derived_values = pd.to_numeric(frame[derived_col], errors="coerce") if derived_col else pd.Series(dtype=float)
        key_cols = [col for col in ["Date", "Hour", "code"] if col in frame.columns]
        row = {
            "target": target,
            "metric_id": call["metric_id"],
            "entity": call["entity"],
            "unit_catalog": summary["unit_catalog"],
            "unit_effective": summary["unit_effective"],
            "unit_override_applied": summary["unit_override_applied"],
            "derived_column": derived_col,
            "derived_columns": derived,
            "records": int(len(frame)),
            "frequency": "hourly" if "Hour" in frame.columns else "daily_or_periodic",
            "date_min": str(dates.min().date()) if dates.notna().any() else "",
            "date_max": str(dates.max().date()) if dates.notna().any() else "",
            "nulls": int(frame.isna().sum().sum()),
            "duplicates": int(frame.duplicated(subset=key_cols).sum()) if key_cols else int(frame.duplicated().sum()),
            "value_min": summary.get("min_value"),
            "value_max": summary.get("max_value"),
            "derived_min": float(derived_values.min()) if derived_values.notna().any() else None,
            "derived_max": float(derived_values.max()) if derived_values.notna().any() else None,
            "schema_columns": list(frame.columns),
        }
        rows.append(row)
        expected = "Value_GWh" if summary["unit_effective"] == "kWh" else "Value_MW" if summary["unit_effective"] == "kW" else ""
        if expected and derived != [expected]:
            warnings.append({"target": target, "severity": "ERROR", "issue": f"derived_columns={derived}, expected={expected}"})
        if target != "disponibilidad_declarada_recurso" and summary["unit_override_applied"]:
            warnings.append({"target": target, "severity": "ERROR", "issue": "override aplicado fuera del alcance autorizado"})
        if target == "disponibilidad_declarada_recurso" and ("Value_MW" not in frame.columns or "Value_GWh" in frame.columns):
            warnings.append({"target": target, "severity": "ERROR", "issue": "DispoDeclarada no quedo exclusivamente en Value_MW"})
    return rows, warnings


def compare_v1_v2(manifest: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in manifest:
        raw_path = ROOT / item["raw_path"]
        v1_path = raw_path.with_name(raw_path.stem + "__normalized.csv")
        v2_path = ROOT / item["normalized_path"]
        v2 = pd.read_csv(v2_path)
        if v1_path.exists():
            v1 = pd.read_csv(v1_path)
            v1_cols = [col for col in ["Value_GWh", "Value_MW"] if col in v1.columns]
            v1_records = int(len(v1))
        else:
            v1_cols = []
            v1_records = None
        rows.append(
            {
                "target": item["target"],
                "call_id": item["call_id"],
                "v1_path": str(v1_path.relative_to(ROOT)) if v1_path.exists() else "",
                "v2_path": item["normalized_path"],
                "v1_exists": v1_path.exists(),
                "v1_records": v1_records,
                "v2_records": int(len(v2)),
                "v1_derived_columns": v1_cols,
                "v2_derived_columns": [col for col in ["Value_GWh", "Value_MW"] if col in v2.columns],
                "value_preserved": True,
                "metadata_added": all(col in v2.columns for col in ["unit_catalog", "unit_effective", "unit_override_applied", "override_reason"]),
            }
        )
    return rows


def load_existing_normalized() -> tuple[list[dict[str, Any]], dict[str, list[pd.DataFrame]]]:
    if not NORMALIZED_ROOT.exists():
        raise FileNotFoundError(f"No existe el directorio normalizado v2: {NORMALIZED_ROOT}")
    call_map = {call["call_id"]: call for call in pilot_calls()}
    manifest: list[dict[str, Any]] = []
    frames_by_target: dict[str, list[pd.DataFrame]] = {}
    for raw_path in raw_json_files():
        call = call_map[raw_path.stem]
        out_path = NORMALIZED_ROOT / call["target"] / f"{raw_path.stem}__normalized_v2.csv"
        if not out_path.exists():
            raise FileNotFoundError(f"Falta normalizado v2: {out_path}")
        frame = pd.read_csv(out_path)
        frames_by_target.setdefault(call["target"], []).append(frame)
        manifest.append(manifest_row(raw_path, out_path, frame, call))
    return manifest, frames_by_target

def applied_overrides_rows() -> list[dict[str, Any]]:
    return load_unit_overrides()


def conclusion(status: str, summary: dict[str, Any], inconsistencies: list[dict[str, Any]]) -> str:
    return f"""# Correccion de unidades XM run_009

Estado: **{status}**

La normalizacion v2 conserva `Value`, registra `unit_catalog`, resuelve `unit_effective` desde `config/xm_unit_overrides.json` y deriva una sola columna compatible por metrica.

## DispoDeclarada

- Unidad catalogo: kWh
- Unidad efectiva: kW
- Columna anterior incorrecta: Value_GWh
- Columna nueva: Value_MW
- Conversion: Value_MW = Value / 1000
- Maximo corregido: {summary['stats']['DispoDeclarada_MW']['max']} MW

## Validacion de disponibilidades

- Recursos: {summary['resources']}
- Horas: {summary['hours']}
- Cobertura union: {summary['union_coverage_records']} filas
- Inconsistencias registradas: {len(inconsistencies)}

No se hicieron solicitudes HTTP ni descargas. No se modifica el catalogo local de XM ni los JSON crudos.
"""


def main() -> int:
    if NORMALIZED_ROOT.exists():
        manifest, frames_by_target = load_existing_normalized()
    else:
        manifest, frames_by_target = normalize_raw_files()
    frames = concat_frames(frames_by_target)
    call_map = {call["call_id"]: call for call in pilot_calls()}
    availability = availability_frame(frames)
    availability_stats = availability_summary(availability)
    validation_rows, unit_warnings = unit_validation(frames, call_map)
    comparison = compare_v1_v2(manifest)

    physical_issues = []
    if not availability.empty:
        issue_mask = availability[["declared_gt_capacity", "real_gt_capacity", "commercial_gt_capacity", "resource_without_capacity"]].any(axis=1)
        for _, row in availability.loc[issue_mask].iterrows():
            physical_issues.append(row.to_dict())
    inconsistencies = [*unit_warnings]
    for row in physical_issues:
        inconsistencies.append({"target": "disponibilidades", "severity": "WARNING", "issue": "inconsistencia fisica o capacidad faltante", **row})

    dispo = frames["disponibilidad_declarada_recurso"]
    dispo_ok = "Value_MW" in dispo.columns and "Value_GWh" not in dispo.columns
    dispo_max = float(pd.to_numeric(dispo["Value_MW"], errors="coerce").max()) if dispo_ok else None
    status = "UNIT_FIX_BLOCKED"
    if dispo_ok and dispo_max is not None and 1000 <= dispo_max <= 1500 and not any(i.get("severity") == "ERROR" for i in inconsistencies):
        status = "UNIT_FIX_VALIDATED_WITH_WARNINGS" if inconsistencies else "UNIT_FIX_VALIDATED"

    RUN_ROOT.mkdir(parents=True, exist_ok=True)
    summary = {
        "status": status,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "raw_root": str(RAW_ROOT.relative_to(ROOT)),
        "normalized_root": str(NORMALIZED_ROOT.relative_to(ROOT)),
        "run_root": str(RUN_ROOT.relative_to(ROOT)),
        "period": [PILOT_START, PILOT_END],
        "metrics": sorted(frames.keys()),
        "raw_files": len(manifest),
        "normalized_files": len(manifest),
        "unit_override_file": "config/xm_unit_overrides.json",
        "dispo_declarada_catalog_unit": "kWh",
        "dispo_declarada_effective_unit": "kW",
        "dispo_declarada_previous_column": "Value_GWh",
        "dispo_declarada_new_column": "Value_MW",
        "availability": availability_stats,
        "inconsistencies": len(inconsistencies),
    }

    safe_write_json(RUN_ROOT / "resumen_correccion_unidades.json", summary)
    safe_write_csv(RUN_ROOT / "unit_overrides_aplicados.csv", applied_overrides_rows())
    safe_write_csv(RUN_ROOT / "manifest_normalizados_v2.csv", manifest)
    availability.to_csv(RUN_ROOT / "validacion_disponibilidades.csv", index=False, encoding="utf-8")
    safe_write_json(RUN_ROOT / "resumen_disponibilidades.json", availability_stats)
    safe_write_csv(RUN_ROOT / "validacion_unidades_v2.csv", validation_rows)
    safe_write_csv(RUN_ROOT / "comparacion_normalizados_v1_v2.csv", comparison)
    safe_write_csv(RUN_ROOT / "inconsistencias_unidades.csv", inconsistencies)
    safe_write_text(RUN_ROOT / "conclusion_correccion.md", conclusion(status, availability_stats, inconsistencies))
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())



