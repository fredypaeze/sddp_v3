# Auditoría técnica inicial — SDDP + CVaR (v001)

- Proyecto: Modelo SDDP + CVaR — Ministerio de Minas y Energía de Colombia
- Repositorio: https://github.com/fredypaeze/sddp_v3
- Rama base auditada: `trabajo/modelo-hidrotermico-v3` · commit `2f576c7`
- Rama de finalización: `trabajo/finalizacion-sddp-cvar-v1`
- Servidor: `tuxilo-server` (Ubuntu 24.04, Xeon SapphireRapids 4 vCPU, 7.7 GB RAM, sin GPU)
- Entorno: Python 3.11.15 (venv `.venv`, `uv`), dependencias `requirements.txt` + `pip check` limpio
- Paquete de datos: `transferencia_sddp_v3_20260723.zip` — SHA-256 **verificado**; manifiesto **3079/3079 OK**
- Fecha auditoría: 2026-07-23

> **Nota de honestidad (marco general).** El prompt de la tarea listaba como "ya construidos" varios componentes (modelo de balance hidro-térmico, Monte Carlo, cálculo de CVaR, dashboard MVP). La revisión directa del código muestra que **la mayoría de esos componentes no existen en el repositorio**: lo construido es una **base de ingeniería de datos con puertas de calidad**, más **una función utilitaria de CVaR ex-post**. Esta auditoría documenta el estado real, no el aspiracional.

---

## 1. Arquitectura actual

El repositorio implementa un **pipeline de datos XM con trazabilidad y puertas de calidad**, no un motor de optimización. Capas presentes:

```
config/*.json  ── rutas externas, plan de descarga, métricas, políticas de unidades/faltantes
   │
scripts/01..15 ── auditar fuentes → preparar → puertas → descarga controlada XM →
   │               validar → consolidar (sistema, hidrología SIN, hidrología embalse)
src/minenergia_sddp/
   ├─ config/paths.py        rutas del proyecto y fuentes externas (data_sources.json)
   ├─ data/                  catálogo XM, cliente pydataxm, checkpoints, piloto, validación
   ├─ validation/            contratos, chequeos, unidades, disponibilidad
   ├─ risk/cvar.py           CVaR empírico ex-post (única lógica "de modelo")
   └─ demand|dispatch|hydro|thermal|scenarios|reporting/   → stubs (solo __init__.py)
data/raw|interim|processed   ── insumos XM + datasets model-ready
outputs/run_001..015         ── evidencia de calidad, brechas, piloto, consolidación
```

La salida objetivo declarada por los autores es **"Recomendación de despacho y priorización térmica"**, explícitamente **no** un SDDP completo ni un Unit Commitment (ver `docs/DIFERENCIA_DESPACHO_CVAR_SDDP_UC.md`). La puerta de calidad global estaba en estado `BLOCKED_CRITICAL_DATA`.

## 2. Componentes funcionales (verificados)

| Componente | Estado | Evidencia |
|---|---|---|
| Ingesta/adquisición XM (pydataxm) | Funcional (piloto) | `src/.../data/xm_*`, `outputs/run_007/008` |
| Validación de unidades y contratos | Funcional | `src/.../validation/*`, 96 pruebas OK |
| Consolidación histórica del sistema (diaria) | Funcional | `system_historical_v3/system_daily_model_ready.csv` |
| Hidrología energética agregada SIN | Funcional | `hydro_system_historical_v1/…_model_ready.csv` |
| Hidrología por embalse (24 embalses) | Funcional | `hydro_reservoir_historical_v2/…_model_ready.csv` |
| CVaR empírico (ex-post) | Funcional (utilidad) | `src/.../risk/cvar.py` |
| Parche pydataxm `freq='M'→'ME'` | Aplicado | `scripts/14`, respaldo `.bak_v001` |

## 3. Componentes incompletos o ausentes

| Componente | Estado real |
|---|---|
| Modelo determinístico de despacho hidro-térmico | **Ausente** (módulo `dispatch/` es stub vacío) |
| Topología hidráulica (embalse–río–central) | **Ausente** |
| Pronóstico hidrológico / ENOS | **Ausente** (módulo `forecasting/` inexistente) |
| Generación y reducción de escenarios | **Ausente** (`scenarios/` stub) |
| SDDP (forward/backward/cortes/convergencia) | **Ausente** |
| CVaR **integrado** en la optimización | **Ausente** (solo métrica ex-post) |
| Backtesting de políticas | **Ausente** (`outputs/run_002/003/004` reservados y **vacíos**) |
| API de resultados | **Ausente** |
| Dashboard | **Ausente** (no hay `app/`, ni Streamlit/hardcoded) |
| Actualización incremental | **Parcial** (hay descarga controlada, no incremental por fecha) |
| Solver de optimización | **Ausente** en `requirements.txt` |

