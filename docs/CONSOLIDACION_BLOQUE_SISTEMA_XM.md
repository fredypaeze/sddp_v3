# Consolidacion bloque sistema XM

Este documento describe la consolidacion local del bloque historico XM de Sistema para el periodo 2023-01-01 a 2026-07-13.

## Fuentes

Se usan exclusivamente JSON crudos ya descargados en `data/raw/xm` para cinco targets:

- `demanda_real_sistema_horaria`
- `demanda_sin_diaria`
- `generacion_real_total`
- `importaciones_energia_sistema`
- `exportaciones_energia_sistema`

No se hacen solicitudes HTTP y no se modifican los JSON crudos.

## Granularidad y unidades

Las metricas horarias conservan `Date`, `Hour` y `code`. La metrica diaria `DemaSIN` conserva `Date` y `code`. Todas las unidades catalogo y efectivas son `kWh`; la columna consolidada `Value_GWh` se calcula como:

```text
Value_GWh = Value / 1.000.000
```

## Timestamp

`Hour01` se representa como la primera hora del dia y se convierte a `timestamp` naive como fecha 00:00. `Hour24` se convierte a fecha 23:00. No se aplica zona horaria ni desplazamiento adicional porque no hay evidencia suficiente para alterar la convencion horaria XM.

## Faltantes e importaciones vacias

Las ventanas de importaciones con `Items: []` se clasifican como `NO_REPORTED_VALUES`. No se imputan como cero. En `system_hourly.csv` y `system_daily_all.csv` esos valores quedan como `NaN`, los flags de reporte quedan en `false` y los dias afectados se excluyen de `system_daily_model_ready.csv`.

## Balance

El balance diagnostico se calcula como:

```text
generacion_neta_intercambios_gwh = generacion_total_gwh + importaciones_gwh - exportaciones_gwh
```

Las diferencias frente a demanda se calculan solo cuando las variables requeridas estan reportadas. No se exige que el balance cierre exactamente en cero porque las definiciones pueden incluir perdidas, generacion no cubierta u otros componentes.

## Datasets

- `system_hourly.csv`: serie horaria integrada.
- `system_daily_all.csv`: agregacion diaria completa, con dias incompletos marcados.
- `system_daily_model_ready.csv`: solo dias con demanda SIN, generacion, importaciones, exportaciones y balance calculable.
- `system_daily_excluded.csv`: dias excluidos y motivo.

## Limitaciones

El bloque queda listo para integracion posterior con hidrologia y recursos, pero aun no incorpora disponibilidad, embalses ni aportes. Las ventanas sin importaciones reportadas no prueban importaciones cero.
