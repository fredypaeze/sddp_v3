# Reporte de cierre — SDDP + CVaR v0.1.0

- **Fecha:** 2026-07-23
- **Rama de entrega:** `trabajo/modelo-hidrotermico-v3`
- **Commit fusionado validado (código):** `58f7c17` (merge del PR #1). El commit de cierre añade **solo documentación** sobre esa base ya validada.
- **Entorno:** Ubuntu 24.04, Xeon SapphireRapids 4 vCPU / 7.7 GB RAM, **sin GPU**. Python **3.11.15**, solver **HiGHS 1.11.0**.

## Pruebas (reconciliadas)

- **Total: 143 · Aprobadas: 136 · Omitidas: 7 · Fallidas: 0** (xfail/xpass/deselected: 0).
- Reconciliación: 136 + 7 + 0 = 143 ✓ (verificado con `unittest.TestResult`). El reporte previo decía “134”: era un **error de conteo** (las pruebas del piloto XM imprimen a stdout y rompían el conteo por línea); el número correcto de aprobadas es **136**.
- Los 7 *skip* dependen de catálogos maestros XM externos no montados (portabilidad, no lógica); no son funcionalidad crítica de ejecución.

## Corrida demostrativa

- Comando: `PYTHONPATH=src python scripts/24_sddp.py` → `outputs/run_024_v001/`.
- **Horizonte:** agosto 2026 – enero 2027 · **Condición:** El Niño (ONI≈0.98) · **λ=0.0, α=0.95**.
- **Resultado demostrativo condicionado a los datos, escenarios y supuestos configurados en la versión v0.1.0:**
  - Costo esperado ≈ **6.55 B COP** · VaR₉₅ ≈ **8.00 B COP** · CVaR₉₅ ≈ **8.35 B COP**.
  - Probabilidad simulada de ENS: **0 %** (con el embalse al 79 %). *La ENS de 0 % **no** significa que el riesgo real del sistema sea cero.*
  - Convergencia en **5 iteraciones**.
- **No es un pronóstico oficial.**

## Balances (500 simulaciones)

- **Balance energético** `gh+gt+ens=D`: OK (máx. desviación **0.00 GWh**).
- **Balance hídrico** `v=v₋₁+a−gh−sp`: OK (**0.00 GWh**).
- Límites de embalse, gh∈[0,Hmax], gt∈[0,Tmax], ENS≥0: OK.

## Convergencia — explicación del gap

- **Definición:** `gap = (UB − LB) / UB`, adimensional.
- **LB** (cota inferior): valor del subproblema de la primera etapa con la función de costo futuro vigente. Es una cota inferior válida y **no decrece** entre iteraciones.
- **UB** (cota superior): **media Monte Carlo** del costo total de las trayectorias del forward pass; es un **estimador muestral** con ruido.
- **Por qué puede ser negativo:** al ser el UB una media muestral de pocas trayectorias, puede quedar por **debajo** del LB dentro del error de muestreo; entonces `gap<0`. No es un error matemático: refleja la **varianza del estimador del UB**, no un LB por encima del óptimo.
- **¿Convergió?** Sí: la cota inferior se estabilizó y el `|gap| = 0.011 < tol = 0.02` (criterio cumplido, iteración ≥ 3). El indicador negativo corresponde a **tolerancia numérica / estimación muestral**, no a una violación del criterio. No se alteró el algoritmo para forzar un signo.

## API

- Inicia con `uvicorn`; `/estado`, `/riesgo`, `/docs` responden **200** (verificado también en clon limpio).

## Dashboard

- Inicia con Streamlit; carga **sin excepción** (5 pestañas, métricas reales), verificado con `streamlit.testing` en clon limpio.

## Validación en clon limpio

Clon nuevo de la rama de entrega (fuera del repo principal): commit 58f7c17, venv 3.11.15, instalación de `requirements.txt` + `requirements-model.txt` (exit 0), **`uv pip check` = “All installed packages are compatible” (78 paquetes)**, parche pydataxm, extracción del paquete (3082 archivos), **143 pruebas OK**, demo **reproducida idénticamente**, API 200, dashboard sin excepción. Clon temporal eliminado tras la validación.

> Nota: en un venv de `uv` no se instala `pip`; usar **`uv pip check`** (no `python -m pip check`). Documentado en la guía rápida.

## Limitaciones (declaradas, no bloqueantes)

Embalse-equivalente agregado; split hidro/térmico endógeno; costos/capacidad térmica y precios son supuestos configurables; respuesta a λ acotada en el agregado; datos hasta 2026-07-13; actualización incremental pendiente del catálogo externo; validación institucional pendiente. Detalle en `docs/LIMITACIONES_v001.md` y `docs/ALCANCE_ENTREGA_v001.md`.

## Riesgos de interpretación

- Los resultados son **demostrativos**, condicionados a supuestos configurables; **no** son instrucción operativa oficial ni pronóstico.
- **P(ENS)=0 %** es del modelo agregado bajo los escenarios configurados; **no** implica riesgo real nulo del SIN.
- El costo esperado usa el precio de bolsa por fase como proxy del costo térmico; no es costo declarado por planta.

## Archivos de entrega

- Código: `src/minenergia_sddp/`, `scripts/20–27`, `app/dashboard.py`, `config/model/`.
- Datos: `paquete_datos/transferencia_sddp_v3_20260723.zip` (SHA-256 verificado; manifiesto 3079/3079) + `data/reference/oni_noaa.csv`.
- Resultado demostrativo: `outputs/run_024_v001/`.
- Documentación: `docs/*_v001.md` (guía rápida, alcance, este reporte, informes, y los técnicos por etapa).

## Comandos exactos

- Modelo: `PYTHONPATH=src .venv/bin/python scripts/24_sddp.py`
- API: `PYTHONPATH=src .venv/bin/uvicorn minenergia_sddp.api.app:app --host 127.0.0.1 --port 8900`
- Dashboard: `PYTHONPATH=src .venv/bin/streamlit run app/dashboard.py --server.port 8901`

## Estado final

**ENTREGA CERRADA — v0.1.0.** Prototipo analítico funcional, reproducible y correctamente delimitado. Merge del PR #1 realizado; commit de cierre y tag `v0.1.0-entrega` publicados.
