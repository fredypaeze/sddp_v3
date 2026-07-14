"""Validacion de respuestas y unidades XM."""

from __future__ import annotations

from typing import Any


def response_is_empty(data: Any) -> bool:
    if data is None:
        return True
    if isinstance(data, (list, tuple, dict, str)) and len(data) == 0:
        return True
    return False


def validate_non_empty_response(data: Any) -> None:
    if response_is_empty(data):
        raise ValueError("Respuesta XM vacia; el lote no puede marcarse como completado")


def kwh_to_gwh(value: float) -> float:
    return float(value) / 1_000_000.0


def kw_to_mw(value: float) -> float:
    return float(value) / 1000.0


def preserve_price_unit(unit: str) -> str:
    normalized = unit.strip().upper().replace(" ", "")
    if normalized in {"COP/KWH", "$/KWH"}:
        return "COP/kWh"
    if "MWH" in normalized:
        raise ValueError("No se permiten precios electricos en COP/MWh")
    return unit


def validate_expected_unit(metric_id: str, unit: str) -> None:
    if "Prec" in metric_id or metric_id.startswith("P"):
        preserve_price_unit(unit)
    if metric_id in {"Gene", "DemaSIN", "DemaReal", "AporEner", "VoluUtilDiarEner", "CapaUtilDiarEner"} and unit != "kWh":
        raise ValueError(f"Unidad inesperada para {metric_id}: {unit}")
    if metric_id in {"DispoReal", "DispoCome", "CapEfecNeta"} and unit != "kW":
        raise ValueError(f"Unidad inesperada para {metric_id}: {unit}")


def required_payload_fields(call: dict[str, Any]) -> list[str]:
    if call.get("periodicity") == "ListsEntities":
        return ["MetricId"]
    fields = ["MetricId", "StartDate", "EndDate", "Entity"]
    if call.get("filter_count", 0):
        fields.append("Filter")
    return fields


def validate_payload_schema(payload: dict[str, Any], call: dict[str, Any]) -> None:
    missing = [field for field in required_payload_fields(call) if field not in payload]
    if missing:
        raise ValueError(f"Payload incompleto para {call.get('call_id')}: {missing}")
    if "http://" in str(call.get("url", "")).lower():
        raise ValueError("Solo se permite HTTPS")

