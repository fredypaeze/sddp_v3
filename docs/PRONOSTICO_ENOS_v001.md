# Pronóstico hidrológico condicionado a ENOS (v001)

Pronóstico mensual de **aportes del SIN** (GWh/día) para el horizonte operativo (6 meses), condicionado al índice ONI (El Niño–Oscilación del Sur).

- Código: `src/minenergia_sddp/forecasting/aportes.py`
- ONI: `data/reference/oni_noaa.csv` (NOAA CPC, descargado 2026-07-23; ver `data/reference/README.md`)
- Ejecución: `PYTHONPATH=src python scripts/22_pronostico_aportes.py` → `outputs/run_022_v001/`

## Señal ENOS (validada con datos, 2010–2026)

Aportes medios diarios por fase: **neutral 186.8 · La Niña 180.9 · El Niño 131.4 GWh/día**. El Niño reduce los aportes ~30 % — señal física fuerte que justifica condicionar el modelo a ENOS.

## Modelos comparados

- **Baselines:** climatología mensual, persistencia estacional (valor de hace 12 meses).
- **SARIMAX** `(1,0,0)(0,1,1)_12` sin exógena.
- **SARIMAX + ONI** (exógena = ONI del mes objetivo).

## Backtesting (origen móvil, sin fuga temporal)

Selección por MAE sobre múltiples orígenes (min_train=72, paso 3, horizonte 6):

| Modelo | MAE | RMSE | sesgo | sMAPE |
|---|---|---|---|---|
| **sarimax_oni** | **35.7** | 49.1 | −17.3 | 0.200 |
| sarimax | 38.6 | 52.0 | −18.1 | 0.217 |
| climatología | 42.8 | 57.5 | −26.6 | 0.245 |
| persistencia_estacional | 53.0 | 69.1 | −30.6 | 0.306 |

El SARIMAX+ONI **supera a todos los baselines**, con mayor ventaja a horizontes largos (h6: 41.2 vs 46.3 de climatología). Las métricas se reportan también por horizonte y por fase ENOS (`metricas_por_horizonte.csv`, `metricas_por_fase.csv`).

## Pronóstico vigente (ejemplo run_022_v001)

Mejor modelo **sarimax_oni**; los próximos 6 meses (Ago 2026–Ene 2027) caen en fase **El Niño** con aportes por debajo de lo normal.

## Limitaciones (honestidad)

- El **ONI futuro** más allá del último dato observado se mantiene constante (último valor). Un pronóstico operativo debería usar el ONI proyectado del CPC/IRI.
- Objetivo agregado del SIN (no por embalse/región): consistente con la disponibilidad de aportes (ver auditoría §5).
- Sin fuga temporal: cada origen se ajusta solo con datos previos.

## Uso aguas abajo

Este pronóstico y su condicionamiento ENOS alimentan la **generación de escenarios** (ETAPA 6) y el **SDDP** (ETAPA 7): la media y la dispersión de aportes por fase determinan los árboles de escenarios y el valor del agua.