## 4. Datos disponibles (validados)

| Dataset (model-ready) | Cobertura | Resolución | Variables clave (unidad) |
|---|---|---|---|
| `hydro_system_daily_model_ready` | **2010-01-01 → 2026-07-13** (6038 d) | diaria | aportes_energia (GWh), volumen_util_energia (GWh), capacidad_util_energia (GWh), %volumen |
| `hydro_reservoir_daily_model_ready` | 2010-01-01 → 2026-07-13 | diaria × **24 embalses** | volumen/capacidad_util_energia (GWh), %oficial |
| `system_daily_model_ready` | 2023-01-31 → 2026-07-13 (1230 d) | diaria | demanda_sin (GWh), demanda_real (GWh), generacion_total (GWh), import/export (GWh), flags de completitud |
| `by_target/generacion_real_total` | 2023-01-01 → 2026-07-13 | horaria | generación total del **Sistema** (GWh) |
| `by_target/demanda_sin_diaria` | 2023-01-01 → 2026-07-13 | diaria | demanda SIN (GWh) |
| Piloto por recurso (carbón) | 2026-06-01 → 2026-06-07 | diario/horario | capacidad/disponibilidad/gen por recurso (parcial) |

**Cifras reales verificadas (2023-01-31 → 2026-07-13):** demanda media **227.4 GWh/día**, generación media **228.8 GWh/día**, aportes medios **204.9 GWh/día**, volumen útil medio **66.0 %** de capacidad (rango 28.6 %–86.0 %). Precio de bolsa se maneja en **COP/kWh** (no MWh).

## 5. Datos faltantes / brechas (críticas para el modelo)

1. **Generación por tecnología (hidro/térmica) clasificada por `ListadoRecursos`** — solo existe el total del Sistema y un piloto de 7 días para carbón. Impide medir el split real y validar los hallazgos (§8).
2. **Capacidad y disponibilidad térmica MW de toda la flota** — solo parcial para carbón.
3. **Precios**: bolsa/oferta históricos por recurso — **no incluidos** en el paquete (aparecen citados en decisiones previas pero no en `data/processed`).
4. **Aportes por embalse/río** — inflows solo a nivel **SIN agregado** (no por embalse).
5. **Serie ONI/ENOS** — no incluida; requerida para condicionar escenarios.
6. **Demanda proyectada oficial** y **relación gas/combustible** — ausentes.
7. **Catálogos maestros externos** (`ListadoMetricas.xlsx`, `ListadoRecursos.xlsx`) — referenciados vía `config/data_sources.json` a rutas Windows `D:/Proyectos/...` inexistentes en este servidor.

## 6–7. Variables disponibles vs. faltantes

- **Disponibles y suficientes** para un modelo de **embalse-equivalente agregado**: demanda, aportes, volumen, capacidad (todo en GWh, diario).
- **Faltantes** para granularidad por planta/recurso: costo variable térmico, capacidad/disponibilidad MW por recurso, split hidro/térmico observado, aportes por embalse.

## 8. Calidad de datos

- Integridad del paquete: **3079/3079** archivos con SHA-256 correcto; 0 faltantes, 0 corruptos.
- `quality_status = OK` y `model_ready = True` en los datasets hidrológicos agregado y por embalse.
- Balance del sistema con banderas de completitud (`datos_completos_balance`) y manejo explícito de **ceros estructurales** (import/export).
- **No validable con estos datos:** los hallazgos citados de "hidro ≈ 78.5 %", "térmica ≈ 21.5 %" y "corr(aportes, térmica) ≈ −0.611". Un proxy por balance energético (`hidro ≈ aportes − Δvolumen`) es **circular** para el cálculo de la térmica y da un signo de correlación artificial (+0.73); no debe reportarse como validación. Validarlos requiere generación-por-tecnología (brecha §5.1).

## 9. Cobertura temporal

- Hidrología (aportes/volumen): **16.5 años** diarios (2010–2026) → base sólida para climatología, ENOS y escenarios.
- Balance del sistema (demanda/generación): **3.5 años** diarios (2023–2026).
- Ventana común para acoplar demanda + hidrología: **2023-01-31 → 2026-07-13** (1230 días).

## 10. Cobertura geográfica

- SIN agregado (nacional) + **24 embalses**: AGREGADO BOGOTA, ALTOANCHICAYA, AMANI, BETANIA, CALIMA1, CHUZA, EL QUIMBO, ESMERALDA, GUAVIO, ITUANGO, MIRAFLORES, MUNA, PENOL, PLAYAS, PORCE II, PORCE III, PRADO, PUNCHINA, RIOGRANDE2, SALVAJINA, SAN LORENZO, TOPOCORO, TRONERAS, URRA1.

