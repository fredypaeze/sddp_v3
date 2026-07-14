# Plan de extraccion XM

Este paquete prepara la descarga futura de datos XM sin ejecutarla. La descarga real queda bloqueada por defecto y requiere `--execute`.

## Fuentes locales usadas

- `D:/Proyectos/minenergia/xm_validation-main/data/catalogos/maestros/ListadoMetricas.xlsx`
- `D:/Proyectos/minenergia/xm_validation-main/data/catalogos/maestros/ListadoRecursos.xlsx`
- `D:/Proyectos/minenergia/xm_validation-main/data/catalogos/maestros/ListadoEmbalses.xlsx`
- `D:/Proyectos/minenergia/xm_validation-main/data/catalogos/maestros/ListadoRios.xlsx`

## Alcance

- Historico hidrologico: `2010-01-01` a fecha final indicada en ejecucion.
- Demanda, generacion, capacidad y disponibilidad: `2023-01-01` a fecha final indicada.
- Dry-run generado con fecha final de planificacion `2026-07-13`.

## Reglas

- Solo HTTPS.
- Sin credenciales.
- Lotes maximos de 30 dias para metricas horarias y diarias.
- Filtros por recurso, embalse y rio en lotes de hasta 10 entidades.
- Checkpoints por directorio de salida.
- No se marca un lote como completo si la respuesta esta vacia.
- Cada lote se guarda inmediatamente como JSON versionado.
- Energia se conserva en kWh y se deriva a GWh en consolidacion posterior.
- Potencia se conserva en kW o MW segun catalogo; `CapEfecNeta`, `DispoReal` y `DispoCome` vienen en kW.
- Precios se preservan en COP/kWh; no se acepta COP/MWh.

## pydataxm

En el entorno actual `pydataxm` no esta instalado. Se documenta el problema conocido de `pydataxm 0.3.17` con `freq='M'` y `pandas >= 2.2`; este paquete no modifica el entorno ni aplica parches automaticamente.

