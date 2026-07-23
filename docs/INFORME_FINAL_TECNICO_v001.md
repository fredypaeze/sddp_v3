# Informe final técnico — SDDP + CVaR (v001)

## 1. Objetivo y alcance

Modelo de optimización estocástica hidro-térmica del SIN colombiano para decisiones operativas a **6 meses** bajo incertidumbre climática (ENOS). Función objetivo `min E[C_op] + λ·CVaR_α[C_crit]`. Se partió de un repositorio que era una **base de ingeniería de datos con puertas de calidad** (sin optimizador, MC, SDDP ni dashboard) y se completó el producto.

## 2. Entorno y datos

- Python 3.11.15, solver **HiGHS**; servidor 4 vCPU / 8 GB (no el host L40S; el LP es CPU/RAM-bound).
- Paquete de datos: SHA-256 **verificado**, manifiesto **3079/3079** íntegro.
- Cobertura: hidrología (aportes/volumen/capacidad en GWh) **2010–2026**; balance del sistema (demanda/generación) **2023–2026**; **24 embalses**; ONI NOAA 2009–2026.
- Cifras validadas: demanda 227 GWh/día, aportes 205, generación 229, volumen medio 66 % (28.6–86 %).

## 3. Componentes construidos

| Etapa | Entregable | Estado |
|---|---|---|
| Determinístico | LP multiperiodo HiGHS, balances exactos, valor del agua | ✅ |
| Topología | Catálogo 24 embalses + cascadas (fuente/confianza/validación) | ✅ |
| Pronóstico ENOS | SARIMAX+ONI vs baselines, backtesting temporal | ✅ |
| Escenarios | PAR/ARX(1)+ONI, validación vs historia, reducción | ✅ |
| SDDP | forward/backward, cortes de Benders, LB/UB, convergencia, checkpoints | ✅ |
| CVaR | integrado (anidado en cortes), λ/α, sensibilidad | ✅ |
| Backtesting | políticas vs episodios ENOS, con y sin estrés | ✅ |
| API + dashboard | FastAPI + Streamlit, trazabilidad | ✅ |
| Actualización | plan incremental (descarga bloqueada por catálogo externo) | ⚠️ parcial |

## 4. Resultados clave

- **Pronóstico:** `sarimax_oni` supera baselines (MAE **35.7** GWh/día vs 42.8 climatología). El Niño **reduce los aportes ~30 %** (131 vs 187 GWh/día).
- **Escenarios:** φ=0.633 (persistencia), b_oni=−0.079 (El Niño reduce aportes); medias/percentiles simulados consistentes con la historia.
- **SDDP (horizonte El Niño):** LB≈UB (converge); **E[costo] ≈ 6.55 B COP**, coherente con el hallazgo histórico documentado (~6.365 B); valor del agua inicial ≈ 217 COP/kWh; P(ENS)=0 con el embalse actual (79 %).
- **CVaR:** responde al estrés (CVaR 8.2 → **13.2 B COP**) y crece con α (12.4→13.2→15.0). Limitación honesta: en el embalse agregado la respuesta a λ es acotada; λ=1 es sobre-conservador (recomendado λ∈[0,0.5]).
- **Backtesting:** con embalse sano todas las políticas coinciden; **bajo estrés + El Niño el SDDP evita 2 205 GWh de déficit (ahorra 2.38 B COP)** frente a la regla miope; en período benigno la precaución cuesta ~1 B COP.

## 5. Validación de correctitud

Límite determinístico del SDDP (LB=UB), cota inferior monótona, reproducibilidad por semilla, balances energético/hídrico exactos, unidades consistentes (GWh, COP/kWh). **143 pruebas** (7 *skip* documentados).

## 6. Limitaciones y trabajo futuro

Ver `docs/LIMITACIONES_v001.md`: falta generación por tecnología, capacidad/disponibilidad térmica MW y precios oficiales (se usan supuestos); embalse agregado; demanda determinística; sin gas explícito; recomendación agregada (no orden de encendido). Para producción: datos por recurso, topología validada, escenarios de demanda, integración de gas, actualización con fuentes externas montadas y validación institucional.

## 7. Reproducibilidad

`uv pip install -r requirements.txt -r requirements-model.txt`, parche pydataxm, descomprimir el paquete, ejecutar `scripts/20→27`. Cada corrida deja `outputs/run_XXX/` con commit, semilla, hashes y resultados.

## 8. Validación de aceptación pre-merge (2026-07-23)

Auditoría final sobre `trabajo/finalizacion-sddp-cvar-v1` antes del PR #1: 143 pruebas (134 OK, 0 fallos, 7 skip, ~36 s); **invariantes físicas verificadas sobre 500 simulaciones** (balance energético 0.00 GWh, balance hídrico 0.00 GWh, límites de embalse, gh∈[0,Hmax], gt∈[0,Tmax], ENS≥0); SDDP validado (límite determinístico LB=UB, convergencia gap −0.011) y CVaR integrado; API y dashboard operativos; repositorio sin tokens/credenciales. **Recomendación: APTO PARA MERGE.** Acta completa en `docs/ACTA_VALIDACION_PRE_MERGE_v001.md`.
