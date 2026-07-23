# Arquitectura (v001)

Capas del producto (de datos a decisión), sobre el paquete `minenergia_sddp`.

```
config/                         parametros del modelo, topologia, fuentes, plan XM
data/raw|interim|processed      insumos XM + datasets model-ready (GWh)
data/reference/                 ONI NOAA (referencia versionada)

src/minenergia_sddp/
  config/        rutas y portabilidad de fuentes externas
  data/          ingesta/validacion XM + actualizacion incremental
  validation/    contratos, unidades, disponibilidad
  dispatch/      datos alineados por etapa + despacho deterministico (LP)
  forecasting/   pronostico de aportes condicionado a ENOS (SARIMAX+ONI)
  scenarios/     escenarios estocasticos (PAR/ARX(1)) + reduccion + validacion
  optimization/  helper LP (HiGHS), construccion de horizonte, SDDP+CVaR
  risk/          CVaR empirico (VaR/CVaR)
  topology/      catalogo de embalses y cadenas
  reporting/     carpetas reproducibles + recomendacion operativa
  api/           API REST (FastAPI) de resultados

scripts/         20 despacho · 22 pronostico · 23 escenarios · 24 SDDP ·
                 25 CVaR · 26 backtesting · 27 actualizacion
app/dashboard.py Streamlit (lectura de outputs)
outputs/run_XXX_vYYY/  ejecuciones reproducibles (config, commit, hashes, resultados)
tests/           136+ pruebas
```

## Flujo

1. **Datos** (XM) → validacion/consolidacion → `*_model_ready.csv` (GWh, COP/kWh).
2. **Pronostico** de aportes condicionado a ONI (backtesting temporal).
3. **Escenarios** estocasticos de aportes (PAR/ARX(1)+ONI), validados vs. historia.
4. **Optimizacion**: despacho deterministico (validacion) y **SDDP+CVaR** (política).
5. **Riesgo**: E[costo], VaR, CVaR; sensibilidad λ/α.
6. **Backtesting** sobre episodios ENOS.
7. **Entrega**: API + dashboard + informes; cada cifra trazable a `outputs/run_*`.

## Principios

- Compatibilidad con la estructura existente (`minenergia_sddp`); no se reorganiza el repo.
- Unidades consistentes: energia en GWh, precios en COP/kWh (nunca COP/MWh).
- Supuestos config-driven, marcados y con sensibilidad; nunca presentados como dato oficial.
- Reproducibilidad: semillas, hashes de insumos, commit y entorno por ejecucion.
