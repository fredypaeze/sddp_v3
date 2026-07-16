"""Normalizacion y diagnostico de respuestas reales XM del piloto."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
UNIT_OVERRIDE_PATH = ROOT / "config/xm_unit_overrides.json"
DERIVED_COLUMNS = {"kWh": "Value_GWh", "kW": "Value_MW"}
CONVERSION_FACTORS = {"kWh": 1 / 1_000_000.0, "kW": 1 / 1_000.0}


def normalize_xm_response(data: Any, periodicity: str) -> pd.DataFrame:
    if data in (None, [], {}):
        return pd.DataFrame()
    frame = _top_frame(data)
    if frame.empty:
        return frame
    entity_col = _entity_column(periodicity)
    if entity_col not in frame.columns:
        return frame
    records: list[dict[str, Any]] = []
    for _, row in frame.iterrows():
        date_value = row.get("Date")
        entities = _parse_entities(row.get(entity_col))
        for entity in entities:
            values = entity.get("Values", entity) if isinstance(entity, dict) else {}
            if not isinstance(values, dict):
                continue
            base = {
                "Date": date_value,
                "Id": entity.get("Id") if isinstance(entity, dict) else None,
                "code": values.get("code") or values.get("Code") or values.get("Name"),
                "name": values.get("Name") or values.get("name"),
            }
            hour_values = {key: value for key, value in values.items() if str(key).lower().startswith("hour")}
            if hour_values:
                for hour_key, value in hour_values.items():
                    item = dict(base)
                    item["Hour"] = hour_key
                    item["Value"] = _to_number(value)
                    records.append(item)
            else:
                item = dict(base)
                item["Value"] = _to_number(values.get("Value", values.get("value")))
                if item["Value"] is None:
                    numeric = [(key, _to_number(value)) for key, value in values.items()]
                    numeric = [(key, value) for key, value in numeric if value is not None]
                    if len(numeric) == 1:
                        item["Value"] = numeric[0][1]
                        item["value_field"] = numeric[0][0]
                records.append(item)
    return pd.DataFrame(records)


def _top_frame(data: Any) -> pd.DataFrame:
    if isinstance(data, list):
        return pd.DataFrame(data)
    if isinstance(data, dict):
        for key in ["Items", "data", "Data", "results", "value"]:
            if key in data and isinstance(data[key], list):
                return pd.DataFrame(data[key])
        return pd.DataFrame([data])
    return pd.DataFrame()


def _entity_column(periodicity: str) -> str:
    if periodicity == "HourlyEntities":
        return "HourlyEntities"
    if periodicity == "DailyEntities":
        return "DailyEntities"
    if periodicity == "MonthlyEntities":
        return "MonthlyEntities"
    if periodicity == "ListsEntities":
        return "ListEntities"
    return periodicity


def _parse_entities(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = ast.literal_eval(value)
            if isinstance(parsed, list):
                return parsed
        except (SyntaxError, ValueError):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                return []
    if isinstance(value, dict):
        return [value]
    return []


def _to_number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load_unit_overrides(path: Path | None = None) -> list[dict[str, Any]]:
    override_path = path or UNIT_OVERRIDE_PATH
    if not override_path.exists():
        return []
    data = json.loads(override_path.read_text(encoding="utf-8-sig"))
    rules = data.get("overrides") if isinstance(data, dict) else data
    if not isinstance(rules, list):
        raise ValueError("config/xm_unit_overrides.json debe contener una lista 'overrides'")
    seen: set[tuple[str, str, str]] = set()
    for rule in rules:
        validate_unit_override(rule)
        key = (rule["target"], rule["metric_id"], rule["entity"])
        if key in seen:
            raise ValueError(f"Override de unidad duplicado para {key}")
        seen.add(key)
    return rules


def validate_unit_override(rule: Any) -> None:
    required = {
        "target",
        "metric_id",
        "entity",
        "catalog_unit",
        "effective_unit",
        "derived_column",
        "conversion_factor",
        "status",
        "evidence_period",
        "evidence_run",
        "reason",
    }
    if not isinstance(rule, dict):
        raise ValueError("Cada override de unidad debe ser un objeto JSON")
    missing = sorted(required - set(rule))
    if missing:
        raise ValueError(f"Override de unidad incompleto; faltan: {', '.join(missing)}")
    effective = rule["effective_unit"]
    if effective not in DERIVED_COLUMNS:
        raise ValueError(f"Unidad efectiva no soportada en override: {effective}")
    expected_column = DERIVED_COLUMNS[effective]
    if rule["derived_column"] != expected_column:
        raise ValueError(
            f"Override contradictorio para {rule['target']}: "
            f"{effective} debe derivar {expected_column}, no {rule['derived_column']}"
        )
    expected_factor = CONVERSION_FACTORS[effective]
    if abs(float(rule["conversion_factor"]) - expected_factor) > 1e-12:
        raise ValueError(
            f"Override contradictorio para {rule['target']}: factor {rule['conversion_factor']} "
            f"no corresponde a {effective}"
        )
    if rule["catalog_unit"] == rule["effective_unit"]:
        raise ValueError(f"Override redundante para {rule['target']}: catalog_unit y effective_unit son iguales")


def resolve_effective_unit(
    target: str,
    metric_id: str,
    entity: str,
    catalog_unit: str,
    override_path: Path | None = None,
) -> dict[str, Any]:
    matches = [
        rule
        for rule in load_unit_overrides(override_path)
        if rule["target"] == target and rule["metric_id"] == metric_id and rule["entity"] == entity
    ]
    if not matches:
        return {
            "unit_catalog": catalog_unit,
            "unit_effective": catalog_unit,
            "unit_override_applied": False,
            "override_reason": "",
            "derived_column": DERIVED_COLUMNS.get(catalog_unit, ""),
            "conversion_factor": CONVERSION_FACTORS.get(catalog_unit),
        }
    if len(matches) > 1:
        raise ValueError(f"Override de unidad ambiguo para {target}/{metric_id}/{entity}")
    rule = matches[0]
    if rule["catalog_unit"] != catalog_unit:
        raise ValueError(
            f"Override contradictorio para {target}/{metric_id}/{entity}: "
            f"catalogo={catalog_unit}, regla={rule['catalog_unit']}"
        )
    return {
        "unit_catalog": catalog_unit,
        "unit_effective": rule["effective_unit"],
        "unit_override_applied": True,
        "override_reason": rule["reason"],
        "derived_column": rule["derived_column"],
        "conversion_factor": float(rule["conversion_factor"]),
        "override_status": rule["status"],
        "override_evidence_period": rule["evidence_period"],
        "override_evidence_run": rule["evidence_run"],
    }


def derive_units(frame: pd.DataFrame, unit: str) -> pd.DataFrame:
    result = frame.copy()
    if "Value" not in result.columns:
        return result
    result = result.drop(columns=[col for col in ["Value_GWh", "Value_MW"] if col in result.columns])
    if unit == "kWh":
        result["Value_GWh"] = result["Value"] / 1_000_000.0
    elif unit == "kW":
        result["Value_MW"] = result["Value"] / 1000.0
    return result


def derive_units_contextual(
    frame: pd.DataFrame,
    *,
    target: str,
    metric_id: str,
    entity: str,
    catalog_unit: str,
    override_path: Path | None = None,
) -> pd.DataFrame:
    result = frame.copy()
    resolution = resolve_effective_unit(target, metric_id, entity, catalog_unit, override_path)
    result = result.drop(columns=[col for col in ["Value_GWh", "Value_MW"] if col in result.columns])
    result["unit_catalog"] = resolution["unit_catalog"]
    result["unit_effective"] = resolution["unit_effective"]
    result["unit_override_applied"] = bool(resolution["unit_override_applied"])
    result["override_reason"] = resolution["override_reason"]
    if "Value" not in result.columns:
        return result
    derived_column = resolution.get("derived_column", "")
    factor = resolution.get("conversion_factor")
    if derived_column and factor is not None:
        result[derived_column] = result["Value"] * float(factor)
    return result


def schema_summary(frame: pd.DataFrame, metric_id: str, target: str, unit: str, entity: str) -> dict[str, Any]:
    resolution = resolve_effective_unit(target, metric_id, entity, unit)
    summary: dict[str, Any] = {
        "target": target,
        "metric_id": metric_id,
        "entity": entity,
        "unit_catalog": unit,
        "unit_effective": resolution["unit_effective"],
        "unit_override_applied": resolution["unit_override_applied"],
        "override_reason": resolution["override_reason"],
        "columns": list(frame.columns),
        "dtypes": {col: str(dtype) for col, dtype in frame.dtypes.items()},
        "records": int(len(frame)),
        "nulls": frame.isna().sum().astype(int).to_dict() if not frame.empty else {},
        "duplicates": int(frame.duplicated().sum()) if not frame.empty else 0,
    }
    if "Date" in frame.columns:
        dates = pd.to_datetime(frame["Date"], errors="coerce")
        summary["date_min"] = str(dates.min().date()) if dates.notna().any() else None
        summary["date_max"] = str(dates.max().date()) if dates.notna().any() else None
    if "Value" in frame.columns:
        values = pd.to_numeric(frame["Value"], errors="coerce")
        summary["negative_values"] = int((values < 0).sum())
        summary["zero_values"] = int((values == 0).sum())
        summary["min_value"] = float(values.min()) if values.notna().any() else None
        summary["max_value"] = float(values.max()) if values.notna().any() else None
        summary["unit_inferred_by_magnitude"] = infer_unit_by_magnitude(metric_id, unit, values)
    return summary


def infer_unit_by_magnitude(metric_id: str, unit: str, values: pd.Series) -> str:
    clean = values.dropna()
    if clean.empty:
        return "sin valores"
    median = float(clean.abs().median())
    if metric_id.startswith("Dispo") or metric_id == "CapEfecNeta":
        if median > 50_000:
            return "probablemente kW"
        if median > 10:
            return "probablemente MW o kW pequeno; requiere contraste"
    if unit == "kWh":
        if median > 1_000_000:
            return "kWh plausible"
        if median < 10_000:
            return "magnitud baja para energia agregada; revisar entidad"
    return unit


def read_normalized_outputs(root: Path) -> dict[str, pd.DataFrame]:
    frames: dict[str, list[pd.DataFrame]] = {}
    for path in root.glob("**/*_normalized.csv"):
        parts = path.stem.replace("_normalized", "").split("__")
        target = parts[0]
        frames.setdefault(target, []).append(pd.read_csv(path))
    return {target: pd.concat(items, ignore_index=True) for target, items in frames.items() if items}

