# Matriz de metricas XM

La matriz completa reproducible esta en `outputs/run_006/metricas_identificadas.csv`.

| Objetivo | MetricId | Entidad | Periodicidad | Unidad | Estado |
|---|---|---|---|---|---|
| Demanda SIN diaria | `DemaSIN` | Sistema | DailyEntities | kWh | FOUND_EXACT |
| Demanda real sistema horaria | `DemaReal` | Sistema | HourlyEntities | kWh | FOUND_EXACT |
| Generacion real por recurso | `Gene` | Recurso | HourlyEntities | kWh | FOUND_EXACT |
| Generacion real total | `Gene` | Sistema | HourlyEntities | kWh | FOUND_EXACT |
| Listado de recursos | `ListadoRecursos` | Sistema | ListsEntities |  | FOUND_EXACT |
| Capacidad efectiva neta | `CapEfecNeta` | Recurso | DailyEntities | kW | FOUND_EXACT |
| Disponibilidad real | `DispoReal` | Recurso | HourlyEntities | kW | FOUND_EXACT |
| Disponibilidad comercial | `DispoCome` | Recurso | HourlyEntities | kW | FOUND_EXACT |
| Disponibilidad declarada | `DispoDeclarada` | Recurso | HourlyEntities | kWh | FOUND_EXACT |
| Volumen util energia SIN | `VoluUtilDiarEner` | Sistema | DailyEntities | kWh | FOUND_EXACT |
| Volumen util energia embalse | `VoluUtilDiarEner` | Embalse | DailyEntities | kWh | FOUND_EXACT |
| Capacidad util energia SIN | `CapaUtilDiarEner` | Sistema | DailyEntities | kWh | FOUND_EXACT |
| Capacidad util energia embalse | `CapaUtilDiarEner` | Embalse | DailyEntities | kWh | FOUND_EXACT |
| Aportes energia SIN | `AporEner` | Sistema | DailyEntities | kWh | FOUND_EXACT |
| Aportes energia rio | `AporEner` | Rio | DailyEntities | kWh | FOUND_EXACT |
| Importaciones energia | `ImpoEner` | Sistema | HourlyEntities | kWh | FOUND_EXACT |
| Exportaciones energia | `ExpoEner` | Sistema | HourlyEntities | kWh | FOUND_EXACT |
| UPME alto | `EscDemUPMEAlto` | Sistema | MonthlyEntities | kWh | FOUND_EXACT |
| UPME medio | `EscDemUPMEMedio` | Sistema | MonthlyEntities | kWh | FOUND_EXACT |
| UPME bajo | `EscDemUPMEBajo` | Sistema | MonthlyEntities | kWh | FOUND_EXACT |

Nota: `DispoDeclarada` aparece con unidad `kWh` en el catalogo local aunque la descripcion habla de maxima potencia neta. El esquema real debe validarse antes de usarla como capacidad o disponibilidad.

