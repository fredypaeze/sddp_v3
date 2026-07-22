# Hidrologia energetica agregada del SIN

Este bloque consolida tres series diarias historicas XM ya descargadas localmente para el SIN:

- `aportes_energia_sin` (`AporEner`, `Sistema`)
- `volumen_util_energia_sin` (`VoluUtilDiarEner`, `Sistema`)
- `capacidad_util_energia_sin` (`CapaUtilDiarEner`, `Sistema`)

El periodo objetivo es `2010-01-01` a `2026-07-13`. La consolidacion no realiza solicitudes HTTP, no descarga datos y no modifica los JSON crudos.

## Salidas

El script `scripts/13_consolidar_hidrologia_sin.py` crea una version secuencial en:

- `data/processed/xm/hydro_system_historical_vN`
- `outputs/run_013` o `outputs/run_013_vNNN`

El dataset contiene:

- `hydro_system_daily_all.csv` y `.parquet`
- `hydro_system_daily_model_ready.csv` y `.parquet`
- `hydro_system_daily_excluded.csv` y `.parquet`
- `source_manifest.csv`
- `dataset_manifest.json`
- `data_dictionary.csv`
- `quality_summary.json`
- `capacity_changes.csv`
- `largest_volume_increases.csv`
- `largest_volume_decreases.csv`
- `README.md`

El run registra cobertura, claves, rangos, hashes antes/despues de fuentes, eventos de cambio y comando ejecutado.

## Reglas

Todas las entradas se conservan en kWh y se derivan a GWh con:

```text
Value_GWh = Value / 1.000.000
```

El porcentaje se calcula por fecha:

```text
porcentaje_volumen_util_calculado =
volumen_util_energia_gwh / capacidad_util_energia_gwh * 100
```

No se usa una capacidad fija para la serie. Los cambios diarios se calculan con diferencia contra la observacion inmediatamente anterior dentro del periodo; por eso la primera fecha conserva nulos tecnicos en `cambio_diario_volumen_gwh` y `cambio_diario_capacidad_gwh`.

## Calidad

`quality_status` es:

- `OK`: cobertura y consistencia fisica basica validas.
- `WARNING`: reservado para situaciones expresamente definidas que no bloqueen uso.
- `ERROR`: falta informacion o se incumple una regla bloqueante.

`model_ready=True` exige aportes, volumen, capacidad, porcentaje, fecha valida, union uno a uno y reglas fisicas basicas. Los nulos tecnicos de la primera diferencia diaria no bloquean `model_ready`.

Los cambios grandes de volumen o capacidad se reportan y ordenan, pero no se clasifican automaticamente como advertencias ni errores.
