# Inventario de fuentes

Auditoria local sin modificar las fuentes externas.

## Resumen por fuente y clasificacion

| Fuente | Clasificacion | Archivos |
|---|---|---:|
| embalses_manu | cache | 1 |
| embalses_manu | codigo | 6 |
| embalses_manu | documentacion | 3 |
| embalses_manu | fuente procesada | 16 |
| embalses_manu | no relevante | 57 |
| embalses_manu | output de modelo | 12 |
| sddp_previous | cache | 5 |
| sddp_previous | codigo | 2939 |
| sddp_previous | documentacion | 149 |
| sddp_previous | fuente procesada | 63 |
| sddp_previous | no relevante | 1096 |
| sddp_previous | output de modelo | 46 |
| xm_validation | cache | 1 |
| xm_validation | codigo | 11 |
| xm_validation | documentacion | 4 |
| xm_validation | fuente procesada | 9 |

## Archivos prioritarios perfilados

### embalses_manu/README.md
- Filas: no tabular
- Fechas: None a None
- Columnas: 

### embalses_manu/baseindices.parquet
- Filas: 3851
- Fechas: 2013-01-01 a 2026-05-01
- Columnas: Fecha, CodigoEmbalse, Caudal_DESCARGA NO TURBINADA, Caudal_DESCARGA TURBINADA, Caudal_NO IDENTIFICADO, Caudal_VERTIMIENTO, RegionHidrologica, CapacidadUtilMasa, VolumenTotalMasa, VolumenUtilDiarioMasa, VertimientosMasa, VertimientosEnergia, VolumenUtilPorcentaje, VolumenPorcentaje, NivelENFICCProbabilistico, AportesHidricosMasa, oni, mei2, tna, tsa, best, soi, humedad, precipitacion, temperatura ...

### embalses_manu/metricas_modelo.xlsx
- Filas: 3
- Fechas: None a None
- Columnas: Modelo, MAE, RMSE, R2, MAPE, N

### embalses_manu/outputs/escenarios_con_probabilidad.xlsx
- Filas: 60
- Fechas: 2026-06-01 a 2027-05-01
- Columnas: Fecha, Escenario, ONI_forzado, VolumenUtilTotal, Trimestre, Probabilidad

### embalses_manu/outputs/escenarios_nacional.xlsx
- Filas: 60
- Fechas: 2026-06-01 a 2027-05-01
- Columnas: Fecha, Escenario, ONI_forzado, VolumenUtilTotal

### embalses_manu/outputs/escenarios_por_embalse.xlsx
- Filas: 23
- Fechas: None a None
- Columnas: CodigoEmbalse, Neutro, Debil, Moderado, Fuerte, MuyFuerte

### embalses_manu/outputs/metricas_multihorizonte.xlsx
- Filas: 12
- Fechas: None a None
- Columnas: Horizonte, Modelo, MAE, RMSE, R2, MAPE, N

### embalses_manu/outputs/metricas_walkforward.xlsx
- Filas: 15
- Fechas: None a None
- Columnas: AnioValidacion, Modelo, MAE, RMSE, R2, MAPE, N

### embalses_manu/predicciones_multihorizonte.parquet
- Filas: 564
- Fechas: 2020-01-01 a 2025-12-01
- Columnas: Fecha, CodigoEmbalse, CaudalNoTurbinadoPorc_mean, CaudalTurbinadoPorc_mean, CaudalVertimientoPorc_mean, AportesPorc_mean, humedad_mean, precipitacion_mean, temperatura_mean, CapacidadUtilMasa_max, VolumenTotalMasa_max, VolumenUtilDiarioMasa_mean, VolumenUtilDiarioMasa_last, VolumenUtilDiarioMasa_min, VolumenUtilDiarioMasa_max, VolumenUtilPorcentaje_mean, VolumenUtilPorcentaje_last, VolumenUtilPorcentaje_min, VolumenUtilPorcentaje_max, VolumenPorcentaje_mean, VolumenPorcentaje_last, VolumenPorcentaje_min, VolumenPorcentaje_max, VertimientosMasa_sum, VertimientosEnergia_sum ...

### embalses_manu/predicciones_walkforward.parquet
- Filas: 1417
- Fechas: 2021-01-01 a 2025-12-01
- Columnas: Fecha, CodigoEmbalse, CaudalNoTurbinadoPorc_mean, CaudalTurbinadoPorc_mean, CaudalVertimientoPorc_mean, AportesPorc_mean, humedad_mean, precipitacion_mean, temperatura_mean, CapacidadUtilMasa_max, VolumenTotalMasa_max, VolumenUtilDiarioMasa_mean, VolumenUtilDiarioMasa_last, VolumenUtilDiarioMasa_min, VolumenUtilDiarioMasa_max, VolumenUtilPorcentaje_mean, VolumenUtilPorcentaje_last, VolumenUtilPorcentaje_min, VolumenUtilPorcentaje_max, VolumenPorcentaje_mean, VolumenPorcentaje_last, VolumenPorcentaje_min, VolumenPorcentaje_max, VertimientosMasa_sum, VertimientosEnergia_sum ...

### embalses_manu/resultados.parquet
- Filas: 3978
- Fechas: 2013-01-01 a 2027-05-01
- Columnas: Fecha, CodigoEmbalse, CaudalNoTurbinadoPorc_mean, CaudalTurbinadoPorc_mean, CaudalVertimientoPorc_mean, AportesPorc_mean, humedad_mean, precipitacion_mean, temperatura_mean, CapacidadUtilMasa_max, VolumenTotalMasa_max, VolumenUtilDiarioMasa_mean, VolumenUtilDiarioMasa_last, VolumenUtilDiarioMasa_min, VolumenUtilDiarioMasa_max, VolumenUtilPorcentaje_mean, VolumenUtilPorcentaje_last, VolumenUtilPorcentaje_min, VolumenUtilPorcentaje_max, VolumenPorcentaje_mean, VolumenPorcentaje_last, VolumenPorcentaje_min, VolumenPorcentaje_max, VertimientosMasa_sum, VertimientosEnergia_sum ...

