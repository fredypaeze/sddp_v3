# Diccionario dataset sistema XM

| Dataset | Columna | Descripcion |
| --- | --- | --- |
| system_hourly | fecha | Fecha reportada por XM. |
| system_hourly | hora_xm | Etiqueta horaria original `Hour01` a `Hour24`. |
| system_hourly | timestamp | Timestamp naive construido como fecha + hora_xm - 1. |
| system_hourly | demanda_real_gwh | Demanda real horaria en GWh. |
| system_hourly | generacion_total_gwh | Generacion total horaria en GWh. |
| system_hourly | importaciones_gwh | Importaciones horarias en GWh; `NaN` si no hay valor reportado. |
| system_hourly | exportaciones_gwh | Exportaciones horarias en GWh. |
| system_hourly | generacion_neta_intercambios_gwh | Generacion + importaciones - exportaciones, solo con tres variables reportadas. |
| system_hourly | *_reportada | Indica si la variable fue observada en la fuente XM. |
| system_daily_all | demanda_sin_gwh | Demanda SIN diaria en GWh. |
| system_daily_all | horas_* | Conteo de horas reportadas por variable horaria. |
| system_daily_all | *_completa | Indica cobertura diaria suficiente. |
| system_daily_all | diferencia_demareal_demasin_gwh | Demanda real agregada menos DemaSIN. |
| system_daily_all | diferencia_balance_gwh | Generacion neta de intercambios menos DemaSIN. |
| system_daily_model_ready | todas | Subconjunto de dias con datos suficientes para modelamiento. |
| system_daily_excluded | motivo_exclusion | Razon por la cual el dia no entra al dataset model-ready. |
