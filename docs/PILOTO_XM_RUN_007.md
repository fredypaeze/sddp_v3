# Piloto XM run_007

Periodo autorizado: `2026-06-01` a `2026-06-07`.

Estado: `PILOT_BLOCKED_NETWORK`.

El cliente intento ejecutar el piloto contra endpoints HTTPS oficiales de XM, pero el sandbox bloqueo la apertura de sockets con `WinError 10013`. Se detuvo la adquisicion, se registraron errores por metrica y no se marcaron lotes como completados.

No se recibieron respuestas validas, por lo que no fue posible validar esquemas reales, unidades efectivas, balance electrico, hidrologia ni `DispoDeclarada`.

Artefactos:

- `outputs/run_007/resumen_piloto.json`
- `outputs/run_007/metricas_piloto.csv`
- `outputs/run_007/errores_piloto.csv`
- `outputs/run_007/conclusion_piloto.md`
- `data/raw/xm/pilot_20260601_20260607/*/_checkpoint.json`

La descarga historica completa no debe autorizarse desde este sandbox hasta ejecutar un piloto exitoso en un entorno con salida HTTPS permitida hacia XM.
