"""Normalizacion y diagnostico de respuestas reales XM del piloto."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

import pandas as pd


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


def derive_units(frame: pd.DataFrame, unit: str) -> pd.DataFrame:
    result = frame.copy()
    if "Value" not in result.columns:
        return result
    if unit == "kWh":
        result["Value_GWh"] = result["Value"] / 1_000_000.0
    elif unit == "kW":
        result["Value_MW"] = result["Value"] / 1000.0
    return result


def schema_summary(frame: pd.DataFrame, metric_id: str, target: str, unit: str, entity: str) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "target": target,
        "metric_id": metric_id,
        "entity": entity,
        "unit_catalog": unit,
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

