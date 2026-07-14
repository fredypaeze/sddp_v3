# Diferencia entre despacho, CVaR, SDDP y Unit Commitment

- Despacho deterministico: optimiza una trayectoria con datos conocidos o supuestos fijos.
- Simulacion prospectiva: evalua escenarios futuros; no es prediccion si las entradas son supuestos.
- Optimizacion con CVaR: incorpora riesgo de cola en la funcion objetivo mediante `lambda` y `alpha`.
- SDDP: metodo de programacion dinamica estocastica con forward pass, backward pass, cortes y funcion de costo futuro.
- Unit Commitment: problema con decisiones binarias de encendido, rampas, minimos tecnicos y costos de arranque.

Esta base tecnica no debe usar "orden de encendido" ni "prender planta". La salida admisible es "Recomendacion de despacho y priorizacion termica" solo cuando existan datos suficientes.
