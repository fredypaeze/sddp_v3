# Hidrología energética diaria por embalse

## 1. Propósito

El bloque consolida tres métricas oficiales de XM por pareja fecha–embalse:

- `VoluUtilDiarEner`: volumen útil energético.
- `CapaUtilDiarEner`: capacidad útil energética.
- `PorcVoluUtilDiar`: porcentaje de volumen útil oficial.

El periodo inicial validado es 2010-01-01 a 2026-07-13. Los JSON descargados se mantienen inmutables y el consolidado se escribe en una ruta versionada.

## 2. Interpretación de unidades

Las métricas energéticas llegan en kWh y se convierten a GWh mediante:

`GWh = kWh / 1.000.000`

Aunque el catálogo de XM registra `%`, `PorcVoluUtilDiar` llega como fracción decimal. La normalización aplicada es:

`porcentaje_volumen_util_oficial = valor_crudo_XM * 100`

La auditoría cruzada confirmó que el porcentaje oficial reproduce prácticamente:

`volumen_util_energia / capacidad_util_energia * 100`

En 135.467 pares comparables, la diferencia absoluta máxima observada fue 0,0005 puntos porcentuales.

## 3. Política de calidad

El dataset preserva los valores publicados por XM. No se recortan valores a 0 % o 100 % y no se reemplazan anomalías.

Condiciones bloqueantes para `model_ready`:

- métricas requeridas incompletas;
- volumen útil negativo;
- porcentaje oficial negativo;
- capacidad no positiva.

Condiciones no bloqueantes:

- volumen útil mayor que capacidad útil;
- porcentaje oficial o calculado superior a 100 %.

Estas últimas se conservan con:

`INCONSISTENCIA_RELACION_VOLUMEN_CAPACIDAD`

La entidad `FLORIDA II` permanece registrada como activa en el catálogo, pero sin reporte de las tres métricas:

`ENTIDAD_CATALOGO_SIN_REPORTE_METRICA`

## 4. Conteos esperados del periodo validado

- Archivos JSON canónicos: 606 por métrica.
- Volumen: 135.467 registros.
- Capacidad: 135.957 registros.
- Porcentaje oficial: 135.467 registros.
- Unión fecha–embalse: 135.957 filas.
- Embalses observados: 24 de 25.
- Filas incompletas: 490.
- Filas negativas: 4.
- Filas `model_ready`: 135.463.
- Filas excluidas: 494.
- Porcentajes oficiales superiores a 100 %: 7.290.
- Relaciones volumen mayor que capacidad: 7.342.

Los conteos exactos se controlan cuando se ejecuta el periodo predeterminado. Para otros periodos se reportan como información, no como expectativa fija.

## 5. Archivos generados

Dataset:

- `hydro_reservoir_daily_all.csv/.parquet`
- `hydro_reservoir_daily_model_ready.csv/.parquet`
- `hydro_reservoir_daily_excluded.csv/.parquet`
- `reservoir_coverage.csv`
- `catalog_entities_without_data.csv`
- `missing_metric_pairs.csv`
- `percentage_inconsistencies.csv`
- `capacity_changes.csv`
- `largest_volume_increases.csv`
- `largest_volume_decreases.csv`
- `source_manifest.csv`
- `data_dictionary.csv`
- `quality_summary.json`
- `dataset_manifest.json`

Evidencia de ejecución:

- `resumen_consolidacion_hidrologia_embalse.json`
- `validacion_cobertura_fuentes.csv`
- `validacion_cobertura_embalses.csv`
- `validacion_claves.csv`
- `validacion_controles.csv`
- `errores.csv`
- `advertencias.csv`
- `hashes_fuentes_antes.csv`
- `hashes_fuentes_despues.csv`
- `comando_ejecutado.txt`

## 6. Ejecución

Inspección sin escritura:

```powershell
.\.venv\Scripts\python.exe .\scripts\15_consolidar_hidrologia_embalse.py --dry-run
```

Consolidación versionada:

```powershell
.\.venv\Scripts\python.exe .\scripts\15_consolidar_hidrologia_embalse.py --execute
```

El script nunca sobrescribe un dataset ni un directorio de evidencia existente. Si la versión base ya existe, calcula la siguiente versión disponible.
