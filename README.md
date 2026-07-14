# Modelo multiperiodo de despacho hidrotermico bajo escenarios ENOS

Base tecnica para una futura **Recomendacion de despacho y priorizacion termica**.

Estado actual de puerta de calidad: **BLOCKED_CRITICAL_DATA**.

La version actual organiza fuentes, contratos, trazabilidad, matriz de unidades, brechas y validaciones. No construye un SDDP completo ni un Unit Commitment.

## Ejecucion

```powershell
python scripts/01_auditar_fuentes.py
python scripts/02_preparar_datos.py
python -m unittest discover -s tests
```

Los scripts `03` a `05` verifican la puerta de calidad y se bloquean si los datos criticos siguen ausentes.
