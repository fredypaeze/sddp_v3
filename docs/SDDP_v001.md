# SDDP formal (v001)

Programación dinámica dual estocástica (SDDP) de **embalse-equivalente agregado** del SIN. Código: `src/minenergia_sddp/optimization/sddp.py`; construcción del horizonte: `optimization/build.py`; ejecución: `scripts/24_sddp.py` → `outputs/run_024_v001/`.

## Formulación

- **Etapas:** meses del horizonte operativo (6).
- **Estado:** volumen útil almacenado `v` (GWh). Único estado (los aportes son de independencia por etapa ⇒ no entran al estado).
- **Decisiones por etapa:** generación hidráulica `gh`, térmica `gt`, energía no servida `ens`, vertimiento `sp`, volumen final `v_next`.
- **Incertidumbre:** aportes (K muestras por etapa con probabilidad), del modelo PAR/ARX(1)+ONI (ETAPA 6).
- **Transición:** `v_next = v + aporte − gh − sp`, con `0 ≤ v_next ≤ capacidad`.
- **Costo inmediato:** `c_term·gt + c_ens·ens + c_spill·sp` (MnCOP; 1 MnCOP/GWh = 1 COP/kWh).
- **Costo futuro (FCF):** función `θ(v_next)` aproximada por **cortes de Benders** acumulados; FCF terminal codifica el valor del agua al final (penaliza terminar bajo `vfin`).

## Algoritmo

1. **Forward pass:** desde `V0`, muestrea trayectorias de aportes, resuelve el subproblema de cada etapa con la FCF vigente, registra estados visitados y costo inmediato + costo terminal exacto.
2. **Backward pass:** de la última a la primera etapa, en cada estado visitado resuelve para cada aporte posible, promedia valor y **dual del balance hídrico** (subgradiente respecto a `v`), y agrega un corte a la FCF de la etapa previa.
3. **Cota inferior (LB):** valor del subproblema de la 1ª etapa (aporte esperado). No decrece entre iteraciones.
4. **Cota superior (UB):** media del costo total de las trayectorias forward (estimador Monte Carlo, con ruido).
5. **Convergencia:** cuando `(UB−LB)/UB` cae bajo la tolerancia (o máx. iteraciones).
6. **Checkpoints:** los cortes se guardan/recargan (`save_cuts`/`load_cuts`) para reanudar.

## Validación de correctitud

- **Límite determinístico (K=1):** LB=UB (gap≈0) ⇒ el SDDP recupera exactamente el óptimo determinístico multiperiodo. Probado.
- **Monotonía:** la cota inferior no decrece. Probado.
- **Reproducibilidad:** misma semilla ⇒ mismo LB. Probado.

## Resultado del horizonte vigente (run_024_v001)

Horizonte Ago 2026–Ene 2027, fase **El Niño** (ONI≈0.98). Converge en pocas iteraciones. **E[costo] ≈ 6.55 billones COP** para los 6 meses — del mismo orden que el hallazgo histórico documentado (~6.365 billones bajo El Niño). Valor del agua inicial ≈ 217 COP/kWh (= costo térmico marginal). P(ENS)=0 % con el volumen inicial actual.

## Granularidad y justificación

Se usa un **embalse-equivalente agregado** porque los aportes solo existen a nivel SIN agregado (auditoría §5); el nivel por embalse tiene volumen/capacidad pero no aportes. Es la granularidad soportada por los datos. La regionalización queda como extensión (requiere desagregar aportes).

## Limitaciones (honestidad)

- Independencia por etapa de los aportes (supuesto estándar del SDDP); la persistencia real se preserva solo en las trayectorias de validación.
- Demanda determinística (climatología); costo térmico por una fase ENOS del horizonte.
- Costo térmico y capacidad son **supuestos** config-driven (brechas de datos), con sensibilidad en ETAPA 9.
- El UB es un estimador Monte Carlo: su intervalo puede contener al LB.

## Riesgo (CVaR integrado)

La `SddpConfig` incluye `lam` (aversión) y `alpha`. Con `lam>0`, el backward reponderá la cola (peores costos) — SDDP averso al riesgo con **CVaR anidado integrado en la política** (no ex-post). Ver `docs/CVAR_v001.md` (ETAPA 8).
