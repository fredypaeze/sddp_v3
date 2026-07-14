"""Clasificacion de disponibilidad de datos para puertas V1/V2."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AvailabilityCategory(StrEnum):
    FOUND_VALID = "FOUND_VALID"
    FOUND_WITH_LIMITATIONS = "FOUND_WITH_LIMITATIONS"
    DERIVABLE_WITH_VALID_METHOD = "DERIVABLE_WITH_VALID_METHOD"
    FOUND_METADATA_ONLY = "FOUND_METADATA_ONLY"
    MISSING_CRITICAL = "MISSING_CRITICAL"
    NOT_REQUIRED_FOR_AGGREGATE_V1 = "NOT_REQUIRED_FOR_AGGREGATE_V1"
    REQUIRED_ONLY_FOR_RESOURCE_LEVEL_V2 = "REQUIRED_ONLY_FOR_RESOURCE_LEVEL_V2"


class GateStatus(StrEnum):
    GO_AGGREGATE_V1 = "GO_AGGREGATE_V1"
    BLOCKED_AGGREGATE_V1 = "BLOCKED_AGGREGATE_V1"
    GO_RESOURCE_LEVEL_V2 = "GO_RESOURCE_LEVEL_V2"
    BLOCKED_RESOURCE_LEVEL_V2 = "BLOCKED_RESOURCE_LEVEL_V2"


@dataclass(frozen=True)
class DataFinding:
    dato: str
    category: AvailabilityCategory
    evidence_file: str
    unit: str
    coverage: str
    limitation: str


def evaluate_aggregate_v1(findings: dict[str, AvailabilityCategory]) -> GateStatus:
    required = {
        "demanda_oficial_sin",
        "generacion_agregada",
        "almacenamiento_porcentaje",
        "escenarios_probabilidades",
        "limite_termico_agregado",
    }
    valid = {
        AvailabilityCategory.FOUND_VALID,
        AvailabilityCategory.FOUND_WITH_LIMITATIONS,
        AvailabilityCategory.DERIVABLE_WITH_VALID_METHOD,
    }
    if all(findings.get(key) in valid for key in required):
        return GateStatus.GO_AGGREGATE_V1
    return GateStatus.BLOCKED_AGGREGATE_V1


def evaluate_resource_v2(findings: dict[str, AvailabilityCategory]) -> GateStatus:
    required = {
        "capacidad_termica",
        "disponibilidad_termica",
        "precio_por_recurso",
        "generacion_por_recurso",
        "codigo_union",
        "combustible",
    }
    valid = {AvailabilityCategory.FOUND_VALID, AvailabilityCategory.DERIVABLE_WITH_VALID_METHOD}
    if all(findings.get(key) in valid for key in required):
        return GateStatus.GO_RESOURCE_LEVEL_V2
    return GateStatus.BLOCKED_RESOURCE_LEVEL_V2


def is_metadata_only(columns: list[str], metric_id: str | None = None) -> bool:
    lowered = {col.lower() for col in columns}
    if "listentities" in lowered and metric_id:
        return True
    metadata_cols = {"metricid", "metricname", "entity", "maxdays", "type", "url", "filter", "metricunits"}
    return bool(metadata_cols.intersection(lowered)) and not {"date", "fecha", "value", "values_hour01"}.intersection(lowered)


def can_convert_volume_to_gwh(columns: list[str]) -> bool:
    lowered = {col.lower() for col in columns}
    has_volume = any("volumen" in col for col in lowered)
    has_energy = any("gwh" in col or "energia_almacenada" in col for col in lowered)
    has_factor = any("factor" in col or "productividad" in col or "conversion" in col for col in lowered)
    return has_volume and (has_energy or has_factor)

