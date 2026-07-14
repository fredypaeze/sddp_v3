"""Conversiones de unidades explicitamente auditables."""

from __future__ import annotations


def mw_to_gwh(capacity_mw: float, hours: float) -> float:
    if capacity_mw < 0 or hours < 0:
        raise ValueError("capacity_mw y hours deben ser no negativos")
    return capacity_mw * hours / 1000.0


def gwh_times_cop_kwh_to_billion_cop(energy_gwh: float, price_cop_kwh: float) -> float:
    if energy_gwh < 0 or price_cop_kwh < 0:
        raise ValueError("energia y precio deben ser no negativos")
    return energy_gwh * 1_000_000.0 * price_cop_kwh / 1_000_000_000.0


def assert_cop_kwh_unit(unit: str) -> None:
    normalized = unit.strip().upper().replace(" ", "")
    if normalized != "COP/KWH":
        raise ValueError("Los precios electricos deben expresarse en COP/kWh")

