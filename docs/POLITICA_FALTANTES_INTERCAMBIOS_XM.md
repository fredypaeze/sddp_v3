# Politica de faltantes en intercambios XM

Esta politica distingue ausencia de dato y cero. Un valor cero solo puede usarse si aparece explicitamente en la respuesta o si la estructura local auditada permite inferir un cero estructural de forma trazable.

## Estados horarios

- `REPORTED_VALUE`: existe valor horario numerico reportado por XM.
- `EXPLICIT_ZERO`: existe valor horario numerico igual a cero.
- `STRUCTURAL_ZERO_INFERRED`: la hora o el dia no trae valor dentro de una respuesta JSON valida y no vacia, y la matriz horaria evidencia reporte por eventos.
- `UNKNOWN_EMPTY_WINDOW`: la ventana completa respondio `Items: []`; no se convierte en cero.
- `UNKNOWN_MISSING_OR_INVALID`: falta informacion por estructura invalida, archivo no legible o llave horaria ausente.

## Regla adoptada

Para `importaciones_energia_sistema` y `exportaciones_energia_sistema`, los blancos horarios y dias omitidos dentro de una ventana valida con `Items` no vacio pueden tratarse como `STRUCTURAL_ZERO_INFERRED`.

La regla no aplica a ventanas completas `Items: []`. Esas ventanas permanecen como `UNKNOWN_EMPTY_WINDOW` y excluyen los dias afectados del dataset model-ready.

## Prohibiciones

- No imputar estadisticamente.
- No convertir una ventana vacia completa en cero sin evidencia independiente.
- No llamar observado a un cero inferido.
- No sobrescribir los datos crudos ni el dataset v1.

## Impacto

El dataset v2 conserva el valor original reportado y agrega columnas de estado e imputacion. Los balances diarios solo se calculan cuando las variables necesarias no contienen `UNKNOWN`.
