"""Validaciones simples compartidas por scripts y pruebas."""

from __future__ import annotations

import pandas as pd


def duplicate_count(df: pd.DataFrame, keys: list[str]) -> int:
    missing = [col for col in keys if col not in df.columns]
    if missing:
        raise KeyError(f"Columnas ausentes para duplicados: {missing}")
    return int(df.duplicated(keys).sum())


def date_range(df: pd.DataFrame, column: str) -> tuple[str | None, str | None, int]:
    if column not in df.columns:
        raise KeyError(f"Columna de fecha ausente: {column}")
    values = pd.to_datetime(df[column], errors="coerce")
    if values.notna().sum() == 0:
        return None, None, int(values.isna().sum())
    return values.min().date().isoformat(), values.max().date().isoformat(), int(values.isna().sum())


def probabilities_sum_to_one(df: pd.DataFrame, group_cols: list[str], prob_col: str, tol: float = 1e-6) -> pd.DataFrame:
    missing = [col for col in [*group_cols, prob_col] if col not in df.columns]
    if missing:
        raise KeyError(f"Columnas ausentes para probabilidades: {missing}")
    grouped = df.groupby(group_cols, dropna=False)[prob_col].sum().reset_index(name="probability_sum")
    grouped["valid"] = (grouped["probability_sum"] - 1.0).abs() <= tol
    return grouped

