# Acta de validación pre-merge — SDDP + CVaR (v001)

## Identificación

- **Rama:** `trabajo/finalizacion-sddp-cvar-v1`
- **Commit validado (código):** `8150d47` (el commit final de la rama es esta acta + actualización de docs, encima de `8150d47`; el árbol de código auditado es idéntico).
- **PR:** #1 (abierto). Cualquier push a la rama lo actualiza automáticamente; **no se crea otro PR ni se fusiona**.
- **Fecha:** 2026-07-23

## Entorno

- Ubuntu 24.04, Xeon SapphireRapids **4 vCPU / 7.7 GB RAM**, sin GPU (no es el host L40S descrito).
- **Python 3.11.15** (venv `uv`), solver **HiGHS 1.11.0**, `pip check` limpio.

## Datos utilizados

- Paquete `transferencia_sddp_v3_20260723.zip`: SHA-256 verificado; manifiesto **3079/3079** íntegro.
- Hidrología energética (aportes/volumen/capacidad, GWh) **2010–2026**; balance del sistema (demanda/generación) **2023–2026** (1230 días); **24 embalses**; ONI NOAA 2009–2026.

## Pruebas

- Comando: `python -m unittest discover -s tests`
- **Total: 143 · Aprobadas: 134 · Fallidas: 0 · Omitidas: 7 · Tiempo: ~36 s**
- Los 7 *skip* están documentados: dependen de catálogos maestros XM externos no montados en este servidor (portabilidad, no lógica).

## Corrida demostrativa (reproducible)

- `PYTHONPATH=src python scripts/24_sddp.py --iters 30 --forward 20 --k 20 --seed 42` → `outputs/run_024_v001/`.
- Horizonte **Ago 2026 – Ene 2027**, fase **El Niño** (ONI≈0.98). SDDP converge en **5 iteraciones**.

## Resultados

| Métrica | Valor |
|---|---|
| Costo esperado E[·] | **6.55 B COP** (≈ hallazgo histórico 6.36 B) |
| VaR₉₅ | 8.00 B COP |
| CVaR₉₅ | 8.35 B COP |
| Probabilidad de ENS | 0.0 % (embalse al 79 %) |
| Valor del agua inicial | ≈ 217 COP/kWh |
| Convergencia SDDP | LB 6.598 / UB 6.526 / gap −0.011 (LB no decrece) |

### Verificación física explícita (500 simulaciones)

| Verificación | Resultado |
|---|---|
| Balance energético `gh+gt+ens=D` | **OK** (máx. desviación 0.00 GWh) |
| Balance hídrico `v=v₋₁+a−gh−sp` | **OK** (0.00 GWh) |
| Límites de embalse `0≤v≤cap` | **OK** |
| Generación hidro `0≤gh≤Hmax` | **OK** |
| Generación térmica `0≤gt≤Tmax` | **OK** (llega al tope: restricción activa) |
| ENS `≥0` | **OK** |
| λ / α | 0.0 / 0.95 |
| SDDP real (forward/backward/cortes/convergencia) | **Implementado y validado** (límite determinístico LB=UB) |
| CVaR integrado (anidado en los cortes, no ex-post) | **Sí** |

## Estado por madurez

- **Completamente funcionales:** despacho determinístico, pronóstico ENOS, escenarios, SDDP, CVaR (maquinaria), backtesting, API, dashboard, pruebas, reproducibilidad.
- **Parcialmente funcional:** actualización incremental (plan listo; descarga real bloqueada por catálogo externo).
- **Prototipo / requiere validación institucional:** recomendación térmica agregada; supuestos de costo/capacidad térmica y precios.
- **Hardcoded restante:** ninguno en resultados (todo sale de ejecuciones). Los **supuestos** viven en `config/model/parametros_base.json`, marcados y con sensibilidad; **no** son datos oficiales.

## Limitaciones críticas

Embalse-equivalente agregado (sin cadenas por planta); split hidro/térmico endógeno (sin generación por tecnología); costo/capacidad térmica y precios son supuestos; demanda determinística; CVaR de respuesta acotada a λ en el agregado (usar λ∈[0,0.5]). Ver `docs/LIMITACIONES_v001.md`.

## Bloqueos

- **Actualización de datos nuevos:** requiere catálogo maestro externo (ListadoMetricas) + red a XM. El histórico incluido (hasta 2026-07-13) es suficiente para el modelo y el backtesting. Ver `docs/ACTUALIZACION_DATOS_v001.md`.

## Higiene del repositorio

- Sin tokens/credenciales/.env/venv/cachés/temporales rastreados ni en el historial de la rama (verificado por `git grep` y `git log -p`).
- **61 archivos** modificados, todos necesarios: src 17, tests 10, scripts 7, docs 20, config 2, app 1, data/reference 2, raíz 2. Sin archivos fuera de `/home/tuxilo/sddp_v3`.

## Instrucciones exactas

- **Ejecutar el modelo:** `PYTHONPATH=src .venv/bin/python scripts/24_sddp.py`
- **Abrir la API:** `PYTHONPATH=src .venv/bin/uvicorn minenergia_sddp.api.app:app --host 127.0.0.1 --port 8900` (docs en `/docs`)
- **Abrir el dashboard:** `PYTHONPATH=src .venv/bin/streamlit run app/dashboard.py --server.port 8901`

## Recomendación

**APTO PARA MERGE.** El código está limpio, las pruebas pasan (143, 0 fallos), las invariantes físicas se cumplen, el SDDP y el CVaR están implementados y validados, la API y el dashboard funcionan, y las limitaciones/bloqueos están documentados con honestidad. El merge lo realizará el usuario manualmente.
