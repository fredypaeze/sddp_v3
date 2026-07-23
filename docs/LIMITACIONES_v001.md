# Limitaciones (v001)

Honestidad técnica (encargo §32). Este es un **prototipo técnico reproducible**, no un sistema productivo institucional.

## Datos

- Sin **generación por tecnología** clasificada: el split hidro/térmico es endógeno (lo decide el optimizador), no validado contra observación. Los hallazgos históricos (78.5 % hidro, −0.611 correlación) **no** son validables con los datos transferidos.
- Sin **capacidad/disponibilidad térmica MW** de la flota ni **precios de oferta** históricos: se usan **supuestos config-driven** (costo térmico = proxy del precio de bolsa por fase ENOS; capacidad térmica supuesta). No son cifras oficiales.
- **Aportes solo a nivel SIN agregado** (no por embalse): justifica la granularidad de embalse-equivalente.
- **ONI futuro** más allá del último dato se mantiene constante.

## Modelo

- **Embalse-equivalente agregado**: no representa cadenas hidráulicas ni restricciones por planta.
- **Independencia por etapa** de los aportes (supuesto estándar del SDDP); la persistencia se conserva solo en las trayectorias de validación.
- **Demanda determinística** (climatología); sin escenarios de demanda.
- **CVaR anidado**: la respuesta a λ es limitada en el embalse agregado y λ=1 es sobre-conservador (usar λ∈[0,0.5]).
- **UB del SDDP** es un estimador Monte Carlo (ruido).

## Alcance

- No es Unit Commitment (sin binarias, rampas, mínimos técnicos, arranque).
- No hay restricciones explícitas de gas/combustible (datos ausentes).
- La recomendación es **agregada**, no un orden de encendido por planta, y **requiere validación institucional**.

## Cómputo

- Servidor de 4 vCPU / 8 GB (no el host L40S descrito): limita nº de escenarios/estados. La GPU no acelera el LP; se reserva para pronóstico/reducción si se escala.

## Qué se requiere para producción

Generación por recurso + capacidad/disponibilidad MW + precios oficiales; validación de topología por embalse; escenarios de demanda; integración de gas; validación institucional de supuestos y recomendaciones; actualización incremental con las fuentes externas montadas.
