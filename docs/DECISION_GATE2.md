# Decision gate 2

## Estados

- Puerta agregada V1: **BLOCKED_AGGREGATE_V1**
- Puerta por recurso V2: **BLOCKED_RESOURCE_LEVEL_V2**

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
