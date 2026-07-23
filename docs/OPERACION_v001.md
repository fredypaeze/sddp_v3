# Operación: "¿cuándo prendo la térmica?" (v001)

El modelo produce una **recomendación de despacho y priorización térmica** interpretable, con valores trazables a la ejecución (nunca inventados). Código: `src/minenergia_sddp/reporting/recomendacion.py`.

## Qué responde

Por etapa (mes): cuánta generación térmica esperada (GWh/día), cuánta hidráulica, el **valor del agua** (COP/kWh), el volumen esperado (%) y el **riesgo de ENS**. De ahí una **señal**:

- `aumentar_termica_conservar_agua` — cuando el valor del agua supera el umbral o hay riesgo de déficit: conviene apoyarse en térmica y conservar agua.
- `priorizar_hidro` — agua abundante y barata frente a térmica.
- `equilibrado` — entre ambos.

## Forma de la recomendación (conceptual)

> “Aumentar la generación térmica a ~X GWh/día en [mes] permite conservar agua (valor del agua Y COP/kWh, volumen esperado Z %), reduce el riesgo de ENS de la cola seca; el costo esperado del horizonte es E billones y el CVaR₉₅ es C billones.”

Todos los valores (X, Y, Z, E, C) provienen de una ejecución del SDDP (`outputs/run_024_v001/`), no de supuestos.

## Uso

`scripts/24_sddp.py` genera la política; `recomendacion_por_etapa` y `frase_recomendacion` la traducen; la API la expone en `/recomendacion` y el dashboard en la pestaña “Recomendación térmica”.

## Límite honesto

No es un “orden de encendido” por planta ni un despacho vinculante: es una **recomendación agregada** de cuánto apoyarse en térmica y cuánto conservar agua, condicionada a ENOS y al nivel del embalse. La decisión operativa por planta requiere datos por recurso (brecha) y validación institucional.
