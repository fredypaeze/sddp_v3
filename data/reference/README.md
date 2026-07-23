# Datos de referencia

## oni_noaa.csv
Oceanic Niño Index (ONI) mensual, columna `oni` = anomalía SST 3.4 (media móvil trimestral centrada en `mes`).
- Fuente: NOAA CPC — https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt
- Descargado: 2026-07-23. Valores 2026 recientes son preliminares.
- `fase_enos`: nino (ONI>=+0.5), nina (ONI<=-0.5), neutral (intermedio). Umbral simple por mes (no aplica la regla oficial de 5 trimestres consecutivos).
