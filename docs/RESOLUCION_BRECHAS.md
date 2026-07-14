# Resolucion de brechas locales

La segunda auditoria reviso `sddp`, `embalses_manu`, `xm_validation-main` y `carbon_termo` en modo lectura. No se ejecutaron descargas ni consultas XM.

| Dato | Categoria | Evidencia | Unidad | Cobertura | Limitacion |
|---|---|---|---|---|---|
| `demanda_oficial_sin` | `FOUND_METADATA_ONLY` | ListadoMetricas.xlsx | kWh segun MetricUnits de DemaReal | 61 filas de catalogo; no hay serie descargada DemaReal en fuentes autorizadas | MetricId, URL y MaxDays son metadata; no contienen valores de demanda. |
| `generacion_agregada` | `FOUND_WITH_LIMITATIONS` | generacion_2023_2026.csv | kWh y GWh agregados hidro/termo | 1278 registros; 2023-01-01 a 2026-05-31; nivel Sistema | No incluye solar, eolica, cogeneracion, importaciones, exportaciones ni otras fuentes desagregadas. |
| `generacion_por_recurso` | `FOUND_WITH_LIMITATIONS` | panel_generacion_consumo_carbon_test.csv | kWh y MWh diarios por recurso carbon | 86 registros, 13 recursos, 2026-06-01 a 2026-06-07 | Solo muestra de carbon por 7 dias; no cubre generacion por recurso de todo el SIN ni horizonte historico completo. |
| `capacidad_termica` | `FOUND_WITH_LIMITATIONS` | catalogo_plantas_carbon_principal.csv | MW | 14 recursos carbon principales; 14/77 termicas totales; 14/41 termicas centrales; suma 1611.0 MW | Cubre carbon, no toda la flota termica gas/liquidos/biogas/biomasa/GLP/ACPM/JET-A1. |
| `disponibilidad_termica` | `FOUND_METADATA_ONLY` | catalogo_plantas_carbon_principal.csv | categoria/horas historicas; no MW disponible | estado_operacion para catalogo carbon; horas_con_generacion en panel de prueba 2026-06-01 a 2026-06-07 | No existe disponibilidad fisica MW, indisponibilidad ni mantenimiento futuro. Horas con generacion no equivalen a disponibilidad. |
| `relacion_volumen_energia` | `MISSING_CRITICAL` | baseindices.parquet | masa/porcentaje; no GWh | baseindices 3851 registros; resultados 3978 registros; columnas GWh directas: [] | No hay energia_almacenada_gwh, factor de conversion, productividad ni curva cota-volumen. No se puede calcular GWh conservados ni valor del agua COP/kWh. |
| `almacenamiento_porcentaje` | `FOUND_WITH_LIMITATIONS` | escenarios_con_probabilidad.xlsx | VolumenUtilTotal en fraccion/porcentaje normalizado | 60 filas; 2026-06-01 a 2027-05-01; 5 escenarios | Sirve como trayectoria indicativa, envolvente o indice; no representa energia almacenada GWh. |
| `aportes_hidricos` | `FOUND_WITH_LIMITATIONS` | aportes_2010_2026.csv | Value/indice Sistema; en embalses_manu existen AportesHidricosMasa y AportesPorc | 6027 registros diarios Sistema; 2010-01-01 a 2026-06-01 | No es GWh. Permite escenarios relativos o indices, no balance hidrico energetico sin conversion tecnica. |
| `escenarios_probabilidades` | `FOUND_VALID` | escenarios_con_probabilidad.xlsx | probabilidad 0-1; ONI_forzado; VolumenUtilTotal | 12/12 fechas con suma de probabilidades valida; horizonte 2026-06-01 a 2027-05-01 | Probabilidades asociadas a trayectorias de volumen util, no a aportes energeticos. |
| `limite_termico_agregado` | `FOUND_WITH_LIMITATIONS` | catalogo_plantas_carbon_principal.csv | MW para bloque carbon | bloque carbon principal 1611.0 MW; no toda la termica | Suficiente solo para bloque carbon parcial; no representa gas, liquidos ni demas termicas. |
| `precio_por_recurso` | `FOUND_WITH_LIMITATIONS` | precio_oferta_historical.csv | COP/kWh segun auditoria heredada | 95 codigos con oferta; 40/77 termicas totales; 40/41 centrales | No suple capacidad ni disponibilidad; requiere union por codigo. |
| `codigo_union` | `FOUND_WITH_LIMITATIONS` | catalogo_plantas_carbon_principal.csv | codigo recurso | 14/14 codigos carbon principal aparecen en listado_plantas.csv | Valido para carbon; faltan homologaciones completas de otros combustibles. |
| `combustible` | `FOUND_WITH_LIMITATIONS` | listado_plantas.csv | categoria de combustible | listado_plantas cubre 9 fuentes termicas; carbon_termo detalla carbon | Combustible disponible como categoria; no incluye costos de combustible ni restricciones logisticas. |

## Hallazgos principales

- `DemaReal` existe como metrica en `ListadoMetricas.xlsx`, no como serie local descargada.
- `carbon_termo` aporta capacidad MW y generacion diaria por recurso para una muestra de carbon.
- La capacidad de carbon principal suma 1611.0 MW en 14 recursos.
- La cobertura de carbon principal contra termicas del listado local es 18.18% por conteo total y 34.15% por conteo de termicas despachadas centralmente.
- No existe disponibilidad fisica MW ni mantenimiento futuro.
- `embalses_manu` contiene volumen util/porcentaje/masa, pero no conversion verificable a GWh.
