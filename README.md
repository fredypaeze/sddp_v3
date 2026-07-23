# Modelo SDDP + CVaR — Despacho hidrotérmico del SIN (MinEnergía Colombia)

Modelo de **optimización estocástica hidro-térmica** para apoyar decisiones operativas del Sistema Interconectado Nacional a 6 meses bajo incertidumbre climática (ENOS):

```
min_x  E[C_op(x,ω)] + λ · CVaR_α[C_crit(x,ω)]
```

Responde: cuándo conservar agua vs. usar térmica, cuál es el costo esperado y el de los peores escenarios, y qué riesgo de déficit existe — con cifras **trazables** a ejecuciones reproducibles.

> Producto **técnico reproducible** (no sistema productivo institucional). Varios insumos térmicos/precios son **supuestos documentados**, no datos oficiales. Ver `docs/LIMITACIONES_v001.md`.

## Instalación

```bash
uv venv .venv --python 3.11
uv pip install --python .venv/bin/python -r requirements.txt -r requirements-model.txt
.venv/bin/python scripts/14_parchear_pydataxm.py --apply         # parche pydataxm freq='M'->'ME'
# descomprimir paquete_datos/transferencia_sddp_v3_20260723.zip y copiar data/ y outputs/ a la raiz
.venv/bin/python -m unittest discover -s tests                    # 143 pruebas
```

## Pipeline

```bash
PYTHONPATH=src .venv/bin/python scripts/20_despacho_deterministico.py   # despacho deterministico
PYTHONPATH=src .venv/bin/python scripts/22_pronostico_aportes.py        # pronostico ENOS
PYTHONPATH=src .venv/bin/python scripts/23_escenarios_aportes.py        # escenarios estocasticos
PYTHONPATH=src .venv/bin/python scripts/24_sddp.py                      # SDDP + politica
PYTHONPATH=src .venv/bin/python scripts/25_cvar_sensibilidad.py         # sensibilidad lambda/alpha
PYTHONPATH=src .venv/bin/python scripts/26_backtesting.py               # backtesting historico
PYTHONPATH=src .venv/bin/python scripts/27_actualizar_incremental.py    # plan de actualizacion
```

Los scripts `01`–`15` (ingesta/validación/consolidación XM) siguen disponibles.

## API y dashboard

```bash
PYTHONPATH=src .venv/bin/uvicorn minenergia_sddp.api.app:app --port 8900    # API (docs en /docs)
PYTHONPATH=src .venv/bin/streamlit run app/dashboard.py --server.port 8901  # dashboard
```

## Resultados destacados

- Pronóstico `sarimax_oni` supera baselines (MAE 35.7 GWh/día); El Niño reduce aportes ~30 %.
- SDDP El Niño: E[costo] ≈ 6.55 B COP (≈ hallazgo histórico 6.36 B), valor del agua ≈ 217 COP/kWh.
- Backtest de estrés: el SDDP evita 2 205 GWh de déficit vs. una regla miope (ahorra 2.38 B COP).

## Documentación

En `docs/`: AUDITORIA_TECNICA_INICIAL · ARQUITECTURA · MODELO_MATEMATICO · FUENTES_DE_DATOS · DICCIONARIO_DE_DATOS · TOPOLOGIA_HIDRAULICA · PRONOSTICO_ENOS · ESCENARIOS_ENOS · SDDP · CVAR · VALIDACION · OPERACION · ACTUALIZACION_DATOS · API · DASHBOARD · LIMITACIONES · REPRODUCIBILIDAD · INFORME_FINAL_TECNICO · INFORME_FINAL_EJECUTIVO · ESTADO_EJECUCION.

Precios eléctricos en **COP/kWh** (nunca COP/MWh); energía en **GWh**.
