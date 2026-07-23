# CVaR integrado en el SDDP (v001)

Aversión al riesgo mediante **CVaR anidado integrado en la política** (no calculado ex-post). Código: `src/minenergia_sddp/optimization/sddp.py` (pesos de riesgo en el backward pass); sensibilidad: `scripts/25_cvar_sensibilidad.py` → `outputs/run_025_v001/`.

## Medida de riesgo

En cada etapa se optimiza la medida coherente convexa:

```
ρ[Z] = (1 − λ)·E[Z] + λ·CVaR_α[Z]
```

- **λ ∈ [0,1]**: aversión al riesgo (0 = neutral; 1 = solo CVaR). Parámetro de **política pública**, no una constante física.
- **α ∈ [0.80, 0.99]**: nivel de cola (por defecto 0.95).

## Integración en el SDDP (no ex-post)

La diferencia clave con calcular el CVaR sobre resultados ya simulados: aquí la medida entra en la **construcción de los cortes de Benders**. En el backward pass, el corte no usa la esperanza simple `Σ p_k Q_k` sino una **esperanza reponderada** `Σ q_k Q_k`, donde los pesos `q_k` cargan más masa en los peores (mayor costo) aportes:

```
q_k = (1 − λ)·p_k + λ·w_k^CVaR
```

`w_k^CVaR` reparte la probabilidad de la peor fracción (1−α) de resultados (Rockafellar–Uryasev en forma discreta). Con λ=0, `q_k = p_k` (neutral). Así la **función de costo futuro y, por tanto, la política** quedan optimizadas bajo el riesgo — no se re-evalúa una política neutral.

Verificado por pruebas: los pesos son iguales a las probabilidades con λ=0 y cargan la cola con λ>0 (`tests/test_cvar.py`).

## Descomposición de costos reportada

Para cada política se reporta: **E[costo], VaR_α, CVaR_α**, generación térmica, probabilidad de ENS y volumen final. VaR y CVaR se calculan con `src/minenergia_sddp/risk/cvar.py`.

## Resultados de sensibilidad (run_025_v001)

**Caso base (embalse real ~79 %, El Niño):** E[costo] 6.36 · CVaR₉₅ 8.19 B COP · **P(ENS)=0 %**. Sin riesgo de cola: la aversión no cambia el costo (correcto — el sistema hoy es robusto a 6 meses).

**Caso de estrés (embalse 32 %, térmica 60 GWh/día, valor estratégico del agua 800 COP/kWh):** aparece riesgo real — **P(ENS)=25 %, CVaR₉₅ 13.2 B COP ≫ E 8.1 B COP**.

| λ (α=0.95) | E[costo] | CVaR₉₅ | P(ENS) |
|---|---|---|---|
| 0.00 | 8.10 | 13.24 | 24.7 % |
| 0.25–0.75 | 8.10 | 13.24 | 24.7 % |
| 1.00 | 9.63 | 14.61 | 91.2 % |

| α (λ=0.75) | CVaR |
|---|---|
| 0.90 | 12.39 |
| 0.95 | 13.24 |
| 0.99 | 14.99 |

**Lecturas honestas:**
1. El **CVaR responde correctamente al estrés** (8.19 → 13.24) y **crece con α** (12.39 → 13.24 → 14.99): la maquinaria mide bien la cola.
2. En este **embalse-equivalente agregado**, la respuesta a **λ es limitada**: para λ∈[0, 0.75] la política agregada es casi invariante (el recurso se adapta por escenario, dejando poco margen de cobertura por *timing*), y en **λ=1 (CVaR puro) la política se vuelve patológicamente conservadora** (acapara agua por su valor terminal y provoca ENS en el 91 % de los escenarios). Es una **limitación conocida del CVaR anidado/time-consistent** en SDDP.
3. Conclusión de política: bajo estrés severo el problema es de **adecuación de energía/capacidad**, no de preferencia de riesgo; la gestión por despacho tiene poco margen. El CVaR **cuantifica la exposición** (13.2 B COP en la cola vs 8.1 esperado) — información valiosa — pero mitigarla exige **capacidad firme**, no solo re-despacho. **Recomendación operativa: usar λ∈[0, 0.5]**; λ=1 no es aconsejable.

## Lectura de política pública

- **λ** responde a “¿cuánto está dispuesto el sistema a pagar (más costo esperado) para reducir la exposición a los escenarios extremos (CVaR, riesgo de déficit)?”.
- **α** fija qué tan extrema es la cola que se protege.
- La herramienta cuantifica el **trade-off**: cuánto sube el costo esperado y cuánto baja el CVaR / la probabilidad de ENS al aumentar la aversión.

## Honestidad

- El CVaR anidado optimiza una medida por etapas; no es idéntico al CVaR del costo total de fin de horizonte (se reporta ambos: el objetivo usa el anidado; la evaluación reporta el CVaR empírico del costo total).
- La utilidad del CVaR depende de que exista **riesgo de cola**: con el embalse actual sano y capacidad suficiente, el riesgo de déficit a 6 meses es bajo y la aversión cambia poco el costo; su valor se hace evidente en condiciones de **estrés** (embalse bajo, El Niño severo, restricción de gas/térmica).
