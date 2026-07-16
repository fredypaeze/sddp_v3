# Repeticion externa del piloto XM run_008

Este documento describe el reintento seguro del piloto XM para el periodo fijo
2026-06-01 a 2026-06-07. La version operativa es:

```powershell
python scripts/11_ejecutar_piloto_xm2.py --execute --retry-network-errors --resume --max-http-requests 100
```

La ejecucion debe hacerse desde PowerShell normal, fuera del sandbox que bloqueo
sockets con `WinError 10013`. No debe iniciarse la descarga historica completa.

## Destinos

- Datos nuevos: `data/raw/xm/pilot_20260601_20260607_retry1/`
- Reportes nuevos: `outputs/run_008/`
- Evidencia original preservada: `outputs/run_007/` y
  `data/raw/xm/pilot_20260601_20260607/`

## Seguridad

- Sin `--execute`, el script no construye el cliente HTTP ni abre sockets.
- `--dry-run` registra y muestra el plan sin solicitudes.
- `--retry-network-errors` ignora solo errores previos clasificados como bloqueo
  de red o socket local, incluyendo `WinError 10013`.
- Lotes completados en `run_007` o `retry1` se omiten y no se repiten.
- El limite efectivo de solicitudes es `min(100, --max-http-requests)`.

Antes de ejecutar, revisar el dry-run:

```powershell
python scripts/11_ejecutar_piloto_xm2.py --dry-run --retry-network-errors --max-http-requests 100
```
