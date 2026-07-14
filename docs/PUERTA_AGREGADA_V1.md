# Puerta A - Modelo agregado V1

Estado: **BLOCKED_AGGREGATE_V1**

## Evaluacion

- Demanda del sistema: `FOUND_METADATA_ONLY`; no hay serie local descargada.
- Generacion termica e hidraulica agregada: `FOUND_WITH_LIMITATIONS`; existe `generacion_2023_2026.csv`.
- Almacenamiento en porcentaje/indice: `FOUND_WITH_LIMITATIONS`; existe `escenarios_con_probabilidad.xlsx`.
- Escenarios prospectivos y probabilidades: `FOUND_VALID`; suman 1 para cada fecha.
- Limites termicos agregados o por bloques: `FOUND_WITH_LIMITATIONS`; existe bloque carbon parcial, no flota termica completa.

## Decision

La V1 agregada queda bloqueada porque no hay demanda oficial descargada ni limite termico agregado de toda la flota. Puede prepararse una version exploratoria de indices/escenarios, pero no una recomendacion agregada de generacion termica.
