# Alcance de la entrega — SDDP + CVaR v0.1.0

> **Esta versión es un prototipo analítico funcional y reproducible de SDDP + CVaR a nivel agregado. No constituye todavía una instrucción operativa oficial por planta, recurso o embalse.**

## Clasificación por componente

| Componente | Clasificación |
|---|---|
| Ingesta / validación / consolidación XM | Funcional |
| Datasets model-ready (GWh, COP/kWh) | Funcional |
| Despacho determinístico (LP HiGHS, balances, valor del agua) | Funcional |
| Pronóstico de aportes ENOS (SARIMAX+ONI vs. baselines) | Funcional |
| Generación/validación/reducción de escenarios (PAR/ARX(1)) | Funcional |
| **SDDP** (forward/backward, cortes de Benders, LB/UB, convergencia, checkpoints) | Funcional |
| **CVaR** integrado (anidado en los cortes, λ/α) | Funcional |
| Backtesting histórico por episodio ENOS | Funcional |
| API REST (FastAPI) | Funcional |
| Dashboard (Streamlit) | Funcional |
| Reproducibilidad (carpetas de run, semillas, hashes) | Funcional |
| Costos/capacidad térmica y precios | Funcional **con supuestos** (config-driven, no oficiales) |
| Otras fuentes / demanda climatológica | Funcional **con supuestos** |
| Recomendación térmica agregada | **Prototipo** (agregada, no por planta) |
| Topología hidráulica (cascadas) | **Prototipo** (validación `pendiente` vs. topología oficial) |
| Split hidro/térmico por tecnología | **Pendiente de validación institucional** (no hay generación por recurso) |
| Supuestos de costo/capacidad/precio | **Pendiente de validación institucional** |
| Actualización incremental de datos nuevos | **Fase posterior** (requiere catálogo maestro externo + red) |
| Regionalización / topología por embalse / escenarios de demanda / gas / unit commitment | **Fase posterior** |
| Escalamiento a GPU / mayor nº de escenarios | **Fase posterior** |

## Limitaciones aceptadas para esta entrega (declaradas, no bloqueantes)

- Embalse-equivalente **agregado** del SIN.
- Separación hidro-térmica **endógena** (la decide el optimizador).
- Costos, capacidades térmicas y precios **parcialmente basados en supuestos configurables**.
- Respuesta a **λ acotada** en el modelo agregado (usar λ ∈ [0, 0.5]).
- Datos históricos disponibles hasta **2026-07-13**.
- Actualización incremental **pendiente** del catálogo maestro externo.
- **Validación institucional pendiente.**

## Entorno de ejecución

Ejecutado en un **entorno aislado** dentro de la infraestructura disponible (4 vCPU, ~7.7 GB RAM, sin GPU). **No** se usaron las tres GPU NVIDIA L40S; el resultado **no depende de GPU** y las GPU **no son requisito** para v0.1.0. Una evaluación de escalamiento podrá realizarse posteriormente.
