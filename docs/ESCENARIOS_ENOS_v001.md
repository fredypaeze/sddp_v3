# Escenarios estocásticos de aportes condicionados a ENOS (v001)

Modelo estocástico de aportes del SIN para el SDDP. Código: `src/minenergia_sddp/scenarios/inflow.py`. Ejecución: `PYTHONPATH=src python scripts/23_escenarios_aportes.py` → `outputs/run_023_v001/`.

## Modelo: PAR/ARX(1) periódico en espacio log

Sobre el log de aportes desestacionalizado `a'_t = log(a_t) − μ_mes`:

```
a'_t = c + b_oni·ONI_t + φ·a'_{t-1} + ε_t ,   ε_t ~ N(0, σ²)
```

Parámetros ajustados (2010–2026): **φ = 0.633** (persistencia), **b_oni = −0.079** (El Niño reduce aportes), **σ_ε = 0.197**. Preserva estacionalidad (μ_mes, σ_mes), persistencia (φ) y efecto ENOS (b_oni).

## Dos representaciones

- **`stage_scenarios` → [T, K]** muestras marginales por etapa con probabilidades uniformes. Supuesto de **independencia por etapa** (estándar del SDDP): la incertidumbre de cada etapa es independiente dado el estado. Es lo que consume el SDDP (ETAPA 7).
- **`simulate` → trayectorias [n, T]** que preservan la persistencia φ. Para Monte Carlo, validación y evaluación fuera de muestra.

## Validación vs. historia

`validate` compara media, desviación y percentiles simulados por etapa contra la climatología histórica del mes. Para el horizonte El Niño (Ago 2026–Ene 2027, ONI≈0.98) las medias simuladas quedan **~10–15 % por debajo** de la media histórica no condicionada — el efecto ENOS esperado. La dispersión simulada es del mismo orden que la histórica.

## Reducción de escenarios

`reduce_scenarios` agrupa las trayectorias con k-means y asigna probabilidad = peso del clúster (suma 1). Útil para representar el árbol con pocos escenarios trazables.

## Reproducibilidad

Todo el muestreo usa `numpy.random.Generator` con semilla explícita (por defecto 42). Misma semilla ⇒ mismos escenarios (probado).

## Limitaciones (honestidad)

- La independencia por etapa es un supuesto del método; la persistencia real (φ=0.633) se conserva solo en las trayectorias completas, no en el muestreo por etapa.
- El ONI futuro se toma del último valor observado (ver pronóstico §Limitaciones).
- Solo aportes son estocásticos; la demanda se trata determinística (extensión futura: escenarios de demanda).
