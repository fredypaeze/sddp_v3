# Instrucciones de ejecucion de descarga XM

## Preparar plan

```powershell
python scripts/07_preparar_descarga_xm.py
```

## Dry-run sin solicitudes

```powershell
python scripts/08_descargar_xm_controlado.py --dry-run
```

Con filtros:

```powershell
python scripts/08_descargar_xm_controlado.py --dry-run --metric Gene --start-date 2023-01-01 --end-date 2023-01-30 --max-resources 10
```

## Comando que ejecutaria descargas

No ejecutar sin autorizacion explicita.

```powershell
python scripts/08_descargar_xm_controlado.py --execute --resume --start-date 2023-01-01 --end-date 2026-07-13
```

## Validar descargas

```powershell
python scripts/09_validar_descargas_xm.py
```

## Consolidar

```powershell
python scripts/10_consolidar_xm.py
```

La consolidacion permanece conservadora hasta observar esquemas reales de respuesta por metrica.

