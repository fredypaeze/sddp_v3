# Correccion unidad DispoDeclarada

## Dato reportado por catalogo

- MetricId: `DispoDeclarada`
- Entidad: `Recurso`
- Target: `disponibilidad_declarada_recurso`
- Unidad catalogo: `kWh`

El catalogo local se conserva sin cambios. La correccion se aplica como override trazable en `config/xm_unit_overrides.json`.

## Descripcion y evidencia

La descripcion oficial asociada a `DispoDeclarada` corresponde a potencia neta declarada. Las respuestas reales del piloto `outputs/run_008`, periodo 2026-06-01 a 2026-06-07, muestran magnitudes y comportamiento horario comparables con:

- `CapEfecNeta` en kW
- `DispoReal` en kW
- `DispoCome` en kW

Ejemplo validado para el recurso `2QEK`, 2026-06-01:

- `CapEfecNeta`: 35.000 kW = 35 MW
- `DispoReal`: 35.000 kW = 35 MW
- `DispoCome`: 35.000 kW = 35 MW
- `DispoDeclarada`: 35.000 por hora = 35 MW

Maximos observados en el piloto:

- `CapEfecNeta`: 1.250.000
- `DispoReal`: 1.240.000
- `DispoCome`: 1.240.000
- `DispoDeclarada`: 1.240.000

## Decision tecnica

Para `disponibilidad_declarada_recurso` exclusivamente, la unidad efectiva es `kW`, aunque la unidad catalogo siga siendo `kWh`.

Formula:

```text
Value_MW = Value / 1000
```

El normalizador conserva:

- `Value` original
- `unit_catalog = kWh`
- `unit_effective = kW`
- `unit_override_applied = true`
- `override_reason`

La columna `Value_GWh` no debe generarse para `DispoDeclarada`.

## Riesgo de tratar potencia como energia

Tratar `DispoDeclarada` como energia subestima o distorsiona la disponibilidad: `1.240.000 kW` no es `0,00124 GWh`; representa `1.240 MW` de potencia disponible en esa hora.

No se deben sumar MW entre horas como si fueran energia. Para convertir disponibilidad horaria en energia maxima del intervalo:

```text
energia maxima del intervalo = potencia disponible x duracion del intervalo
```

Para una hora:

```text
MWh = MW x 1 h
GWh = MWh / 1000
```

Esta correccion no afecta precios. Las unidades de precios en `COP/kWh` se mantienen como precios, no como energia ni potencia.
