"""Catalogo local XM y construccion del plan de adquisicion."""

from __future__ import annotations

import ast
import json
import math
from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from minenergia_sddp.config.paths import external_source_path, project_root


DEFAULT_PLAN_END_DATE = "2026-07-13"
RESOURCE_BATCH_SIZE = 10


@dataclass(frozen=True)
class XMetric:
    target: str
    official_name: str
    metric_id: str
    entity: str
    periodicity: str
    url: str
    unit: str
    max_days: int
    filter_name: str
    status: str
    evidence_file: str
    evidence: str
    output_domain: str
    start_date: str | None
    end_date: str | None
    entity_source: str
    notes: str


def load_metric_catalog(path: Path | None = None) -> pd.DataFrame:
    catalog_path = path or external_source_path("xm_validation") / "data/catalogos/maestros/ListadoMetricas.xlsx"
    raw = pd.read_excel(catalog_path)
    records: list[dict[str, Any]] = []
    for _, row in raw.iterrows():
        entities = ast.literal_eval(str(row["ListEntities"]))
        for entity in entities:
            item = {"CatalogDate": row.get("Date"), "Id": entity.get("Id")}
            item.update(entity.get("Values", {}))
            records.append(item)
    return pd.DataFrame(records)


def load_list_entities(name: str) -> pd.DataFrame:
    path = external_source_path("xm_validation") / f"data/catalogos/maestros/{name}.xlsx"
    raw = pd.read_excel(path)
    records: list[dict[str, Any]] = []
    for _, row in raw.iterrows():
        entities = ast.literal_eval(str(row["ListEntities"]))
        for entity in entities:
            item = {"CatalogDate": row.get("Date"), "Id": entity.get("Id")}
            item.update(entity.get("Values", {}))
            records.append(item)
    return pd.DataFrame(records).drop_duplicates()


def exact_metric(catalog: pd.DataFrame, metric_id: str, entity: str) -> dict[str, Any] | None:
    matches = catalog[(catalog["MetricId"].eq(metric_id)) & (catalog["Entity"].eq(entity))]
    if matches.empty:
        return None
    row = matches.iloc[0].to_dict()
    return row


def central_hydrothermal_resources() -> list[str]:
    resources = load_list_entities("ListadoRecursos")
    type_col = resources["Type"].astype(str).str.upper()
    disp_col = resources["Disp"].astype(str).str.upper()
    mask = disp_col.eq("DESPACHADO CENTRALMENTE") & type_col.isin(["HIDRAULICA", "TERMICA"])
    return sorted(resources.loc[mask, "Code"].dropna().astype(str).unique().tolist())


def active_embalse_names() -> list[str]:
    embalses = load_list_entities("ListadoEmbalses")
    status = embalses.get("Status", pd.Series([""] * len(embalses))).astype(str).str.upper()
    mask = status.eq("ACTIVO") if "Status" in embalses.columns else pd.Series([True] * len(embalses))
    return sorted(embalses.loc[mask, "Name"].dropna().astype(str).unique().tolist())


def active_rio_names() -> list[str]:
    rios = load_list_entities("ListadoRios")
    status = rios.get("Status", pd.Series([""] * len(rios))).astype(str).str.upper()
    mask = status.eq("ACTIVO") if "Status" in rios.columns else pd.Series([True] * len(rios))
    return sorted(rios.loc[mask, "Name"].dropna().astype(str).unique().tolist())


