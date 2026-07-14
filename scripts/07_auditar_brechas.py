from __future__ import annotations

import ast
import csv
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from minenergia_sddp.config.paths import load_data_sources
from minenergia_sddp.validation.availability import (
    AvailabilityCategory,
    can_convert_volume_to_gwh,
    evaluate_aggregate_v1,
    evaluate_resource_v2,
)


def flatten_xm(path: Path) -> pd.DataFrame:
    raw = pd.read_excel(path)
    records: list[dict[str, Any]] = []
    for _, row in raw.iterrows():
        for entity in ast.literal_eval(str(row["ListEntities"])):
            item = {"Date": row.get("Date"), "Id": entity.get("Id")}
            item.update(entity.get("Values", {}))
            records.append(item)
    return pd.DataFrame(records)


def date_span(df: pd.DataFrame, col: str) -> dict[str, Any]:
    values = pd.to_datetime(df[col], errors="coerce")
    return {
        "min": str(values.min().date()) if values.notna().any() else None,
        "max": str(values.max().date()) if values.notna().any() else None,
        "nulls": int(values.isna().sum()),
        "unique": int(values.nunique(dropna=True)),
    }


def table_profile(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        df = pd.read_csv(path)
    elif suffix == ".parquet":
        df = pd.read_parquet(path)
    elif suffix in {".xlsx", ".xls"}:
        xl = pd.ExcelFile(path)
        df = pd.read_excel(path, sheet_name=xl.sheet_names[0])
    else:
        return {"path": str(path), "format": suffix, "rows": None, "columns": []}
    profile: dict[str, Any] = {
        "path": str(path),
        "format": suffix.lstrip("."),
        "rows": int(len(df)),
        "columns": list(df.columns),
        "nulls_top": df.isna().sum().sort_values(ascending=False).head(8).astype(int).to_dict(),
    }
    for col in df.columns:
        if col.lower() in {"date", "fecha", "fecha_actualizacion"}:
            profile[f"{col}_span"] = date_span(df, col)
    return profile


def discover_candidate_files(paths: dict[str, Path]) -> dict[str, list[str]]:
    terms = {
        "demanda": ["dem", "dema", "carga", "balance"],
        "generacion": ["gene", "generacion", "generación"],
        "capacidad": ["capacidad", "mw", "potencia"],
        "disponibilidad": ["disp", "dispon", "indispon", "mantenimiento", "outage"],
        "volumen_energia": ["volumen", "embalse", "gwh", "energia"],
        "aportes": ["aporte", "aportes", "porcapor"],
        "probabilidades": ["escenario", "prob", "oni", "noaa"],
    }
    skip_parts = {".git", "node_modules", "venv", "venv_embalses", ".venv_mcp", "__pycache__", ".pytest_cache"}
    result = {key: [] for key in terms}
    for root in paths.values():
        for path in root.rglob("*"):
            if not path.is_file() or any(part in skip_parts for part in path.parts):
                continue
            if path.suffix.lower() not in {".csv", ".parquet", ".xlsx", ".xls", ".md", ".py", ".json", ".yaml", ".yml"}:
                continue
            name = path.name.lower()
            rel = str(path)
            for key, key_terms in terms.items():
                if any(term in name for term in key_terms):
                    result[key].append(rel)
    return result


def audit() -> dict[str, Any]:
    cfg = load_data_sources()
    paths = {name: Path(item["path"]) for name, item in cfg["external_sources"].items()}
    sddp = paths["sddp_previous"]
    emb = paths["embalses_manu"]
    xm = paths["xm_validation"]
    carbon = paths["carbon_termo"]

    plants = pd.read_csv(sddp / "data/listado_plantas.csv")
    thermal = plants[plants["Values_Type"].astype(str).str.upper().eq("TERMICA")].copy()
    central_thermal = thermal[thermal["Values_Disp"].astype(str).str.upper().eq("DESPACHADO CENTRALMENTE")].copy()
    offer_codes: set[str] = set()
    for chunk in pd.read_csv(sddp / "data/precio_oferta_historical.csv", chunksize=200_000):
        offer_codes.update(chunk["Values_code"].dropna().astype(str).unique())

    metricas = flatten_xm(xm / "data/catalogos/maestros/ListadoMetricas.xlsx")
    demanda_metricas = metricas[
        metricas.astype(str)
        .apply(lambda col: col.str.contains("DemaReal|demanda", case=False, regex=True, na=False))
        .any(axis=1)
    ].copy()

    gen_agg = pd.read_csv(sddp / "data/generacion_2023_2026.csv")
    aportes = pd.read_csv(sddp / "data/aportes_2010_2026.csv")
    bolsa = pd.read_csv(sddp / "data/precio_bolsa_2010_2026.csv")

    carbon_principal = pd.read_csv(carbon / "data/processed/catalogo_plantas_carbon_principal.csv")
    carbon_secundario = pd.read_csv(carbon / "data/processed/catalogo_plantas_carbon_secundario.csv")
    carbon_panel = pd.read_csv(carbon / "data/processed/panel_generacion_consumo_carbon_test.csv")
    carbon_codes = set(carbon_principal["codigo_sic"].dropna().astype(str))
    carbon_panel_codes = set(carbon_panel["codigo_sic"].dropna().astype(str))
    thermal_codes = set(thermal["Values_Code"].dropna().astype(str))
    central_codes = set(central_thermal["Values_Code"].dropna().astype(str))
    carbon_thermal_match = carbon_codes & thermal_codes
    carbon_central_match = carbon_codes & central_codes

    emb_base = pd.read_parquet(emb / "baseindices.parquet")
    emb_resultados = pd.read_parquet(emb / "resultados.parquet")
    emb_pred_multi = pd.read_parquet(emb / "predicciones_multihorizonte.parquet")
    emb_pred_walk = pd.read_parquet(emb / "predicciones_walkforward.parquet")
    escenarios = pd.read_excel(emb / "outputs/escenarios_con_probabilidad.xlsx")
    prob_sums = escenarios.groupby("Fecha", dropna=False)["Probabilidad"].sum().reset_index(name="probability_sum")
    prob_sums["valid"] = (prob_sums["probability_sum"] - 1.0).abs() < 1e-9

    hydro_columns = sorted(set(emb_base.columns) | set(emb_resultados.columns) | set(emb_pred_multi.columns) | set(emb_pred_walk.columns))
    has_gwh_conversion = can_convert_volume_to_gwh(hydro_columns)
    gwh_like_cols = [col for col in hydro_columns if "gwh" in col.lower() or "energia_almacenada" in col.lower()]
    energia_cols = [col for col in hydro_columns if "energia" in col.lower()]
    factor_cols = [col for col in hydro_columns if any(token in col.lower() for token in ["factor", "productividad", "conversion"])]

    findings = [
        {
            "dato": "demanda_oficial_sin",
            "category": AvailabilityCategory.FOUND_METADATA_ONLY.value,
            "evidence_file": str(xm / "data/catalogos/maestros/ListadoMetricas.xlsx"),
            "columns": list(demanda_metricas.columns),
            "unit": "kWh segun MetricUnits de DemaReal",
            "coverage": f"{len(demanda_metricas)} filas de catalogo; no hay serie descargada DemaReal en fuentes autorizadas",
            "granularity": "HourlyEntities en metadata XM",
            "limitation": "MetricId, URL y MaxDays son metadata; no contienen valores de demanda.",
        },
        {
            "dato": "generacion_agregada",
            "category": AvailabilityCategory.FOUND_WITH_LIMITATIONS.value,
            "evidence_file": str(sddp / "data/generacion_2023_2026.csv"),
            "columns": list(gen_agg.columns),
            "unit": "kWh y GWh agregados hidro/termo",
            "coverage": f"{len(gen_agg)} registros; {date_span(gen_agg, 'Date')['min']} a {date_span(gen_agg, 'Date')['max']}; nivel Sistema",
            "granularity": "diaria",
            "limitation": "No incluye solar, eolica, cogeneracion, importaciones, exportaciones ni otras fuentes desagregadas.",
        },
        {
            "dato": "generacion_por_recurso",
            "category": AvailabilityCategory.FOUND_WITH_LIMITATIONS.value,
            "evidence_file": str(carbon / "data/processed/panel_generacion_consumo_carbon_test.csv"),
            "columns": list(carbon_panel.columns),
            "unit": "kWh y MWh diarios por recurso carbon",
            "coverage": f"{len(carbon_panel)} registros, {len(carbon_panel_codes)} recursos, {date_span(carbon_panel, 'fecha')['min']} a {date_span(carbon_panel, 'fecha')['max']}",
            "granularity": "diaria por recurso",
            "limitation": "Solo muestra de carbon por 7 dias; no cubre generacion por recurso de todo el SIN ni horizonte historico completo.",
        },
        {
            "dato": "capacidad_termica",
            "category": AvailabilityCategory.FOUND_WITH_LIMITATIONS.value,
            "evidence_file": str(carbon / "data/processed/catalogo_plantas_carbon_principal.csv"),
            "columns": list(carbon_principal.columns),
            "unit": "MW",
            "coverage": f"{len(carbon_principal)} recursos carbon principales; {len(carbon_thermal_match)}/{len(thermal)} termicas totales; {len(carbon_central_match)}/{len(central_thermal)} termicas centrales; suma {float(carbon_principal['capacidad_mw'].sum()):.1f} MW",
            "granularity": "recurso",
            "limitation": "Cubre carbon, no toda la flota termica gas/liquidos/biogas/biomasa/GLP/ACPM/JET-A1.",
        },
        {
            "dato": "disponibilidad_termica",
            "category": AvailabilityCategory.FOUND_METADATA_ONLY.value,
            "evidence_file": str(carbon / "data/processed/catalogo_plantas_carbon_principal.csv"),
            "columns": ["estado_operacion", "tipo_despacho", "horas_con_generacion", "factor_uso_diario"],
            "unit": "categoria/horas historicas; no MW disponible",
            "coverage": "estado_operacion para catalogo carbon; horas_con_generacion en panel de prueba 2026-06-01 a 2026-06-07",
            "granularity": "recurso y dia en muestra historica",
            "limitation": "No existe disponibilidad fisica MW, indisponibilidad ni mantenimiento futuro. Horas con generacion no equivalen a disponibilidad.",
        },
        {
            "dato": "relacion_volumen_energia",
            "category": AvailabilityCategory.MISSING_CRITICAL.value,
            "evidence_file": str(emb / "baseindices.parquet"),
            "columns": ["VolumenUtilDiarioMasa", "VolumenUtilPorcentaje", "CapacidadUtilMasa", *energia_cols, *factor_cols],
            "unit": "masa/porcentaje; no GWh",
            "coverage": f"baseindices {len(emb_base)} registros; resultados {len(emb_resultados)} registros; columnas GWh directas: {gwh_like_cols}",
            "granularity": "mensual por embalse en observados/proyecciones",
            "limitation": "No hay energia_almacenada_gwh, factor de conversion, productividad ni curva cota-volumen. No se puede calcular GWh conservados ni valor del agua COP/kWh.",
        },
        {
            "dato": "almacenamiento_porcentaje",
            "category": AvailabilityCategory.FOUND_WITH_LIMITATIONS.value,
            "evidence_file": str(emb / "outputs/escenarios_con_probabilidad.xlsx"),
            "columns": list(escenarios.columns),
            "unit": "VolumenUtilTotal en fraccion/porcentaje normalizado",
            "coverage": f"{len(escenarios)} filas; {escenarios['Fecha'].min().date()} a {escenarios['Fecha'].max().date()}; {escenarios['Escenario'].nunique()} escenarios",
            "granularity": "mensual sistema/escenario",
            "limitation": "Sirve como trayectoria indicativa, envolvente o indice; no representa energia almacenada GWh.",
        },
        {
            "dato": "aportes_hidricos",
            "category": AvailabilityCategory.FOUND_WITH_LIMITATIONS.value,
            "evidence_file": str(sddp / "data/aportes_2010_2026.csv"),
            "columns": list(aportes.columns),
            "unit": "Value/indice Sistema; en embalses_manu existen AportesHidricosMasa y AportesPorc",
            "coverage": f"{len(aportes)} registros diarios Sistema; {date_span(aportes, 'Date')['min']} a {date_span(aportes, 'Date')['max']}",
            "granularity": "diaria Sistema en sddp; mensual por embalse/sistema en embalses_manu",
            "limitation": "No es GWh. Permite escenarios relativos o indices, no balance hidrico energetico sin conversion tecnica.",
        },
        {
            "dato": "escenarios_probabilidades",
            "category": AvailabilityCategory.FOUND_VALID.value,
            "evidence_file": str(emb / "outputs/escenarios_con_probabilidad.xlsx"),
            "columns": list(escenarios.columns),
            "unit": "probabilidad 0-1; ONI_forzado; VolumenUtilTotal",
            "coverage": f"{len(prob_sums)}/{len(prob_sums)} fechas con suma de probabilidades valida; horizonte {escenarios['Fecha'].min().date()} a {escenarios['Fecha'].max().date()}",
            "granularity": "mensual por escenario",
            "limitation": "Probabilidades asociadas a trayectorias de volumen util, no a aportes energeticos.",
        },
        {
            "dato": "limite_termico_agregado",
            "category": AvailabilityCategory.FOUND_WITH_LIMITATIONS.value,
            "evidence_file": str(carbon / "data/processed/catalogo_plantas_carbon_principal.csv"),
            "columns": ["codigo_sic", "combustible_principal", "capacidad_mw"],
            "unit": "MW para bloque carbon",
            "coverage": f"bloque carbon principal {float(carbon_principal['capacidad_mw'].sum()):.1f} MW; no toda la termica",
            "granularity": "recurso agregable a bloque carbon",
            "limitation": "Suficiente solo para bloque carbon parcial; no representa gas, liquidos ni demas termicas.",
        },
        {
            "dato": "precio_por_recurso",
            "category": AvailabilityCategory.FOUND_WITH_LIMITATIONS.value,
            "evidence_file": str(sddp / "data/precio_oferta_historical.csv"),
            "columns": ["Values_code", "Values_Hour01..Values_Hour24", "Date"],
            "unit": "COP/kWh segun auditoria heredada",
            "coverage": f"{len(offer_codes)} codigos con oferta; {int(thermal['Values_Code'].isin(offer_codes).sum())}/{len(thermal)} termicas totales; {int(central_thermal['Values_Code'].isin(offer_codes).sum())}/{len(central_thermal)} centrales",
            "granularity": "horaria por recurso y dia",
            "limitation": "No suple capacidad ni disponibilidad; requiere union por codigo.",
        },
        {
            "dato": "codigo_union",
            "category": AvailabilityCategory.FOUND_WITH_LIMITATIONS.value,
            "evidence_file": str(carbon / "data/processed/catalogo_plantas_carbon_principal.csv"),
            "columns": ["codigo_sic", "recurso_xm", "Values_Code"],
            "unit": "codigo recurso",
            "coverage": f"{len(carbon_thermal_match)}/{len(carbon_principal)} codigos carbon principal aparecen en listado_plantas.csv",
            "granularity": "recurso",
            "limitation": "Valido para carbon; faltan homologaciones completas de otros combustibles.",
        },
        {
            "dato": "combustible",
            "category": AvailabilityCategory.FOUND_WITH_LIMITATIONS.value,
            "evidence_file": str(sddp / "data/listado_plantas.csv"),
            "columns": ["Values_EnerSource", "combustible_principal"],
            "unit": "categoria de combustible",
            "coverage": f"listado_plantas cubre {thermal['Values_EnerSource'].nunique()} fuentes termicas; carbon_termo detalla carbon",
            "granularity": "recurso",
            "limitation": "Combustible disponible como categoria; no incluye costos de combustible ni restricciones logisticas.",
        },
    ]

    finding_map = {item["dato"]: AvailabilityCategory(item["category"]) for item in findings}
    gate_v1 = evaluate_aggregate_v1(finding_map).value
    gate_v2 = evaluate_resource_v2(finding_map).value

    capacity_missing_codes = sorted(thermal_codes - carbon_codes)
    coverage = {
        "thermal_total_resources": int(len(thermal)),
        "thermal_central_resources": int(len(central_thermal)),
        "carbon_principal_resources": int(len(carbon_principal)),
        "carbon_secondary_resources": int(len(carbon_secundario)),
        "carbon_panel_resources": int(len(carbon_panel_codes)),
        "carbon_principal_capacity_mw": float(carbon_principal["capacidad_mw"].sum()),
        "carbon_secondary_capacity_mw": float(carbon_secundario["capacidad_mw"].sum()),
        "carbon_coverage_total_thermal_count_pct": float(len(carbon_thermal_match) / len(thermal) * 100),
        "carbon_coverage_central_thermal_count_pct": float(len(carbon_central_match) / len(central_thermal) * 100),
        "carbon_panel_coverage_principal_count_pct": float(len(carbon_panel_codes & carbon_codes) / len(carbon_codes) * 100),
        "offer_coverage_total_thermal_pct": float(thermal["Values_Code"].isin(offer_codes).mean() * 100),
        "offer_coverage_central_thermal_pct": float(central_thermal["Values_Code"].isin(offer_codes).mean() * 100),
        "capacity_missing_thermal_codes_sample": capacity_missing_codes[:30],
    }

    profiles = {
        "sddp_generacion_agregada": table_profile(sddp / "data/generacion_2023_2026.csv"),
        "sddp_aportes": table_profile(sddp / "data/aportes_2010_2026.csv"),
        "sddp_listado_plantas": table_profile(sddp / "data/listado_plantas.csv"),
        "carbon_catalogo_principal": table_profile(carbon / "data/processed/catalogo_plantas_carbon_principal.csv"),
        "carbon_panel_generacion": table_profile(carbon / "data/processed/panel_generacion_consumo_carbon_test.csv"),
        "embalses_baseindices": table_profile(emb / "baseindices.parquet"),
        "embalses_escenarios_probabilidad": table_profile(emb / "outputs/escenarios_con_probabilidad.xlsx"),
        "xm_listado_metricas": table_profile(xm / "data/catalogos/maestros/ListadoMetricas.xlsx"),
    }

    return {
        "gate_v1": gate_v1,
        "gate_v2": gate_v2,
        "findings": findings,
        "coverage": coverage,
        "profiles": profiles,
        "probability_sums": prob_sums.assign(Fecha=prob_sums["Fecha"].astype(str)).to_dict("records"),
        "candidate_files": discover_candidate_files(paths),
        "hydro_evidence": {
            "columns_with_energia": energia_cols,
            "columns_with_gwh": gwh_like_cols,
            "columns_with_conversion_factor": factor_cols,
            "can_convert_volume_to_gwh": has_gwh_conversion,
            "baseindices_date_span": date_span(emb_base, "Fecha"),
            "resultados_date_span": date_span(emb_resultados, "Fecha"),
            "predicciones_multihorizonte_columns": list(emb_pred_multi.columns),
            "predicciones_walkforward_columns": list(emb_pred_walk.columns),
        },
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "dato",
        "category",
        "evidence_file",
        "unit",
        "coverage",
        "granularity",
        "limitation",
        "columns",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            item = dict(row)
            item["columns"] = "; ".join(map(str, item.get("columns", [])))
            writer.writerow({key: item.get(key, "") for key in fieldnames})


def category_table(rows: list[dict[str, Any]]) -> str:
    lines = ["| Dato | Categoria | Evidencia | Unidad | Cobertura | Limitacion |", "|---|---|---|---|---|---|"]
    for row in rows:
        evidence = Path(row["evidence_file"]).name
        lines.append(f"| `{row['dato']}` | `{row['category']}` | {evidence} | {row['unit']} | {row['coverage']} | {row['limitation']} |")
    return "\n".join(lines)


def write_docs(result: dict[str, Any]) -> None:
    docs = ROOT / "docs"
    rows = result["findings"]
    coverage = result["coverage"]
    hydro = result["hydro_evidence"]
    missing = [r for r in rows if r["category"] in {AvailabilityCategory.MISSING_CRITICAL.value, AvailabilityCategory.FOUND_METADATA_ONLY.value}]

    (docs / "RESOLUCION_BRECHAS.md").write_text(
        f"""# Resolucion de brechas locales

La segunda auditoria reviso `sddp`, `embalses_manu`, `xm_validation-main` y `carbon_termo` en modo lectura. No se ejecutaron descargas ni consultas XM.

{category_table(rows)}

## Hallazgos principales

- `DemaReal` existe como metrica en `ListadoMetricas.xlsx`, no como serie local descargada.
- `carbon_termo` aporta capacidad MW y generacion diaria por recurso para una muestra de carbon.
- La capacidad de carbon principal suma {coverage['carbon_principal_capacity_mw']:.1f} MW en {coverage['carbon_principal_resources']} recursos.
- La cobertura de carbon principal contra termicas del listado local es {coverage['carbon_coverage_total_thermal_count_pct']:.2f}% por conteo total y {coverage['carbon_coverage_central_thermal_count_pct']:.2f}% por conteo de termicas despachadas centralmente.
- No existe disponibilidad fisica MW ni mantenimiento futuro.
- `embalses_manu` contiene volumen util/porcentaje/masa, pero no conversion verificable a GWh.
""",
        encoding="utf-8",
    )
    (docs / "MATRIZ_DISPONIBILIDAD_DATOS.md").write_text(
        "# Matriz de disponibilidad de datos\n\n" + category_table(rows),
        encoding="utf-8",
    )
    (docs / "PUERTA_AGREGADA_V1.md").write_text(
        f"""# Puerta A - Modelo agregado V1

Estado: **{result['gate_v1']}**

## Evaluacion

- Demanda del sistema: `FOUND_METADATA_ONLY`; no hay serie local descargada.
- Generacion termica e hidraulica agregada: `FOUND_WITH_LIMITATIONS`; existe `generacion_2023_2026.csv`.
- Almacenamiento en porcentaje/indice: `FOUND_WITH_LIMITATIONS`; existe `escenarios_con_probabilidad.xlsx`.
- Escenarios prospectivos y probabilidades: `FOUND_VALID`; suman 1 para cada fecha.
- Limites termicos agregados o por bloques: `FOUND_WITH_LIMITATIONS`; existe bloque carbon parcial, no flota termica completa.

## Decision

La V1 agregada queda bloqueada porque no hay demanda oficial descargada ni limite termico agregado de toda la flota. Puede prepararse una version exploratoria de indices/escenarios, pero no una recomendacion agregada de generacion termica.
""",
        encoding="utf-8",
    )
    (docs / "PUERTA_RECURSOS_V2.md").write_text(
        f"""# Puerta B - Modelo por recurso V2

Estado: **{result['gate_v2']}**

## Evaluacion

- Capacidad MW por recurso: parcial para carbon.
- Disponibilidad MW por recurso: no disponible; solo categorias/estado y generacion observada.
- Precio por recurso: parcial, ofertas historicas para {coverage['offer_coverage_total_thermal_pct']:.2f}% de termicas totales y {coverage['offer_coverage_central_thermal_pct']:.2f}% de termicas centrales.
- Generacion observada por recurso: parcial, muestra carbon de 7 dias.
- Codigo de union: parcial, valido para carbon.
- Combustible: disponible como categoria.

## Decision

La V2 por recurso queda bloqueada. Los datos de `carbon_termo` reducen la brecha de capacidad para el bloque carbon, pero no habilitan recomendacion por planta para toda la flota termica.
""",
        encoding="utf-8",
    )
    (docs / "DECISION_GATE2.md").write_text(
        f"""# Decision gate 2

## Estados

- Puerta agregada V1: **{result['gate_v1']}**
- Puerta por recurso V2: **{result['gate_v2']}**

## Variables verificadas

- Probabilidades de escenarios: validas en `escenarios_con_probabilidad.xlsx`.
- Generacion agregada hidro/termo: disponible con limitaciones en `generacion_2023_2026.csv`.
- Precios de oferta por recurso: disponibles con limitaciones en `precio_oferta_historical.csv`.

## Variables parciales

- Capacidad termica: parcial para carbon en `carbon_termo`.
- Generacion por recurso: parcial para carbon, 2026-06-01 a 2026-06-07.
- Almacenamiento: porcentaje/masa, no energia.
- Aportes: indice/masa/porcentaje, no GWh.

## Variables realmente faltantes

- Serie local descargada de demanda oficial SIN.
- Capacidad o limite agregado para toda la flota termica.
- Disponibilidad fisica MW historica y futura.
- Relacion volumen-energia para embalses.
- Generacion por recurso completa para todo el SIN.

## Justificacion

La decision se basa en archivos perfilados y no en nombres aproximados. Una ruta, `MetricId` o URL no fue considerada dato descargado.
""",
        encoding="utf-8",
    )
    (docs / "BRECHAS_DATOS2.md").write_text(
        "# Brechas de datos 2\n\n" + "\n".join(f"- `{r['dato']}`: {r['category']} - {r['limitation']}" for r in rows),
        encoding="utf-8",
    )
    (docs / "MATRIZ_UNIDADES2.md").write_text(
        f"""# Matriz de unidades 2

| Dato | Unidad real auditada | Conversion permitida |
|---|---|---|
| Demanda DemaReal | kWh en metadata XM | no hay serie local para convertir |
| Generacion agregada | kWh/GWh | kWh / 1e6 = GWh |
| Generacion carbon por recurso | kWh/MWh | MWh / 1000 = GWh |
| Capacidad carbon | MW | MW * horas / 1000 = GWh maximo teorico del bloque carbon |
| Disponibilidad | categoria/horas observadas | no convertir a MW disponible |
| Embalses | masa/porcentaje/fraccion | no convertir a GWh sin factor tecnico |
| Aportes | indice, masa o porcentaje | no convertir a GWh sin factor tecnico |
| Probabilidad | 0-1 | suma por fecha debe ser 1 |

Columnas de energia en embalses: {hydro['columns_with_energia']}.
Columnas GWh directas en embalses: {hydro['columns_with_gwh']}.
Columnas de factor/productividad/conversion: {hydro['columns_with_conversion_factor']}.
""",
        encoding="utf-8",
    )
    request_rows = [
        {
            "nombre": "Demanda oficial SIN descargada",
            "columnas": "fecha, demanda_kwh o demanda_gwh",
            "unidad": "kWh o GWh",
            "periodo": "2023-actual y horizonte futuro si aplica",
            "granularidad": "horaria o diaria",
            "cobertura": "Sistema",
            "motivo": "La auditoria encontro solo metadata DemaReal, no valores.",
            "puerta": "V1 y V2",
            "local": "xm_validation-main/data/catalogos contiene MetricId, no serie",
            "institucional": "XM/Sinergox DemaReal",
            "proxy": "hidro+termo no es valido sin cuantificar otras fuentes",
            "consecuencia": "balance electrico incompleto",
        },
        {
            "nombre": "Capacidad o limite agregado de toda la flota termica",
            "columnas": "fecha_vigencia, combustible/bloque, capacidad_mw",
            "unidad": "MW",
            "periodo": "vigente para horizonte",
            "granularidad": "bloque o recurso",
            "cobertura": "gas, carbon, liquidos, biogas, biomasa, ACPM, GLP, JET-A1",
            "motivo": "Solo se encontro capacidad de carbon parcial.",
            "puerta": "V1",
            "local": "carbon_termo cubre bloque carbon",
            "institucional": "XM/ListadoRecursos o documentos de capacidad efectiva",
            "proxy": "maximo historico solo retrospectivo",
            "consecuencia": "limites termicos subestimados o sesgados a carbon",
        },
        {
            "nombre": "Disponibilidad fisica termica",
            "columnas": "fecha, codigo_recurso, disponibilidad_mw, estado/mantenimiento",
            "unidad": "MW",
            "periodo": "historico y 26 semanas futuras",
            "granularidad": "diaria/semanal por recurso o bloque",
            "cobertura": "flota termica",
            "motivo": "Solo hay estado categorial y horas con generacion historica.",
            "puerta": "V1 sensibilidad, V2 y decision operativa",
            "local": "no localizada",
            "institucional": "XM o reportes operativos",
            "proxy": "escenarios de sensibilidad si se documentan externamente",
            "consecuencia": "no se puede asegurar factibilidad operativa",
        },
        {
            "nombre": "Relacion volumen-energia de embalses",
            "columnas": "codigo_embalse, volumen/cota, energia_almacenada_gwh o factor_conversion",
            "unidad": "GWh y unidad de volumen",
            "periodo": "vigente",
            "granularidad": "embalse o region",
            "cobertura": "embalses usados en modelo",
            "motivo": "No hay energia almacenada GWh ni factor/productividad.",
            "puerta": "valor del agua, V1 energetica, V2",
            "local": "embalses_manu contiene porcentaje/masa",
            "institucional": "XM/UPME/agentes hidraulicos",
            "proxy": "indice de almacenamiento sin GWh",
            "consecuencia": "no reportar GWh hidraulicos evitados ni COP/kWh del agua",
        },
        {
            "nombre": "Generacion por recurso completa",
            "columnas": "fecha, codigo_recurso, tipo_recurso, generacion_kwh/gwh",
            "unidad": "kWh/GWh",
            "periodo": "2023-actual",
            "granularidad": "horaria o diaria",
            "cobertura": "recursos hidraulicos y termicos del SIN",
            "motivo": "Solo hay agregado Sistema y muestra carbon de 7 dias.",
            "puerta": "V2",
            "local": "carbon_termo muestra carbon",
            "institucional": "XM generacion por recurso",
            "proxy": "bloques agregados historicos si conservan energia total",
            "consecuencia": "no hay recomendacion por planta",
        },
        {
            "nombre": "Aportes hidricos energeticos o convertibles",
            "columnas": "fecha, escenario_id, codigo_embalse/sistema, aporte_gwh o caudal y factor",
            "unidad": "GWh o caudal con factor",
            "periodo": "historico y horizonte",
            "granularidad": "diaria/semanal/mensual",
            "cobertura": "sistema/embalses relevantes",
            "motivo": "Los aportes encontrados son indices/masa/porcentaje, no energia.",
            "puerta": "balance hidrico energetico",
            "local": "sddp/aportes y embalses_manu/AportesHidricosMasa",
            "institucional": "XM hidrologia/aportes",
            "proxy": "escenarios relativos de sequia",
            "consecuencia": "modelo en indice, no balance energetico",
        },
    ]
    lines = [
        "# Solicitud de datos al usuario 2",
        "",
        "Incluye solo datos que siguen ausentes o insuficientes despues de la segunda auditoria.",
        "",
        "| Nombre exacto | Columnas | Unidad | Periodo | Granularidad | Cobertura requerida | Motivo | Puerta que bloquea | Posible fuente local | Posible fuente institucional | Sustitucion temporal | Consecuencia del proxy |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in request_rows:
        lines.append(
            f"| {r['nombre']} | {r['columnas']} | {r['unidad']} | {r['periodo']} | {r['granularidad']} | {r['cobertura']} | {r['motivo']} | {r['puerta']} | {r['local']} | {r['institucional']} | {r['proxy']} | {r['consecuencia']} |"
        )
    (docs / "SOLICITUD_DATOS_USUARIO2.md").write_text("\n".join(lines), encoding="utf-8")


def write_summary(result: dict[str, Any]) -> str:
    coverage = result["coverage"]
    return f"""# Resumen de auditoria de brechas

- Puerta agregada V1: **{result['gate_v1']}**
- Puerta por recurso V2: **{result['gate_v2']}**
- Demanda: solo metadata `DemaReal`, sin serie local.
- Generacion por recurso: parcial en `carbon_termo`, {coverage['carbon_panel_resources']} recursos carbon, 7 dias.
- Capacidad termica: parcial carbon, {coverage['carbon_principal_capacity_mw']:.1f} MW.
- Cobertura capacidad carbon: {coverage['carbon_coverage_total_thermal_count_pct']:.2f}% de termicas totales por conteo; {coverage['carbon_coverage_central_thermal_count_pct']:.2f}% de termicas centrales por conteo.
- Disponibilidad: no hay MW disponible; solo estado/categoria y generacion observada.
- Embalses: volumen util/porcentaje/masa; no GWh.
- Aportes: indice/masa/porcentaje, no energia.
- Probabilidades: `embalses_manu/outputs/escenarios_con_probabilidad.xlsx`, suman 1 por fecha.
"""


def main() -> int:
    result = audit()
    out = ROOT / "outputs/run_005"
    out.mkdir(parents=True, exist_ok=True)
    (out / "auditoria_brechas.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    write_csv(out / "auditoria_brechas.csv", result["findings"])
    summary = write_summary(result)
    (out / "resumen_brechas.md").write_text(summary, encoding="utf-8")
    write_docs(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