### embalses_manu/resultados.xlsx
- Filas: 3978
- Fechas: 2013-01-01 a 2027-05-01
- Columnas: Fecha, CodigoEmbalse, CaudalNoTurbinadoPorc_mean, CaudalTurbinadoPorc_mean, CaudalVertimientoPorc_mean, AportesPorc_mean, humedad_mean, precipitacion_mean, temperatura_mean, CapacidadUtilMasa_max, VolumenTotalMasa_max, VolumenUtilDiarioMasa_mean, VolumenUtilDiarioMasa_last, VolumenUtilDiarioMasa_min, VolumenUtilDiarioMasa_max, VolumenUtilPorcentaje_mean, VolumenUtilPorcentaje_last, VolumenUtilPorcentaje_min, VolumenUtilPorcentaje_max, VolumenPorcentaje_mean, VolumenPorcentaje_last, VolumenPorcentaje_min, VolumenPorcentaje_max, VertimientosMasa_sum, VertimientosEnergia_sum ...

### embalses_manu/resultados_walkforward.xlsx
- Filas: 15
- Fechas: None a None
- Columnas: AnioValidacion, Modelo, MAE, RMSE, R2, MAPE, N

### embalses_manu/validacion_multihorizonte.xlsx
- Filas: 12
- Fechas: None a None
- Columnas: HorizonteMeses, Modelo, MAE, RMSE, R2, MAPE, N

### sddp_previous/README.md
- Filas: no tabular
- Fechas: None a None
- Columnas: 

### sddp_previous/data/aportes_2010_2026.csv
- Filas: 6027
- Fechas: 2010-01-01 a 2026-06-01
- Columnas: Id, Value, Date, es_nino, ma7

### sddp_previous/data/embalses_historico.csv
- Filas: no tabular
- Fechas: None a None
- Columnas: 
- Error de perfilado: EmptyDataError: No columns to parse from file

### sddp_previous/data/generacion_2023_2026.csv
- Filas: 1278
- Fechas: 2023-01-01 a 2026-05-31
- Columnas: Id, Value, Date, es_nino, ma7, hidro_kwh, termo_kwh, hidro_gwh, termo_gwh, hidro_ma30, termo_ma30, apor_ma30

### sddp_previous/data/listado_plantas.csv
- Filas: 2209
- Fechas: 2026-06-03 a 2026-06-03
- Columnas: Id, Values_Code, Values_Name, Values_Type, Values_Disp, Values_RecType, Values_CompanyCode, Values_EnerSource, Values_OperStartdate, Values_State, Date

### sddp_previous/data/precio_bolsa_2010_2026.csv
- Filas: 6026
- Fechas: 2010-01-01 a 2026-05-31
- Columnas: Id, Values_code, Values_Hour01, Values_Hour02, Values_Hour03, Values_Hour04, Values_Hour05, Values_Hour06, Values_Hour07, Values_Hour08, Values_Hour09, Values_Hour10, Values_Hour11, Values_Hour12, Values_Hour13, Values_Hour14, Values_Hour15, Values_Hour16, Values_Hour17, Values_Hour18, Values_Hour19, Values_Hour20, Values_Hour21, Values_Hour22, Values_Hour23 ...

### sddp_previous/data/precio_oferta_historical.csv
- Filas: 353087
- Fechas: 2010-01-01 a 2026-06-30
- Columnas: Id, Values_code, Values_Hour01, Values_Hour02, Values_Hour03, Values_Hour04, Values_Hour05, Values_Hour06, Values_Hour07, Values_Hour08, Values_Hour09, Values_Hour10, Values_Hour11, Values_Hour12, Values_Hour13, Values_Hour14, Values_Hour15, Values_Hour16, Values_Hour17, Values_Hour18, Values_Hour19, Values_Hour20, Values_Hour21, Values_Hour22, Values_Hour23 ...

### sddp_previous/data/sim_nino.npy
- Filas: [10000, 6]
- Fechas: None a None
- Columnas: 

### sddp_previous/data/sim_normal.npy
- Filas: [10000, 6]
- Fechas: None a None
- Columnas: 

### sddp_previous/docs/dispatch_hidrotermico.md
- Filas: no tabular
- Fechas: None a None
- Columnas: 

### xm_validation/README.md
- Filas: no tabular
- Fechas: None a None
- Columnas: 

### xm_validation/config/config.yaml
- Filas: no tabular
- Fechas: None a None
- Columnas: 

### xm_validation/data/catalogos/maestros/ListadoEmbalses.xlsx
- Filas: 30
- Fechas: 2026-06-11 a 2026-06-11
- Columnas: Date, ListEntities

### xm_validation/data/catalogos/maestros/ListadoMetricas.xlsx
- Filas: 193
- Fechas: 2026-06-11 a 2026-06-11
- Columnas: Date, ListEntities

### xm_validation/data/catalogos/maestros/ListadoRecursos.xlsx
- Filas: 2212
- Fechas: 2026-06-11 a 2026-06-11
- Columnas: Date, ListEntities

### xm_validation/data/catalogos/metricas_candidatas_enos.xlsx
- Filas: 157
- Fechas: 2026-06-11 a 2026-06-11
- Columnas: Date, ListEntities

### xm_validation/docs/BACKLOG.md
- Filas: no tabular
- Fechas: None a None
- Columnas: 
