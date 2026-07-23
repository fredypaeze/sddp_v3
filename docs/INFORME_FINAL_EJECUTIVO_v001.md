# Informe final ejecutivo — SDDP + CVaR (v001)

## Qué había

Un repositorio sólido de **datos de XM** (histórico del sistema, hidrología por embalse, validaciones y puertas de calidad), pero **sin un modelo de optimización**: no existían despacho, escenarios, SDDP, medida de riesgo ni tablero.

## Qué se completó

Un **modelo hidro-térmico estocástico completo y reproducible** que decide cómo usar el agua embalsada y la generación térmica durante los próximos 6 meses, considerando el clima (El Niño / La Niña):

- Pronóstico de aportes condicionado a ENOS (mejor que los métodos simples).
- Generación de escenarios climáticos coherentes con la historia.
- **SDDP** (programación dinámica estocástica) con **cortes de Benders** y **valor del agua**.
- **CVaR**: medida de riesgo para proteger contra los peores escenarios de sequía.
- Backtesting histórico, **API** y **tablero** de consulta.

## Qué hace y qué resultados entrega

Responde, con cifras trazables (no inventadas):

- **¿Cuánto costará operar el sistema los próximos 6 meses?** Bajo El Niño, ≈ **6.55 billones de COP** esperados (coincide con el dato histórico de referencia ~6.36 billones).
- **¿Cuál es el riesgo en los peores escenarios?** El CVaR cuantifica la cola: hoy, con el embalse al **79 %**, el riesgo de déficit es **prácticamente nulo**; en un escenario de estrés (embalse bajo + El Niño) el costo de cola sube a ~**13 billones**.
- **¿Cuándo conviene encender más térmica y conservar agua?** El modelo lo indica por mes, con el **valor del agua** asociado.
- **¿Qué ganamos con una buena política?** En un backtest de estrés bajo El Niño, la gestión del SDDP **evitó un déficit de 2 205 GWh** que una regla simple no evitó, **ahorrando 2.38 billones de COP**.

## Cómo se usa

- Ejecutar los scripts del pipeline (pronóstico → escenarios → SDDP → sensibilidad → backtesting).
- Consultar resultados por **API** (`/riesgo`, `/recomendacion`, …) o por el **tablero** Streamlit.

## Qué NO debe interpretarse como recomendación automática

Es una **herramienta de apoyo**, no un despacho vinculante ni un “orden de encendido” por planta. Varios insumos (costos y capacidad térmica, precios) son **supuestos documentados**, no datos oficiales; deben validarse institucionalmente antes de usarse en decisiones reales.

## Qué falta para producción institucional

Generación por tecnología y capacidad/disponibilidad térmica reales, precios oficiales, topología por embalse validada, escenarios de demanda, integración de restricciones de gas, y actualización automática de datos (hoy limitada por un catálogo externo no montado). Con eso, el prototipo puede evolucionar a un sistema de apoyo a la operación.

## Qué decisiones soporta

Cuándo conservar agua vs. usar térmica; cuánto cuesta aumentar la seguridad energética; qué tan expuestos estamos a un El Niño; y cómo cambia todo según la aversión al riesgo (parámetro de política pública λ).

## Estado de validación

Se realizó una **auditoría de aceptación** antes de integrar el trabajo: todas las pruebas pasan, los balances de energía y agua se cumplen exactamente, el modelo y su medida de riesgo están validados, y la aplicación (API + tablero) funciona. El resultado es **APTO PARA MERGE** (revisión y fusión a cargo del equipo). Detalle en `docs/ACTA_VALIDACION_PRE_MERGE_v001.md`.
