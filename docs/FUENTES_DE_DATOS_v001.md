# Fuentes de datos (v001)

| Fuente | Uso | Cobertura | Unidad | Estado |
|---|---|---|---|---|
| XM — `demanda_sin_diaria` | Demanda del SIN | 2023-01 → 2026-07 | GWh | oficial |
| XM — `generacion_real_total` | Generación total | 2023-01 → 2026-07 | GWh (kWh origen) | oficial |
| XM — `aportes_energia_sin` | Aportes hídricos (energía) | 2010-01 → 2026-07 | GWh | oficial |
| XM — `volumen/capacidad_util_energia` (SIN y 24 embalses) | Estado del embalse | 2010-01 → 2026-07 | GWh | oficial |
| XM — import/export, %volumen | Balance/validación | 2023-01 → 2026-07 | GWh, % | oficial |
| NOAA CPC — ONI | Condicionamiento ENOS | 2009 → 2026 | °C anomalía | referencia (`data/reference/oni_noaa.csv`) |
| Piloto por recurso (carbón) | Diagnóstico térmico | 2026-06 (7 días) | MW/GWh | parcial |

## Trazabilidad

- Los datasets model-ready conservan `source_file` y `source_sha256` por registro.
- El paquete de transferencia trae `MANIFEST_SHA256` (3079 archivos, **verificado íntegro**).
- Precio de bolsa se maneja en **COP/kWh** (nunca COP/MWh).

## Brechas (ver auditoría §5)

Generación por tecnología clasificada, capacidad/disponibilidad térmica MW de la flota, precios de oferta históricos, aportes por embalse, demanda proyectada oficial. Cubiertas con **supuestos config-driven** marcados (no oficiales) y análisis de sensibilidad.

## Catálogos maestros externos

`ListadoMetricas.xlsx` / `ListadoRecursos.xlsx` viven fuera del repo (`config/data_sources.json` → equipo de origen). En un servidor limpio no están montados; se puede fijar `SDDP_EXTERNAL_SOURCES_ROOT` para montarlos. Sin ellos, la adquisición nueva de XM queda planificada pero no ejecutable (ver `docs/ACTUALIZACION_DATOS_v001.md`).
