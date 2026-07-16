# Dataset Sistema XM v2

`data/processed/xm/system_historical_v2/` es una nueva version del bloque Sistema. No reemplaza `system_historical_v1`.

## Cambios frente a v1

- Agrega `importaciones_status` y `exportaciones_status`.
- Agrega `importaciones_imputed` y `exportaciones_imputed`.
- Conserva ventanas vacias como `UNKNOWN_EMPTY_WINDOW`.
- Incluye `structural_zeros.csv` con la trazabilidad de ceros inferidos.
- Mantiene `Value` original en los archivos `by_target`.

## Model-ready

`system_daily_model_ready.csv` incluye solo dias donde:

- demanda SIN esta reportada;
- generacion esta completa;
- importaciones y exportaciones son reportadas, cero explicito o cero estructural validado;
- no hay `UNKNOWN`;
- el balance puede calcularse.

Los dias con ventanas completas vacias de importaciones se conservan en `system_daily_excluded.csv` con motivo explicito.

## Limitaciones

La politica no demuestra que toda ausencia historica en otros endpoints de XM sea cero. Aplica solo a las dos metricas auditadas y al periodo de evidencia indicado.
