# API de resultados (v001)

FastAPI en `src/minenergia_sddp/api/app.py`. Sirve, en solo lectura, los artefactos reproducibles de `outputs/run_*`. No ejecuta el modelo.

## Ejecución

```
PYTHONPATH=src .venv/bin/uvicorn minenergia_sddp.api.app:app --host 127.0.0.1 --port 8900
```

Docs interactivas en `/docs` (Swagger).

## Endpoints

| Método | Ruta | Devuelve |
|---|---|---|
| GET | `/estado` | Estado del servicio, última fecha de datos, runs disponibles |
| GET | `/ultima_actualizacion` | Última fecha de datos y tipo (rezago) |
| GET | `/resultados` | Resumen de la política SDDP (run_024) |
| GET | `/riesgo` | E[costo], VaR, CVaR, α, P(ENS) |
| GET | `/recomendacion` | Recomendación térmica por etapa |
| GET | `/generacion` | Despacho hidro/térmico por etapa |
| GET | `/sensibilidad/lambda` | Trade-off costo–riesgo al variar λ |
| GET | `/sensibilidad/alpha` | CVaR al variar α |
| GET | `/escenarios` | Parámetros del modelo de escenarios |
| GET | `/pronostico` | Pronóstico de aportes a 6 meses |
| GET | `/backtesting` | Comparación de políticas por episodio |
| GET | `/embalses` | Catálogo de los 24 embalses |

Si un resultado aún no fue calculado, el endpoint responde **404** indicando qué script ejecutar. Probado con `fastapi.testclient` (`tests/test_infra.py`).
