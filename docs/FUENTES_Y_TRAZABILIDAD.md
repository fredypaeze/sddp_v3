# Fuentes y trazabilidad

No se copiaron insumos originales a `data/raw` durante esta fase. El manifiesto registra ruta original, SHA-256 y razon tecnica de cada insumo auditado.

| Fuente | Archivo | SHA-256 | Unidad | Periodo | Uso |
|---|---|---|---|---|---|
| sddp_previous | README.md | `9c6f75b626af0825...` | no aplica/no documentada |  a  | Auditar antecedentes y datos historicos descargados; no reutilizar parametros hardcoded. |
| sddp_previous | dispatch_hidrotermico.md | `85d5cfe3acfa7250...` | no aplica/no documentada |  a  | Auditar antecedentes y datos historicos descargados; no reutilizar parametros hardcoded. |
| sddp_previous | aportes_2010_2026.csv | `6ae4a6b8dd39b030...` | indice/valor Sistema; unidad hidrologica no documentada en archivo | 2010-01-01 a 2026-06-01 | Auditar antecedentes y datos historicos descargados; no reutilizar parametros hardcoded. |
| sddp_previous | generacion_2023_2026.csv | `135899f209a7c9fd...` | kWh y GWh en columnas hidro/termo | 2023-01-01 a 2026-05-31 | Auditar antecedentes y datos historicos descargados; no reutilizar parametros hardcoded. |
| sddp_previous | listado_plantas.csv | `e288b026a7bacd8d...` | no aplica/no documentada | 2026-06-03 a 2026-06-03 | Auditar antecedentes y datos historicos descargados; no reutilizar parametros hardcoded. |
| sddp_previous | precio_oferta_historical.csv | `398d8d38e86a1694...` | COP/kWh segun archivos heredados; requiere confirmacion XM por metrica | 2010-01-01 a 2026-06-30 | Auditar antecedentes y datos historicos descargados; no reutilizar parametros hardcoded. |
| sddp_previous | precio_bolsa_2010_2026.csv | `6937a9330093e740...` | COP/kWh segun archivos heredados; requiere confirmacion XM por metrica | 2010-01-01 a 2026-05-31 | Auditar antecedentes y datos historicos descargados; no reutilizar parametros hardcoded. |
| sddp_previous | sim_normal.npy | `fd9b9e28b2f3f3fc...` | no aplica/no documentada |  a  | Auditar antecedentes y datos historicos descargados; no reutilizar parametros hardcoded. |
| sddp_previous | sim_nino.npy | `9fe3704b57ac934d...` | no aplica/no documentada |  a  | Auditar antecedentes y datos historicos descargados; no reutilizar parametros hardcoded. |
| sddp_previous | embalses_historico.csv | `7eb70257593da06f...` | no aplica/no documentada |  a  | Auditar antecedentes y datos historicos descargados; no reutilizar parametros hardcoded. |
| embalses_manu | README.md | `96a35f75fb77f7b6...` | volumen util en masa/porcentaje; sin conversion auditada a GWh |  a  | Auditar almacenamiento observado/proyectado y escenarios ENOS sin tratar volumen como aporte. |
| embalses_manu | baseindices.parquet | `eab7cf064ad18a2b...` | volumen util en masa/porcentaje; sin conversion auditada a GWh | 2013-01-01 a 2026-05-01 | Auditar almacenamiento observado/proyectado y escenarios ENOS sin tratar volumen como aporte. |
| embalses_manu | resultados.parquet | `085f01adae2e7f95...` | volumen util en masa/porcentaje; sin conversion auditada a GWh | 2013-01-01 a 2027-05-01 | Auditar almacenamiento observado/proyectado y escenarios ENOS sin tratar volumen como aporte. |
| embalses_manu | predicciones_multihorizonte.parquet | `23d716d432bb4876...` | volumen util en masa/porcentaje; sin conversion auditada a GWh | 2020-01-01 a 2025-12-01 | Auditar almacenamiento observado/proyectado y escenarios ENOS sin tratar volumen como aporte. |
| embalses_manu | predicciones_walkforward.parquet | `67ba50785634412d...` | volumen util en masa/porcentaje; sin conversion auditada a GWh | 2021-01-01 a 2025-12-01 | Auditar almacenamiento observado/proyectado y escenarios ENOS sin tratar volumen como aporte. |
| embalses_manu | metricas_modelo.xlsx | `f59ead934be7b437...` | volumen util en masa/porcentaje; sin conversion auditada a GWh |  a  | Auditar almacenamiento observado/proyectado y escenarios ENOS sin tratar volumen como aporte. |
| embalses_manu | validacion_multihorizonte.xlsx | `6a89b28432b649d7...` | volumen util en masa/porcentaje; sin conversion auditada a GWh |  a  | Auditar almacenamiento observado/proyectado y escenarios ENOS sin tratar volumen como aporte. |
| embalses_manu | resultados.xlsx | `2715550322995574...` | volumen util en masa/porcentaje; sin conversion auditada a GWh | 2013-01-01 a 2027-05-01 | Auditar almacenamiento observado/proyectado y escenarios ENOS sin tratar volumen como aporte. |
| embalses_manu | resultados_walkforward.xlsx | `24bd7fe3380938e2...` | volumen util en masa/porcentaje; sin conversion auditada a GWh |  a  | Auditar almacenamiento observado/proyectado y escenarios ENOS sin tratar volumen como aporte. |
| embalses_manu | escenarios_con_probabilidad.xlsx | `a70ad7e274b3f686...` | volumen util en masa/porcentaje; sin conversion auditada a GWh | 2026-06-01 a 2027-05-01 | Auditar almacenamiento observado/proyectado y escenarios ENOS sin tratar volumen como aporte. |
| embalses_manu | escenarios_nacional.xlsx | `5d54f9d0a7c19bdb...` | volumen util en masa/porcentaje; sin conversion auditada a GWh | 2026-06-01 a 2027-05-01 | Auditar almacenamiento observado/proyectado y escenarios ENOS sin tratar volumen como aporte. |
| embalses_manu | escenarios_por_embalse.xlsx | `ff8dd3ad8fac2166...` | volumen util en masa/porcentaje; sin conversion auditada a GWh |  a  | Auditar almacenamiento observado/proyectado y escenarios ENOS sin tratar volumen como aporte. |
| embalses_manu | metricas_multihorizonte.xlsx | `6f874eddeec5fb0b...` | volumen util en masa/porcentaje; sin conversion auditada a GWh |  a  | Auditar almacenamiento observado/proyectado y escenarios ENOS sin tratar volumen como aporte. |
| embalses_manu | metricas_walkforward.xlsx | `b6ce24be445dd929...` | volumen util en masa/porcentaje; sin conversion auditada a GWh |  a  | Auditar almacenamiento observado/proyectado y escenarios ENOS sin tratar volumen como aporte. |
| xm_validation | README.md | `e7484c8dd3e1ab15...` | no aplica/no documentada |  a  | Auditar nombres oficiales, unidades, granularidad y codigos XM sin consultar API. |
| xm_validation | config.yaml | `e3b0c44298fc1c14...` | no aplica/no documentada |  a  | Auditar nombres oficiales, unidades, granularidad y codigos XM sin consultar API. |
| xm_validation | BACKLOG.md | `1a18098e21ce7b2b...` | no aplica/no documentada |  a  | Auditar nombres oficiales, unidades, granularidad y codigos XM sin consultar API. |
| xm_validation | ListadoMetricas.xlsx | `d105a07e37f2a28a...` | segun MetricUnits del catalogo XM | 2026-06-11 a 2026-06-11 | Auditar nombres oficiales, unidades, granularidad y codigos XM sin consultar API. |
| xm_validation | ListadoRecursos.xlsx | `b2d290b33ee6c226...` | no aplica/no documentada | 2026-06-11 a 2026-06-11 | Auditar nombres oficiales, unidades, granularidad y codigos XM sin consultar API. |
| xm_validation | ListadoEmbalses.xlsx | `12b58a9949ce192a...` | no aplica/no documentada | 2026-06-11 a 2026-06-11 | Auditar nombres oficiales, unidades, granularidad y codigos XM sin consultar API. |
| xm_validation | metricas_candidatas_enos.xlsx | `0e0a8fb4b5610d30...` | no aplica/no documentada | 2026-06-11 a 2026-06-11 | Auditar nombres oficiales, unidades, granularidad y codigos XM sin consultar API. |