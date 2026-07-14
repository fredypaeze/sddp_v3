from __future__ import annotations

import csv
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from minenergia_sddp.config.paths import load_data_sources
from minenergia_sddp.data.readers import flatten_xm_list_entities
from minenergia_sddp.validation.checks import probabilities_sum_to_one


SKIP_PARTS = {".git", "node_modules", "venv", "venv_embalses", "__pycache__", ".pytest_cache"}
PRIORITY_FILES = {
    "embalses_manu": [
        "README.md",
        "baseindices.parquet",
        "resultados.parquet",
        "predicciones_multihorizonte.parquet",
        "predicciones_walkforward.parquet",
        "metricas_modelo.xlsx",
        "validacion_multihorizonte.xlsx",
        "resultados.xlsx",
        "resultados_walkforward.xlsx",
        "outputs/escenarios_con_probabilidad.xlsx",
        "outputs/escenarios_nacional.xlsx",
        "outputs/escenarios_por_embalse.xlsx",
        "outputs/metricas_multihorizonte.xlsx",
        "outputs/metricas_walkforward.xlsx",
    ],
    "xm_validation": [
        "README.md",
        "config/config.yaml",
        "docs/BACKLOG.md",
        "data/catalogos/maestros/ListadoMetricas.xlsx",
        "data/catalogos/maestros/ListadoRecursos.xlsx",
        "data/catalogos/maestros/ListadoEmbalses.xlsx",
        "data/catalogos/metricas_candidatas_enos.xlsx",
    ],
    "sddp_previous": [
        "README.md",
        "docs/dispatch_hidrotermico.md",
        "data/aportes_2010_2026.csv",
        "data/generacion_2023_2026.csv",
        "data/listado_plantas.csv",
        "data/precio_oferta_historical.csv",
        "data/precio_bolsa_2010_2026.csv",
        "data/sim_normal.npy",
        "data/sim_nino.npy",
        "data/embalses_historico.csv",
    ],
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def should_skip(path: Path) -> bool:
    return any(part in SKIP_PARTS for part in path.parts)


def classify(path: Path) -> str:
    suffix = path.suffix.lower()
    parts = {p.lower() for p in path.parts}
    name = path.name.lower()
    if name.startswith(".") or "cache" in parts:
        return "cache"
    if suffix in {".py", ".ipynb"}:
        return "codigo"
    if suffix in {".md", ".yaml", ".yml", ".json", ".txt"}:
        return "documentacion"
    if "outputs" in parts or "reports" in parts:
        return "output de modelo"
    if "legacy" in parts:
        return "legado"
    if suffix in {".csv", ".parquet", ".xlsx", ".xls", ".npy"}:
        return "fuente procesada"
    if suffix in {".png", ".jpg", ".jpeg", ".gif", ".html", ".pptx"}:
        return "no relevante"
    return "no relevante"


def profile_table(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    out: dict[str, Any] = {"format": suffix.lstrip(".")}
    try:
        if suffix == ".csv":
            if path.stat().st_size > 20_000_000:
                rows = 0
                cols: list[str] | None = None
                min_date = None
                max_date = None
                null_dates = 0
                unique_codes: set[str] = set()
                for chunk in pd.read_csv(path, chunksize=200_000):
                    rows += len(chunk)
                    cols = list(chunk.columns)
                    if "Date" in chunk.columns:
                        dates = pd.to_datetime(chunk["Date"], errors="coerce")
                        null_dates += int(dates.isna().sum())
                        if dates.notna().any():
                            min_date = dates.min() if min_date is None else min(min_date, dates.min())
                            max_date = dates.max() if max_date is None else max(max_date, dates.max())
                    for code_col in ["Values_code", "Values_Code", "codigo_recurso"]:
                        if code_col in chunk.columns:
                            unique_codes.update(chunk[code_col].dropna().astype(str).unique().tolist())
                out.update(
                    rows=rows,
                    columns=cols or [],
                    min_date=str(min_date.date()) if min_date is not None else None,
                    max_date=str(max_date.date()) if max_date is not None else None,
                    null_dates=null_dates,
                    unique_codes=len(unique_codes),
                )
            else:
                df = pd.read_csv(path)
                out.update(_profile_df(df))
        elif suffix == ".parquet":
            df = pd.read_parquet(path)
            out.update(_profile_df(df))
        elif suffix in {".xlsx", ".xls"}:
            xl = pd.ExcelFile(path)
            out["sheets"] = xl.sheet_names
            df = pd.read_excel(path, sheet_name=xl.sheet_names[0])
            out.update(_profile_df(df))
        elif suffix == ".npy":
            arr = np.load(path, allow_pickle=False)
            out.update(shape=list(arr.shape), dtype=str(arr.dtype), min=float(np.nanmin(arr)), max=float(np.nanmax(arr)))
        elif suffix == ".md":
            text = path.read_text(encoding="utf-8", errors="ignore")
            out.update(lines=text.count("\n") + 1, excerpt=text[:500].replace("\n", " "))
    except Exception as exc:
        out["error"] = f"{type(exc).__name__}: {exc}"
    return out


def _profile_df(df: pd.DataFrame) -> dict[str, Any]:
    result: dict[str, Any] = {
        "rows": int(len(df)),
        "columns": list(df.columns),
        "dtypes": {c: str(t) for c, t in df.dtypes.items()},
        "nulls_top": df.isna().sum().sort_values(ascending=False).head(10).astype(int).to_dict(),
        "duplicates_all_columns": int(df.duplicated().sum()),
    }
    for col in ["Date", "Fecha", "fecha"]:
        if col in df.columns:
            dates = pd.to_datetime(df[col], errors="coerce")
            result["date_column"] = col
            result["min_date"] = str(dates.min().date()) if dates.notna().any() else None
            result["max_date"] = str(dates.max().date()) if dates.notna().any() else None
            result["null_dates"] = int(dates.isna().sum())
            break
    return result


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def inventory_sources(cfg: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    inventory: list[dict[str, Any]] = []
    manifest: list[dict[str, Any]] = []
    profiles: dict[str, Any] = {}
    for source_name, source in cfg["external_sources"].items():
        root = Path(source["path"])
        for file_path in root.rglob("*"):
            if should_skip(file_path) or not file_path.is_file():
                continue
            rel = file_path.relative_to(root).as_posix()
            category = classify(file_path)
            stat = file_path.stat()
            is_priority = rel in PRIORITY_FILES.get(source_name, [])
            inventory.append(
                {
                    "source": source_name,
                    "relative_path": rel,
                    "classification": category,
                    "available": True,
                    "size_bytes": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                    "priority": is_priority,
                    "potential_use": "auditoria" if is_priority else "referencia/no prioritario",
                }
            )
        for rel in PRIORITY_FILES.get(source_name, []):
            path = root / rel
            if not path.exists():
                inventory.append(
                    {
                        "source": source_name,
                        "relative_path": rel,
                        "classification": "fuente primaria",
                        "available": False,
                        "size_bytes": "",
                        "modified": "",
                        "priority": True,
                        "potential_use": "faltante",
                    }
                )
                continue
            stat = path.stat()
            profile = profile_table(path)
            profiles[f"{source_name}/{rel}"] = profile
            manifest.append(
                {
                    "source": source_name,
                    "original_path": str(path),
                    "destination_path": "",
                    "name": path.name,
                    "size_bytes": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                    "sha256": sha256_file(path),
                    "description": _description_for(source_name, rel),
                    "unit": _unit_for(source_name, rel, profile),
                    "period": f"{profile.get('min_date', '')} a {profile.get('max_date', '')}",
                    "granularity": _granularity_for(source_name, rel),
                    "reason": _reason_for(source_name, rel),
                }
            )
    return inventory, manifest, profiles


def _description_for(source: str, rel: str) -> str:
    if source == "embalses_manu":
        return "Modelo/proyeccion de volumen util de embalses y escenarios ENOS."
    if source == "xm_validation":
        return "Catalogo o documentacion local de metricas y entidades XM."
    return "Dato historico local proveniente del proyecto SDDP anterior."


def _unit_for(source: str, rel: str, profile: dict[str, Any]) -> str:
    cols = " ".join(profile.get("columns", []))
    if "precio" in rel.lower() or "Precio" in cols:
        return "COP/kWh segun archivos heredados; requiere confirmacion XM por metrica"
    if "generacion" in rel.lower():
        return "kWh y GWh en columnas hidro/termo"
    if "aportes" in rel.lower():
        return "indice/valor Sistema; unidad hidrologica no documentada en archivo"
    if "embalses" in source:
        return "volumen util en masa/porcentaje; sin conversion auditada a GWh"
    if "ListadoMetricas" in rel:
        return "segun MetricUnits del catalogo XM"
    return "no aplica/no documentada"


def _granularity_for(source: str, rel: str) -> str:
    lowered = rel.lower()
    if source == "embalses_manu":
        return "mensual por embalse o sistema segun archivo"
    if any(token in lowered for token in ["generacion", "aportes", "precio"]):
        return "diaria con columnas horarias en precios"
    return "catalogo/documentacion"


def _reason_for(source: str, rel: str) -> str:
    if source == "embalses_manu":
        return "Auditar almacenamiento observado/proyectado y escenarios ENOS sin tratar volumen como aporte."
    if source == "xm_validation":
        return "Auditar nombres oficiales, unidades, granularidad y codigos XM sin consultar API."
    return "Auditar antecedentes y datos historicos descargados; no reutilizar parametros hardcoded."


def build_quality_report(cfg: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    sddp = Path(cfg["external_sources"]["sddp_previous"]["path"])
    emb = Path(cfg["external_sources"]["embalses_manu"]["path"])
    xm = Path(cfg["external_sources"]["xm_validation"]["path"])

    plants = pd.read_csv(sddp / "data/listado_plantas.csv")
    thermal = plants[plants["Values_Type"].astype(str).str.upper().eq("TERMICA")].copy()
    offer_codes: set[str] = set()
    offer_dates: list[pd.Timestamp] = []
    for chunk in pd.read_csv(sddp / "data/precio_oferta_historical.csv", chunksize=200_000):
        offer_codes.update(chunk["Values_code"].dropna().astype(str).unique().tolist())
        offer_dates.append(pd.to_datetime(chunk["Date"], errors="coerce").min())
        offer_dates.append(pd.to_datetime(chunk["Date"], errors="coerce").max())

    gen = pd.read_csv(sddp / "data/generacion_2023_2026.csv")
    aportes = pd.read_csv(sddp / "data/aportes_2010_2026.csv")
    bolsa = pd.read_csv(sddp / "data/precio_bolsa_2010_2026.csv")
    escenarios = pd.read_excel(emb / "outputs/escenarios_con_probabilidad.xlsx")
    xm_metricas = flatten_xm_list_entities(xm / "data/catalogos/maestros/ListadoMetricas.xlsx")

    metric_ids = set(xm_metricas.get("MetricId", pd.Series(dtype=str)).dropna().astype(str))
    required_metric_presence = {
        "DemaReal": "DemaReal" in metric_ids,
        "catalogo_metricas_disponible": len(metric_ids) > 0,
    }
    prob_by_date = probabilities_sum_to_one(escenarios, ["Fecha"], "Probabilidad")
    central_thermal = thermal[thermal["Values_Disp"].astype(str).str.upper().eq("DESPACHADO CENTRALMENTE")]
    tables = [
        {
            "metric": "catalogo_vs_generacion_por_recurso",
            "value": 0.0,
            "detail": "generacion_2023_2026.csv esta agregada a Sistema; no trae codigo_recurso.",
        },
        {
            "metric": "termicas_con_precio_oferta",
            "value": float(thermal["Values_Code"].isin(offer_codes).mean()) if len(thermal) else 0.0,
            "detail": f"{int(thermal['Values_Code'].isin(offer_codes).sum())}/{len(thermal)} recursos termicos.",
        },
        {
            "metric": "termicas_centrales_con_precio_oferta",
            "value": float(central_thermal["Values_Code"].isin(offer_codes).mean()) if len(central_thermal) else 0.0,
            "detail": f"{int(central_thermal['Values_Code'].isin(offer_codes).sum())}/{len(central_thermal)} termicas despachadas centralmente.",
        },
        {
            "metric": "termicas_con_capacidad_mw",
            "value": 0.0,
            "detail": "Listado de plantas no contiene capacidad_mw.",
        },
        {
            "metric": "termicas_con_disponibilidad_mw",
            "value": 0.0,
            "detail": "Values_Disp es clasificacion de despacho central, no disponibilidad_mw temporal.",
        },
        {
            "metric": "escenarios_probabilidades_validas_por_fecha",
            "value": float(prob_by_date["valid"].mean()) if len(prob_by_date) else 0.0,
            "detail": f"{int(prob_by_date['valid'].sum())}/{len(prob_by_date)} fechas suman 1.",
        },
    ]
    quality = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "BLOCKED_CRITICAL_DATA",
        "decision_reasons": [
            "No hay demanda oficial local ni desagregacion de solar, eolica, cogeneracion, importaciones u otras fuentes para reconstruir balance electrico.",
            "La generacion historica disponible esta agregada a Sistema en hidro_gwh y termo_gwh; no permite recomendacion por recurso.",
            "No hay capacidad_mw ni disponibilidad_mw temporal por recurso termico en los archivos auditados.",
            "embalses_manu proyecta volumen util/porcentaje mensual; no existe relacion tecnica auditada para convertir volumen util o masa a energia almacenada GWh.",
            "Las trayectorias proyectadas de volumen no son aportes hidricos exogenos ni pueden fijarse como almacenamiento endogeno del despacho.",
        ],
        "coverage": {
            "generation_rows": int(len(gen)),
            "generation_range": [str(pd.to_datetime(gen["Date"]).min().date()), str(pd.to_datetime(gen["Date"]).max().date())],
            "aportes_rows": int(len(aportes)),
            "aportes_range": [str(pd.to_datetime(aportes["Date"]).min().date()), str(pd.to_datetime(aportes["Date"]).max().date())],
            "bolsa_rows": int(len(bolsa)),
            "bolsa_range": [str(pd.to_datetime(bolsa["Date"]).min().date()), str(pd.to_datetime(bolsa["Date"]).max().date())],
            "offer_resource_codes": len(offer_codes),
            "offer_range": [
                str(min([d for d in offer_dates if pd.notna(d)]).date()),
                str(max([d for d in offer_dates if pd.notna(d)]).date()),
            ],
            "thermal_resources": int(len(thermal)),
            "central_thermal_resources": int(len(central_thermal)),
            "xm_metric_presence": required_metric_presence,
            "scenario_dates": int(escenarios["Fecha"].nunique()),
            "scenario_names": sorted(escenarios["Escenario"].dropna().astype(str).unique().tolist()),
        },
        "probability_sums": prob_by_date.assign(Fecha=prob_by_date["Fecha"].astype(str)).to_dict("records"),
    }
    return quality, tables


def write_docs(inventory: list[dict[str, Any]], manifest: list[dict[str, Any]], profiles: dict[str, Any], quality: dict[str, Any]) -> None:
    docs = ROOT / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "INVENTARIO_FUENTES.md").write_text(_inventory_md(inventory, profiles), encoding="utf-8")
    (docs / "FUENTES_Y_TRAZABILIDAD.md").write_text(_traceability_md(manifest), encoding="utf-8")
    (docs / "ARQUITECTURA.md").write_text(_architecture_md(), encoding="utf-8")
    (docs / "PLAN_IMPLEMENTACION.md").write_text(_plan_md(), encoding="utf-8")
    (docs / "DECISION_GATE.md").write_text(_decision_gate_md(quality), encoding="utf-8")


def _inventory_md(inventory: list[dict[str, Any]], profiles: dict[str, Any]) -> str:
    counts = pd.DataFrame(inventory).groupby(["source", "classification"]).size().reset_index(name="n")
    lines = ["# Inventario de fuentes", "", "Auditoria local sin modificar las fuentes externas.", "", "## Resumen por fuente y clasificacion", ""]
    lines.extend(["| Fuente | Clasificacion | Archivos |", "|---|---|---:|"])
    for _, row in counts.iterrows():
        lines.append(f"| {row['source']} | {row['classification']} | {int(row['n'])} |")
    lines.extend(["", "## Archivos prioritarios perfilados", ""])
    for key, profile in sorted(profiles.items()):
        lines.append(f"### {key}")
        lines.append(f"- Filas: {profile.get('rows', profile.get('shape', 'no tabular'))}")
        lines.append(f"- Fechas: {profile.get('min_date')} a {profile.get('max_date')}")
        cols = profile.get("columns", [])
        lines.append(f"- Columnas: {', '.join(cols[:25])}{' ...' if len(cols) > 25 else ''}")
        if "error" in profile:
            lines.append(f"- Error de perfilado: {profile['error']}")
        lines.append("")
    return "\n".join(lines)


def _traceability_md(manifest: list[dict[str, Any]]) -> str:
    lines = [
        "# Fuentes y trazabilidad",
        "",
        "No se copiaron insumos originales a `data/raw` durante esta fase. El manifiesto registra ruta original, SHA-256 y razon tecnica de cada insumo auditado.",
        "",
        "| Fuente | Archivo | SHA-256 | Unidad | Periodo | Uso |",
        "|---|---|---|---|---|---|",
    ]
    for row in manifest:
        lines.append(
            f"| {row['source']} | {row['name']} | `{row['sha256'][:16]}...` | {row['unit']} | {row['period']} | {row['reason']} |"
        )
    return "\n".join(lines)


def _architecture_md() -> str:
    return """# Arquitectura

El proyecto separa configuracion, auditoria de datos, contratos, validacion, despacho, riesgo y reporte.

- `config/data_sources.json`: unica ubicacion autorizada para rutas externas.
- `data/raw`: reservado para copias auditadas; no se copio ningun insumo original en esta corrida.
- `data/interim` y `data/processed`: salidas intermedias reproducibles.
- `src/minenergia_sddp`: paquete Python compatible con Python 3.11.9.
- `outputs/run_001`: puerta de calidad de datos.
- `outputs/run_002`, `run_003`, `run_004`: reservados para backtest, prospectivo y CVaR si la puerta lo permite.

La primera version no se denomina SDDP completo. La salida objetivo se denomina "Recomendacion de despacho y priorizacion termica".
"""


def _plan_md() -> str:
    return """# Plan de implementacion

1. Inventario de fuentes externas en solo lectura.
2. Auditoria de unidades, granularidades, cobertura y relaciones.
3. Contratos de datos por dominio.
4. Matriz de unidades y brechas.
5. Puerta de calidad.
6. Formulacion matematica condicionada a la puerta.
7. Backtest deterministico solo si existen balances fisicos reconstruibles.
8. Prospectivo y valor del agua solo si hay datos prospectivos consistentes.
9. CVaR solo despues de una base deterministica valida.
10. Reporte final con procedencia de cada cifra.
"""


def _decision_gate_md(quality: dict[str, Any]) -> str:
    reasons = "\n".join(f"- {item}" for item in quality["decision_reasons"])
    return f"""# Puerta de calidad de datos

Estado asignado: **{quality['status']}**

## Razones

{reasons}

## Implicacion

No se construye optimizador ni se emiten recomendaciones operativas. Se completan arquitectura, contratos, trazabilidad, adaptadores y pruebas de datos. La formulacion matematica queda documentada como especificacion condicionada a recibir datos faltantes.
"""


def main() -> int:
    cfg = load_data_sources()
    inventory, manifest, profiles = inventory_sources(cfg)
    quality, tables = build_quality_report(cfg)

    write_csv(
        ROOT / "data/inventario_fuentes.csv",
        inventory,
        ["source", "relative_path", "classification", "available", "size_bytes", "modified", "priority", "potential_use"],
    )
    write_csv(
        ROOT / "data/manifest_sha256.csv",
        manifest,
        [
            "source",
            "original_path",
            "destination_path",
            "name",
            "size_bytes",
            "modified",
            "sha256",
            "description",
            "unit",
            "period",
            "granularity",
            "reason",
        ],
    )
    write_csv(ROOT / "data/catalogo_fuentes.csv", manifest, ["source", "name", "description", "unit", "period", "granularity", "reason"])

    out = ROOT / "outputs/run_001"
    out.mkdir(parents=True, exist_ok=True)
    (out / "reporte_calidad_datos.json").write_text(json.dumps(quality, indent=2, ensure_ascii=False), encoding="utf-8")
    write_csv(out / "tablas_calidad.csv", tables, ["metric", "value", "detail"])
    (out / "reporte_calidad_datos.md").write_text(_quality_md(quality, tables), encoding="utf-8")
    write_docs(inventory, manifest, profiles, quality)
    return 0


def _quality_md(quality: dict[str, Any], tables: list[dict[str, Any]]) -> str:
    lines = ["# Reporte de calidad de datos", "", f"Estado: **{quality['status']}**", "", "## Cobertura", ""]
    for key, value in quality["coverage"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Indicadores", "", "| Metrica | Valor | Detalle |", "|---|---:|---|"])
    for row in tables:
        lines.append(f"| {row['metric']} | {row['value']:.6f} | {row['detail']} |")
    lines.extend(["", "## Razones de bloqueo", ""])
    lines.extend(f"- {item}" for item in quality["decision_reasons"])
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