## 11–15. Estado del modelo / MC / CVaR / SDDP / dashboard

- **Modelo hidro-térmico:** inexistente (stub). Se construirá determinístico multiperiodo (ETAPA 3).
- **Monte Carlo:** inexistente. Se construirá vía escenarios (ETAPA 6).
- **CVaR:** solo `empirical_cvar`/`expected_plus_lambda_cvar` (ex-post). Falta integrarlo en la función objetivo (ETAPA 8).
- **SDDP:** inexistente. Se implementará forward/backward + cortes (ETAPA 7).
- **Dashboard/API:** inexistentes (ETAPA 10).

## 16. Actualización de datos

Existe descarga controlada por bloques (scripts 07–11) con checkpoints y reintentos, pero **no** hay actualización incremental por "última fecha disponible". Se implementará en ETAPA 11 (sin declarar "tiempo real": XM tiene rezago).

## 17. Pruebas (línea base)

- Comando: `python -m unittest discover -s tests`
- **Total: 103 · OK: 96 · Fallos: 1 · Errores: 6 · Tiempo: ~0.3 s**
- Causa única de los 7 no-OK: `config/data_sources.json` apunta a rutas externas Windows (`D:/Proyectos/...`) inexistentes en este servidor; 6 errores por `ListadoMetricas.xlsx` ausente y 1 fallo por `assert path.exists()`. **No son fallos de lógica**, sino de portabilidad/insumos externos. Se tratarán con *skip* condicionado documentado en ETAPA 2 (no se ocultan; se marcan con razón).

## 18. Deuda técnica

1. Rutas externas absolutas de Windows en `config/data_sources.json` (no portables).
2. Tests acoplados a catálogos maestros externos no versionados.
3. `requirements.txt` sin solver de optimización.
4. Datos versionados en git pese a `.gitignore` (diferencias solo por CRLF; se mantuvieron las versiones commiteadas).
5. Sin CI, sin `pyproject`/lockfile, sin linter configurado.
6. Documentación en `docs/` extensa pero previa al modelo.

## 19. Riesgos

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Brechas de datos (precio, disp. térmica, split) | El despacho requiere **supuestos** | Supuestos config-driven, marcados, con sensibilidad; nunca presentados como dato oficial |
| RAM 8 GB, 4 vCPU (no es el host L40S) | Limita nº de escenarios/estados | Granularidad agregada, escenarios reducidos, Parquet, checkpoints |
| Sin gen-por-tecnología | Backtest del split limitado | Backtest sobre demanda/volumen y coherencia física; documentar límite |
| ENOS sin ONI local | Escenarios condicionados incompletos | Ingerir ONI (fuente pública) o parametrizar por fase; documentar |

## 20. Plan de trabajo (ETAPAS)

- **E2** Catálogo/validación de datos + portabilidad `data_sources.json` + diccionario.
- **E3** Despacho determinístico hidro-térmico (LP, HiGHS, embalse-equivalente, config-driven).
- **E4** Topología hidráulica (catálogo trazable de los 24 embalses + cadenas).
- **E5** Pronóstico hidrológico condicionado a ENOS (baselines → SARIMAX/ML, backtesting).
- **E6** Escenarios estocásticos de aportes/demanda (correlación, persistencia, reducción).
- **E7** SDDP formal (forward/backward, cortes de Benders, convergencia, checkpoints, valor del agua).
- **E8** CVaR integrado (λ, α configurables; sensibilidad).
- **E9** Backtesting y sensibilidad (episodios ENOS; comparación de políticas vs. baseline).
- **E10** API + dashboard con trazabilidad y tooltips.
- **E11** Actualización incremental XM.
- **E12** Documentación completa, pruebas, informes técnico/ejecutivo, commits y push.

## 21. Criterios de aceptación

Instalación reproducible ✓ · datos verificables ✓ · unidades consistentes (COP/kWh, GWh) · modelo determinístico válido · escenarios reproducibles (semilla) · SDDP formal **o** limitación demostrada · CVaR integrado · sensibilidad λ/α · backtesting · resultados fuera de muestra · API · dashboard · trazabilidad (fuente/unidad/fecha/método por cifra) · actualización incremental · documentación · pruebas (mantener 96 OK + nuevas) · commits y push · reporte técnico y ejecutivo · ejecución demostrativa reproducible que reporte estado inicial, escenario, λ, α, despacho, costo esperado, VaR, CVaR, ENS, volumen final, recomendación térmica, justificación y limitaciones.
