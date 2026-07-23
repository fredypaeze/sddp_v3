# Topología hidráulica (v001)

Catálogo trazable de los **24 embalses** del SIN presentes en los datos XM, con cuenca, región, tipo y relaciones de cascada. Fuente de atributos: `config/model/topologia_hidraulica.json`; construcción y cruce con datos: `src/minenergia_sddp/topology/catalog.py`.

## Alcance y honestidad

- **Cuenca / región / tipo**: hechos públicos sectoriales (confianza alta en la mayoría).
- **Cascadas (aguas arriba/abajo)**: solo se registran las **bien establecidas**; el resto queda `null` y **no se inventa** (regla de la §14 del encargo).
- **Validación**: `pendiente` para todas las relaciones — aún **no** verificadas contra la topología oficial XM/UPME. No usar como fuente oficial.

## Entidades

24 embalses; todos con capacidad/volumen energéticos observados (GWh). Mayores por capacidad útil media: **PEÑOL (~4114 GWh)**, AGREGADO BOGOTÁ (~3973), GUAVIO (~1983), ESMERALDA (~1102), EL QUIMBO (~1089).

## Cascadas registradas (confianza)

| Origen | → Aguas abajo | Confianza |
|---|---|---|
| EL QUIMBO | BETANIA | alta |
| PORCE II | PORCE III | alta |
| CHUZA | GUAVIO | media |
| ESMERALDA | GUAVIO | media |
| PEÑOL | SAN LORENZO | media |

## Uso en el modelo

El SDDP opera sobre el **embalse-equivalente agregado** del SIN (los aportes solo existen a nivel agregado; ver auditoría §5). Este catálogo es la base para una futura **regionalización** (agrupar embalses por cuenca/región) y para interpretar qué cadenas explican el riesgo. La salida tabular se genera en `outputs/run_021_v001/` (`catalogo_topologia.csv`, `relaciones_cascada.csv`).

## Próximo paso

Validar cuencas y cascadas contra el catálogo oficial `ListadoRecursos`/topología XM (requiere el maestro externo, hoy no montado — ver auditoría §5.7) y, de ser viable, construir un modelo por regiones con aportes desagregados.
