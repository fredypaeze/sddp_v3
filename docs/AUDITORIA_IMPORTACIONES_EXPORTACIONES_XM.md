# Auditoria de importaciones y exportaciones XM

Auditoria local del periodo `2023-01-01` a `2026-07-13`, usando exclusivamente JSON crudos existentes de:

- `data/raw/xm/intercambios/importaciones_energia_sistema/`
- `data/raw/xm/intercambios/exportaciones_energia_sistema/`

Tambien se usan como referencia demanda real, demanda SIN, generacion total, `outputs/run_010_v002` y `outputs/run_011`. No se realizan solicitudes HTTP.

## Evidencia evaluada

La estructura auditada diferencia tres casos:

- Ventanas no vacias con `Items` y matriz `Hour01` a `Hour24`.
- Horas con cadena vacia dentro de esa matriz.
- Ventanas completas con `Items: []`.

Las horas vacias dentro de respuestas no vacias se tratan separadamente de las ventanas completas vacias. Estas ultimas conservan incertidumbre.

## Comparacion de politicas

La auditoria calcula tres variantes:

- `STRICT_OBSERVED_ONLY`: solo valores numericos explicitos.
- `CANDIDATE_STRUCTURAL_ZERO`: aplica cero estructural solo bajo la regla validada.
- `UNSAFE_ALL_MISSING_ZERO`: escenario diagnostico que convierte todo faltante en cero; esta prohibido para produccion.

El buen cierre de balance no se usa como unica prueba; se combina con estructura de respuesta, presencia de valores positivos, ceros explicitos y ausencia de errores.
