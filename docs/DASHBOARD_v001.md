# Dashboard (v001)

Streamlit en `app/dashboard.py`. Lee `outputs/run_*` (no ejecuta el modelo). Primera versión del tablero (no existía antes; no reemplaza a ninguno).

## Ejecución

```
PYTHONPATH=src .venv/bin/streamlit run app/dashboard.py --server.port 8901
```

## Pestañas

1. **Estado y riesgo**: horizonte, fase ENOS, E[costo], VaR, CVaR, P(ENS), despacho hidro/térmica por etapa, cotas LB/UB y brecha.
2. **Recomendación térmica**: tabla por etapa (generación térmica, valor del agua, volumen esperado, señal) y curva del valor del agua.
3. **Sensibilidad λ/α**: caso base vs. estrés; trade-off costo esperado vs. CVaR.
4. **Pronóstico ENOS**: mejor modelo, MAE, pronóstico a 6 meses, aportes por fase.
5. **Backtesting**: costo realizado por política y episodio.

## Trazabilidad y tooltips

Cada indicador incluye tooltip con definición, unidad y si es **observado / modelado / supuesto**. El pie de página atribuye al **Ministerio de Minas y Energía** y recuerda que las cifras son trazables a `outputs/run_*`.
