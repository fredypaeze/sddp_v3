# Modelo matemático (v001)

Energía en GWh; costos en COP (COP/kWh × GWh). El SDDP trabaja internamente en MnCOP (1 MnCOP/GWh = 1 COP/kWh).

## Función objetivo

```
min_x  E[C_op(x,ω)] + λ · CVaR_α[C_crit(x,ω)]
```

- `x`: decisiones de despacho por etapa; `ω`: escenarios de aportes.
- `C_op`: costo operativo (térmico + penalizaciones).
- `C_crit`: costo crítico (cola de la distribución de costo).
- `λ ∈ [0,1]`: aversión al riesgo (política pública). `α ∈ [0.80,0.99]` (def. 0.95).

En el SDDP la medida se aplica **anidada por etapa**: `ρ = (1−λ)E + λ·CVaR_α`, integrada en los cortes (no ex-post).

## Despacho por etapa t (embalse-equivalente agregado)

Variables: `gh_t` (hidro), `gt_t` (térmica), `ens_t` (energía no servida), `sp_t` (vertimiento), `v_t` (volumen al cierre).

```
Balance eléctrico:  gh_t + gt_t + ens_t = D_t − O_t
Balance hídrico:    v_t = v_{t-1} + a_t − gh_t − sp_t        (v_{-1} = V0)
Cotas:              0 ≤ v_t ≤ Cap_t
                    0 ≤ gh_t ≤ Hmax_t ; 0 ≤ gt_t ≤ Tmax_t
                    0 ≤ ens_t ≤ D_t ; sp_t ≥ 0
Terminal:           v_{T-1} ≥ vfin   (o valor terminal del agua)
Costo inmediato:    c_term·gt_t + c_ens·ens_t + c_vert·sp_t
```

- `D_t` demanda, `a_t` aportes (estocásticos), `O_t` otras fuentes (config), `Cap_t` capacidad útil.
- **Valor del agua** = −dual del balance hídrico (COP/kWh): ahorro marginal por GWh extra de aporte.

## SDDP

Función de costo futuro `Q_{t+1}(v)` aproximada por cortes de Benders:
`Q_{t+1}(v) ≥ max_j { g_j + β_j·v }`, con `β_j` el dual promedio (reponderado por riesgo) del balance hídrico. Forward pass (trayectorias) + backward pass (cortes), cota inferior monótona y cota superior Monte Carlo; convergencia por brecha.

## Incertidumbre de aportes (PAR/ARX(1) periódico, espacio log)

```
a'_t = log a_t − μ_mes ;   a'_t = c + b_oni·ONI_t + φ·a'_{t-1} + ε_t
```

Preserva estacionalidad (μ_mes, σ_mes), persistencia (φ) y efecto ENOS (b_oni<0). Muestreo por etapa (independencia por etapa, para el SDDP) y trayectorias completas (para Monte Carlo/validación).

## Supuestos (config-driven, no oficiales)

Costo variable térmico por fase ENOS (proxy precio de bolsa: 217/423/180 COP/kWh), capacidad térmica, costo de ENS (racionamiento), otras fuentes. Ver `config/model/parametros_base.json` y `docs/LIMITACIONES_v001.md`.
