# Validacion del bloque historico XM Sistema

La validacion historica de los cinco targets de sistema se ejecuta con:

```powershell
python scripts/09_validar_descargas_xm2.py `
  --target demanda_real_sistema_horaria `
  --target demanda_sin_diaria `
  --target generacion_real_total `
  --target importaciones_energia_sistema `
  --target exportaciones_energia_sistema `
  --start-date 2023-01-01 `
  --end-date 2026-07-13 `
  --run-dir outputs/run_010
```

El script no hace solicitudes HTTP, no descarga datos y no consolida datasets. Lee unicamente JSON crudos historicos ubicados en los dominios autorizados de `data/raw/xm` y excluye los pilotos.

## Targets autorizados

- `demanda_real_sistema_horaria`
- `demanda_sin_diaria`
- `generacion_real_total`
- `importaciones_energia_sistema`
- `exportaciones_energia_sistema`

## Validaciones

El validador comprueba legibilidad, JSON valido, respuesta no vacia, `Metric.Id`, entidad `Sistema`, esquema esperado, SHA-256, fechas, duplicados, nulos, negativos, granularidad, cobertura de ventanas y errores de checkpoint.

Las unidades se validan con `config/xm_metrics.json`, `config/xm_unit_overrides.json` y el normalizador contextual del proyecto. Para estas metricas energeticas, la columna esperada en memoria es:

```text
Value_GWh = Value / 1.000.000
```

## Balance preliminar

El balance diario compara `DemaSIN`, `DemaReal` agregada desde horas, `Gene`, `ImpoEner` y `ExpoEner`. Es diagnostico: no fuerza igualdad fisica porque las definiciones pueden incluir perdidas, generacion no cubierta y otros componentes.

## Estados

- `HISTORICAL_BLOCK_VALIDATED`: cobertura, esquemas y unidades utilizables.
- `HISTORICAL_BLOCK_VALIDATED_WITH_WARNINGS`: datos utilizables con advertencias no bloqueantes.
- `HISTORICAL_BLOCK_BLOCKED`: faltan ventanas, hay errores de esquema o inconsistencias bloqueantes.
