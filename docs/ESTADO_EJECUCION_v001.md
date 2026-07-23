# Estado de ejecución — finalización SDDP + CVaR (v001)

Rama: `trabajo/finalizacion-sddp-cvar-v1` · Servidor: `tuxilo-server` · Python 3.11.15

| Etapa | Estado | Notas |
|---|---|---|
| E0 · Entorno + verificación | ✅ Completada | ZIP SHA-256 OK; manifiesto 3079/3079; venv 3.11; parche pydataxm; base de pruebas 96/103 |
| E1 · Auditoría técnica inicial | ✅ Completada | `docs/AUDITORIA_TECNICA_INICIAL_v001.md` |
| E2 · Catálogo/validación de datos | ⏳ En curso | Diccionario + portabilidad `data_sources.json` + validación de balances |
| E3 · Determinístico hidro-térmico | ⬜ Pendiente | LP HiGHS, embalse-equivalente |
| E4 · Topología hidráulica | ⬜ Pendiente | 24 embalses |
| E5 · Pronóstico ENOS | ⬜ Pendiente | baselines → SARIMAX/ML |
| E6 · Escenarios estocásticos | ⬜ Pendiente | aportes/demanda |
| E7 · SDDP formal | ⬜ Pendiente | forward/backward, cortes |
| E8 · CVaR integrado | ⬜ Pendiente | λ, α |
| E9 · Backtesting + sensibilidad | ⬜ Pendiente | episodios ENOS |
| E10 · API + dashboard | ⬜ Pendiente | trazabilidad |
| E11 · Actualización incremental | ⬜ Pendiente | XM por fecha |
| E12 · Documentación + entrega | ⬜ Pendiente | informes + push |

## Línea base de pruebas
- 103 pruebas · 96 OK · 7 no-OK (rutas externas Windows en `data_sources.json`; portabilidad, no lógica).

## Decisiones de diseño registradas
- **Granularidad del SDDP:** embalse-equivalente **agregado** del SIN. Justificación: los aportes (inflows) solo existen a nivel SIN agregado; el nivel por embalse tiene volumen/capacidad pero no aportes. Se documentará y, de ser viable, se probará agrupación por regiones.
- **Split hidro/térmico:** **endógeno** (lo decide el optimizador para cubrir demanda con el agua disponible). No se dispone del split observado por tecnología.
- **Supuestos config-driven** para costo/capacidad térmica y precios (brechas de datos), marcados y con análisis de sensibilidad.

## Bloqueos
- Ninguno que impida avanzar. Brechas de datos se cubren con supuestos documentados (autorizado por el alcance).

## Siguiente acción
- E2: diccionario de datos, validación de balances físicos, y portabilidad de `data_sources.json` (skip condicionado de tests dependientes de catálogos externos).