def target_specs() -> list[dict[str, str | None]]:
    return [
        {"target": "demanda_sin_diaria", "metric_id": "DemaSIN", "entity": "Sistema", "domain": "demanda", "start": "2023-01-01", "scope": "system"},
        {"target": "demanda_real_sistema_horaria", "metric_id": "DemaReal", "entity": "Sistema", "domain": "demanda", "start": "2023-01-01", "scope": "system"},
        {"target": "generacion_real_por_recurso", "metric_id": "Gene", "entity": "Recurso", "domain": "generacion", "start": "2023-01-01", "scope": "central_hydrothermal_resources"},
        {"target": "generacion_real_total", "metric_id": "Gene", "entity": "Sistema", "domain": "generacion", "start": "2023-01-01", "scope": "system"},
        {"target": "listado_recursos", "metric_id": "ListadoRecursos", "entity": "Sistema", "domain": "recursos", "start": None, "scope": "list"},
        {"target": "capacidad_efectiva_neta_recurso", "metric_id": "CapEfecNeta", "entity": "Recurso", "domain": "recursos", "start": "2023-01-01", "scope": "central_hydrothermal_resources"},
        {"target": "disponibilidad_real_recurso", "metric_id": "DispoReal", "entity": "Recurso", "domain": "disponibilidad", "start": "2023-01-01", "scope": "central_hydrothermal_resources"},
        {"target": "disponibilidad_comercial_recurso", "metric_id": "DispoCome", "entity": "Recurso", "domain": "disponibilidad", "start": "2023-01-01", "scope": "central_hydrothermal_resources"},
        {"target": "disponibilidad_declarada_recurso", "metric_id": "DispoDeclarada", "entity": "Recurso", "domain": "disponibilidad", "start": "2023-01-01", "scope": "central_hydrothermal_resources"},
        {"target": "volumen_util_energia_sin", "metric_id": "VoluUtilDiarEner", "entity": "Sistema", "domain": "embalses", "start": "2010-01-01", "scope": "system"},
        {"target": "volumen_util_energia_embalse", "metric_id": "VoluUtilDiarEner", "entity": "Embalse", "domain": "embalses", "start": "2010-01-01", "scope": "active_embalse_names"},
        {"target": "capacidad_util_energia_sin", "metric_id": "CapaUtilDiarEner", "entity": "Sistema", "domain": "embalses", "start": "2010-01-01", "scope": "system"},
        {"target": "capacidad_util_energia_embalse", "metric_id": "CapaUtilDiarEner", "entity": "Embalse", "domain": "embalses", "start": "2010-01-01", "scope": "active_embalse_names"},
        {"target": "porcentaje_volumen_util_sin", "metric_id": "PorcVoluUtilDiar", "entity": "Sistema", "domain": "embalses", "start": "2010-01-01", "scope": "system"},
        {"target": "porcentaje_volumen_util_embalse", "metric_id": "PorcVoluUtilDiar", "entity": "Embalse", "domain": "embalses", "start": "2010-01-01", "scope": "active_embalse_names"},
        {"target": "aportes_energia_sin", "metric_id": "AporEner", "entity": "Sistema", "domain": "aportes", "start": "2010-01-01", "scope": "system"},
        {"target": "aportes_energia_rio", "metric_id": "AporEner", "entity": "Rio", "domain": "aportes", "start": "2010-01-01", "scope": "active_rio_names"},
        {"target": "importaciones_energia_sistema", "metric_id": "ImpoEner", "entity": "Sistema", "domain": "intercambios", "start": "2023-01-01", "scope": "system"},
        {"target": "exportaciones_energia_sistema", "metric_id": "ExpoEner", "entity": "Sistema", "domain": "intercambios", "start": "2023-01-01", "scope": "system"},
        {"target": "escenario_demanda_upme_alto", "metric_id": "EscDemUPMEAlto", "entity": "Sistema", "domain": "demanda", "start": "2023-01-01", "scope": "system"},
        {"target": "escenario_demanda_upme_medio", "metric_id": "EscDemUPMEMedio", "entity": "Sistema", "domain": "demanda", "start": "2023-01-01", "scope": "system"},
        {"target": "escenario_demanda_upme_bajo", "metric_id": "EscDemUPMEBajo", "entity": "Sistema", "domain": "demanda", "start": "2023-01-01", "scope": "system"},
    ]


def build_metric_definitions(end_date: str = DEFAULT_PLAN_END_DATE) -> list[XMetric]:
    catalog = load_metric_catalog()
    evidence_file = str(external_source_path("xm_validation") / "data/catalogos/maestros/ListadoMetricas.xlsx")
    metrics: list[XMetric] = []
    for spec in target_specs():
        row = exact_metric(catalog, str(spec["metric_id"]), str(spec["entity"]))
        if row is None:
            metrics.append(
                XMetric(
                    target=str(spec["target"]),
                    official_name="",
                    metric_id=str(spec["metric_id"]),
                    entity=str(spec["entity"]),
                    periodicity="",
                    url="",
                    unit="",
                    max_days=0,
                    filter_name="",
                    status="NOT_FOUND",
                    evidence_file=evidence_file,
                    evidence="No se encontro combinacion MetricId/Entity en catalogo local.",
                    output_domain=str(spec["domain"]),
                    start_date=spec["start"],
                    end_date=end_date if spec["start"] else None,
                    entity_source=str(spec["scope"]),
                    notes="",
                )
            )
            continue
        metrics.append(
            XMetric(
                target=str(spec["target"]),
                official_name=str(row.get("MetricName", "")),
                metric_id=str(row.get("MetricId", "")),
                entity=str(row.get("Entity", "")),
                periodicity=str(row.get("Type", "")),
                url=str(row.get("Url", "")),
                unit=str(row.get("MetricUnits", "")),
                max_days=int(row.get("MaxDays", 0) or 0),
                filter_name=str(row.get("Filter", "")),
                status="FOUND_EXACT",
                evidence_file=evidence_file,
                evidence=str(row.get("MetricDescription", "")),
                output_domain=str(spec["domain"]),
                start_date=spec["start"],
                end_date=end_date if spec["start"] else None,
                entity_source=str(spec["scope"]),
                notes=_metric_notes(str(row.get("MetricId", "")), str(row.get("Entity", "")), str(row.get("MetricUnits", ""))),
            )
        )
    return metrics


def _metric_notes(metric_id: str, entity: str, unit: str) -> str:
    if metric_id == "DispoDeclarada" and unit == "kWh":
        return "Catalogo reporta kWh aunque la descripcion habla de potencia neta; validar esquema antes de usar como MW/kW."
    if metric_id == "ListadoRecursos":
        return "El listado trae atributos; la capacidad efectiva neta se obtiene con CapEfecNeta."
    if metric_id == "DemaReal":
        return "Demanda real horaria; DemaSIN diaria se usa como referencia principal de SIN."
    return ""


