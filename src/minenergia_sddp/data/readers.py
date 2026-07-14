"""Lectores acotados para auditoria de fuentes locales."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pandas as pd


def read_table_sample(path: Path, rows: int = 5) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path, nrows=rows)
    if suffix == ".parquet":
        return pd.read_parquet(path).head(rows)
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path, nrows=rows)
    raise ValueError(f"Formato no soportado para muestra tabular: {path}")


def flatten_xm_list_entities(path: Path) -> pd.DataFrame:
    """Convierte catálogos XM con columna ListEntities a tabla plana."""
    raw = pd.read_excel(path)
    records: list[dict[str, Any]] = []
    for _, row in raw.iterrows():
        entities = ast.literal_eval(str(row["ListEntities"]))
        for entity in entities:
            item = {"Date": row.get("Date"), "Id": entity.get("Id")}
            values = entity.get("Values") or {}
            item.update(values)
            records.append(item)
    return pd.DataFrame(records)

