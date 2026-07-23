# Actualización de datos (v001)

Proceso **incremental** (no tiempo real: XM tiene rezago). Código: `src/minenergia_sddp/data/incremental.py`; ejecución: `scripts/27_actualizar_incremental.py` → `outputs/run_027_v001/`.

## Qué hace

1. Detecta la **última fecha disponible** localmente (sistema e hidrología).
2. Calcula las **ventanas faltantes** hasta la fecha objetivo, en bloques ≤ 60 días (2 meses) para evitar timeouts de XM.
3. Produce un plan y un informe; **no sobrescribe** el histórico (versionamiento).

Estado actual: última fecha local **2026-07-13**; a 2026-07-23 faltan **10 días** (ventana `2026-07-14 … 2026-07-23`).

## Terminología correcta

- **Actualización programada / incremental / con rezago** — nunca “tiempo real”.
- Se reporta siempre la última fecha disponible y el estado de conexión.

## Ejecución de la descarga (bloqueo actual)

```
BLOQUEO:
DECISIÓN O RECURSO NECESARIO: catálogo maestro externo de XM (ListadoMetricas.xlsx) y acceso de red a la API de XM.
POR QUÉ ES NECESARIO: `build_metric_definitions` lee el catálogo para armar las solicitudes; sin él no se puede planificar la llamada real.
QUÉ INTENTASTE: portabilizar `data_sources.json` (env SDDP_EXTERNAL_SOURCES_ROOT) y planificar las ventanas; el plan queda listo.
IMPACTO SI NO SE RESUELVE: no se pueden traer datos nuevos; el modelo corre con datos hasta 2026-07-13.
INSTRUCCIÓN EXACTA QUE DEBE EJECUTAR EL USUARIO: montar `xm_validation-main/data/catalogos/maestros/` en el servidor y exportar `SDDP_EXTERNAL_SOURCES_ROOT`, con red a servapibi.xm.com.co; luego `python scripts/08_descargar_xm_controlado.py` (execute) y los consolidadores 10/13/15.
ALTERNATIVA TEMPORAL: operar con el histórico incluido (2010–2026-07-13), suficiente para el horizonte y el backtesting.
```

Cuando las fuentes estén montadas, la descarga usa reintentos controlados, guarda cada bloque antes de continuar, registra rangos fallidos y no repite descargas exitosas (scripts 08–15 existentes).