def metric_to_dict(metric: XMetric) -> dict[str, Any]:
    return asdict(metric)


def date_windows(start: str, end: str, max_days: int = 30) -> list[tuple[str, str]]:
    start_date = datetime.strptime(start, "%Y-%m-%d").date()
    end_date = datetime.strptime(end, "%Y-%m-%d").date()
    if end_date < start_date:
        raise ValueError("end debe ser mayor o igual a start")
    windows: list[tuple[str, str]] = []
    current = start_date
    step = max_days if max_days > 0 else 30
    while current <= end_date:
        close = min(current + timedelta(days=step - 1), end_date)
        windows.append((current.isoformat(), close.isoformat()))
        current = close + timedelta(days=1)
    return windows


def entity_values(scope: str) -> list[str]:
    if scope == "system":
        return []
    if scope == "list":
        return []
    if scope == "central_hydrothermal_resources":
        return central_hydrothermal_resources()
    if scope == "active_embalse_names":
        return active_embalse_names()
    if scope == "active_rio_names":
        return active_rio_names()
    raise ValueError(f"Scope no soportado: {scope}")


def batches(values: list[str], batch_size: int = RESOURCE_BATCH_SIZE) -> list[list[str]]:
    if not values:
        return [[]]
    return [values[i : i + batch_size] for i in range(0, len(values), batch_size)]


def window_size_for(metric: XMetric) -> int:
    if metric.periodicity in {"HourlyEntities", "DailyEntities"}:
        return 30
    if metric.periodicity == "MonthlyEntities":
        return min(metric.max_days or 731, 731)
    return metric.max_days or 731


def output_dir_for(metric: XMetric) -> str:
    return f"data/raw/xm/{metric.output_domain}/{metric.target}"


def build_call_plan(metrics: list[XMetric], max_resources: int | None = None) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for metric in metrics:
        if metric.status != "FOUND_EXACT":
            continue
        if metric.periodicity == "ListsEntities":
            calls.append(
                {
                    "call_id": f"{metric.target}__list",
                    "target": metric.target,
                    "metric_id": metric.metric_id,
                    "entity": metric.entity,
                    "periodicity": metric.periodicity,
                    "url": metric.url,
                    "start_date": "",
                    "end_date": "",
                    "filter_values": [],
                    "filter_count": 0,
                    "output_dir": output_dir_for(metric),
                    "unit": metric.unit,
                    "granularity": "catalogo",
                    "timezone": "America/Bogota; API XM publica fechas locales segun metadata operativa",
                }
            )
            continue
        if not metric.start_date or not metric.end_date:
            continue
        values = entity_values(metric.entity_source)
        if max_resources is not None and values:
            values = values[:max_resources]
        for start, end in date_windows(metric.start_date, metric.end_date, window_size_for(metric)):
            for idx, batch in enumerate(batches(values), start=1):
                calls.append(
                    {
                        "call_id": f"{metric.target}__{start}__{end}__b{idx:03d}",
                        "target": metric.target,
                        "metric_id": metric.metric_id,
                        "entity": metric.entity,
                        "periodicity": metric.periodicity,
                        "url": metric.url,
                        "start_date": start,
                        "end_date": end,
                        "filter_values": batch,
                        "filter_count": len(batch),
                        "output_dir": output_dir_for(metric),
                        "unit": metric.unit,
                        "granularity": "horaria" if metric.periodicity == "HourlyEntities" else "diaria" if metric.periodicity == "DailyEntities" else "mensual",
                        "timezone": "America/Bogota; confirmar contra respuesta XM",
                    }
                )
    return calls


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    frame = pd.DataFrame(rows)
    for col in frame.columns:
        frame[col] = frame[col].apply(lambda x: json.dumps(x, ensure_ascii=False) if isinstance(x, list) else x)
    frame.to_csv(path, index=False, encoding="utf-8")


def create_download_configs(end_date: str = DEFAULT_PLAN_END_DATE) -> dict[str, Any]:
    root = project_root()
    metrics = build_metric_definitions(end_date=end_date)
    calls = build_call_plan(metrics)
    metrics_data = [metric_to_dict(metric) for metric in metrics]
    resources = {
        "central_hydrothermal_resources": central_hydrothermal_resources(),
        "active_embalse_names": active_embalse_names(),
        "active_rio_names": active_rio_names(),
    }
    plan = {
        "created_by": "scripts/07_preparar_descarga_xm.py",
        "execute_required": True,
        "network_allowed_by_default": False,
        "default_end_date_for_dry_run": end_date,
        "batching": {
            "hourly_daily_max_days": 30,
            "resource_batch_size": RESOURCE_BATCH_SIZE,
            "retry_attempts": 3,
            "backoff_seconds": [2, 5, 10],
        },
        "resources": resources,
        "metrics": metrics_data,
        "estimated_calls": len(calls),
    }
    write_json(root / "config/xm_metrics.json", {"metrics": metrics_data})
    write_json(root / "config/xm_download_plan.json", plan)
    return {"metrics": metrics_data, "calls": calls, "plan": plan}

