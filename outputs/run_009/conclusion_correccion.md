# Correccion de unidades XM run_009

Estado: **UNIT_FIX_VALIDATED_WITH_WARNINGS**

La normalizacion v2 conserva `Value`, registra `unit_catalog`, resuelve `unit_effective` desde `config/xm_unit_overrides.json` y deriva una sola columna compatible por metrica.

## DispoDeclarada

- Unidad catalogo: kWh
- Unidad efectiva: kW
- Columna anterior incorrecta: Value_GWh
- Columna nueva: Value_MW
- Conversion: Value_MW = Value / 1000
- Maximo corregido: 1240.0 MW

## Validacion de disponibilidades

- Recursos: 72
- Horas: 168
- Cobertura union: 12096 filas
- Inconsistencias registradas: 325

No se hicieron solicitudes HTTP ni descargas. No se modifica el catalogo local de XM ni los JSON crudos.
