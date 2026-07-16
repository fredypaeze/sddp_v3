# Politica de overrides de unidades XM

Los overrides de unidades XM son excepciones explicitas para corregir contradicciones demostradas entre el catalogo local y respuestas reales validadas. No modifican archivos fuente externos ni `ListadoMetricas.xlsx`.

## Archivo de configuracion

Los overrides viven en:

```text
config/xm_unit_overrides.json
```

Cada regla debe declarar:

- `target`
- `metric_id`
- `entity`
- `catalog_unit`
- `effective_unit`
- `derived_column`
- `conversion_factor`
- `status`
- `evidence_period`
- `evidence_run`
- `reason`

La coincidencia es exacta por `target + metric_id + entity`. No se permiten reglas globales por unidad.

## Reglas de validacion

El normalizador debe fallar si una regla esta incompleta, duplicada o contradice su conversion:

- `kWh` deriva `Value_GWh` con factor `0.000001`.
- `kW` deriva `Value_MW` con factor `0.001`.
- Una metrica solo debe generar una columna derivada compatible.
- `Value` original siempre debe conservarse.
- `unit_catalog` y `unit_effective` deben coexistir.

## Alcance actual

El unico override aprobado es:

- `target`: `disponibilidad_declarada_recurso`
- `metric_id`: `DispoDeclarada`
- `entity`: `Recurso`
- `catalog_unit`: `kWh`
- `effective_unit`: `kW`
- `derived_column`: `Value_MW`

## Precios

Las metricas de precio mantienen su unidad de catalogo, por ejemplo `COP/kWh`. Esta politica no convierte precios a energia ni potencia.

## Uso operativo

Las descargas futuras deben normalizar respuestas mediante las funciones contextuales del modulo `minenergia_sddp.data.xm_pilot`, no con reglas basadas solo en el texto de `unit`.
