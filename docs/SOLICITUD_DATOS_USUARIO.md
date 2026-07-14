# Solicitud de datos al usuario

| Dato requerido | Columnas requeridas | Periodo | Granularidad | Unidad | Formato aceptado | Razon | Fase bloqueada | Alternativa |
|---|---|---|---|---|---|---|---|---|
| Demanda oficial SIN | fecha, demanda_kwh o demanda_gwh | 2023-actual y prospectivo 26 semanas | horaria o diaria | kWh/GWh | CSV/Parquet/XLSX | Reconstruir balance electrico sin proxy hidro+termica | backtest/prospectivo | metrica XM `DemaReal` ya descargada localmente |
| Generacion por recurso | fecha, codigo_recurso, tipo_recurso, generacion_kwh/gwh | 2023-actual | horaria o diaria | kWh/GWh | CSV/Parquet/XLSX | Validar generacion termica e hidraulica por recurso | backtest/recomendacion | bloques agregados por combustible si conservan energia total |
| Capacidad termica | fecha, codigo_recurso, capacidad_mw | vigente para el horizonte | recurso | MW | CSV/Parquet/XLSX | Limitar energia maxima por periodo | backtest/prospectivo | capacidad efectiva por bloque termico |
| Disponibilidad termica | fecha, codigo_recurso, disponibilidad_mw | historico y 26 semanas futuras | diaria/semanal | MW | CSV/Parquet/XLSX | Evitar recomendar energia no disponible | backtest/prospectivo | escenarios de disponibilidad por bloque |
| Relacion volumen-energia | codigo_embalse, capacidad_util, energia_almacenada_gwh o factor/cota | vigente | embalse | GWh y unidad de volumen | CSV/Parquet/XLSX/documento tecnico | Convertir almacenamiento a balance hidrico energetico | valor del agua/prospectivo | curvas regionales auditadas |
| Aportes hidricos utiles para despacho | fecha, escenario_id, codigo_embalse/sistema, aporte_gwh o caudal convertible | historico y 26 semanas futuras | diaria/semanal/mensual | GWh o caudal con factor | CSV/Parquet/XLSX | Balance hidrico prospectivo exogeno | prospectivo/CVaR | escenarios de energia afluente por sistema |
| Probabilidades de escenarios | fecha, escenario_id, probabilidad | 26 semanas futuras | por escenario | 0-1 | CSV/Parquet/XLSX | CVaR y valor esperado coherentes | prospectivo/CVaR | probabilidades ENOS oficiales por trimestre mapeadas a escenarios |
