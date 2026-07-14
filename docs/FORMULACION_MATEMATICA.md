# Formulacion matematica

Estado de puerta usado para esta formulacion: **BLOCKED_CRITICAL_DATA**.

Esta especificacion no declara un SDDP completo. Un SDDP formal requeriria forward pass, backward pass, cortes y funcion de costo futuro aproximada. Tampoco declara Unit Commitment, porque no hay variables binarias, rampas, minimos tecnicos ni costos de arranque.

## Usos tecnicamente consistentes de `embalses_manu`

1. Estado inicial y condicion terminal indicativa si se valida conversion a unidad comun.
2. Envolvente o banda prospectiva de almacenamiento.
3. Trayectoria de validacion contra resultados simulados.

Seleccion actual: **trayectoria indicativa/envolvente y validacion**, no almacenamiento fijo endogeno ni aporte hidrico.

## Backtest deterministico condicionado

Indices: periodo `t`, recurso termico `r`, escenario `s`.

Decisiones: generacion hidraulica, generacion termica por recurso o bloque, almacenamiento, vertimiento, ENS e incumplimientos separados.

Objetivo: minimizar costo termico mas penalizaciones separadas por ENS e incumplimientos. Las penalizaciones no son valor economico del agua.

Restricciones requeridas: balance electrico, balance hidrico en unidad energetica comun, limites de generacion, disponibilidad, almacenamiento minimo/maximo, condicion inicial, condicion terminal y no negatividad.

## CVaR condicionado

Objetivo: minimizar `E[costo operativo] + lambda * CVaR_alpha[costo critico]`.

`lambda` pondera riesgo de cola; no es precio. Solo puede declararse optimizacion con CVaR si se resuelve conjuntamente con las variables de decision, no si se calcula la metrica ex post.
