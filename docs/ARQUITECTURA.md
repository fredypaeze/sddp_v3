# Arquitectura

El proyecto separa configuracion, auditoria de datos, contratos, validacion, despacho, riesgo y reporte.

- `config/data_sources.json`: unica ubicacion autorizada para rutas externas.
- `data/raw`: reservado para copias auditadas; no se copio ningun insumo original en esta corrida.
- `data/interim` y `data/processed`: salidas intermedias reproducibles.
- `src/minenergia_sddp`: paquete Python compatible con Python 3.11.9.
- `outputs/run_001`: puerta de calidad de datos.
- `outputs/run_002`, `run_003`, `run_004`: reservados para backtest, prospectivo y CVaR si la puerta lo permite.

La primera version no se denomina SDDP completo. La salida objetivo se denomina "Recomendacion de despacho y priorizacion termica".
