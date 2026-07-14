"""Utilidades de CVaR; no implican optimizacion conjunta por si solas."""

from __future__ import annotations

import numpy as np


def empirical_cvar(costs: list[float] | np.ndarray, alpha: float) -> float:
    values = np.asarray(costs, dtype=float)
    if values.size == 0:
        raise ValueError("costs no puede estar vacio")
    if not 0 < alpha < 1:
        raise ValueError("alpha debe estar entre 0 y 1")
    var = np.quantile(values, alpha, method="higher")
    tail = values[values >= var]
    return float(tail.mean())


def expected_plus_lambda_cvar(costs: list[float] | np.ndarray, alpha: float, lambda_: float) -> float:
    if lambda_ < 0:
        raise ValueError("lambda debe ser no negativo")
    values = np.asarray(costs, dtype=float)
    return float(values.mean() + lambda_ * empirical_cvar(values, alpha))

