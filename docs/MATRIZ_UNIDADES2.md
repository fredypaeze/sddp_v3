# Matriz de unidades 2

| Dato | Unidad real auditada | Conversion permitida |
|---|---|---|
| Demanda DemaReal | kWh en metadata XM | no hay serie local para convertir |
| Generacion agregada | kWh/GWh | kWh / 1e6 = GWh |
| Generacion carbon por recurso | kWh/MWh | MWh / 1000 = GWh |
| Capacidad carbon | MW | MW * horas / 1000 = GWh maximo teorico del bloque carbon |
| Disponibilidad | categoria/horas observadas | no convertir a MW disponible |
| Embalses | masa/porcentaje/fraccion | no convertir a GWh sin factor tecnico |
| Aportes | indice, masa o porcentaje | no convertir a GWh sin factor tecnico |
| Probabilidad | 0-1 | suma por fecha debe ser 1 |

Columnas de energia en embalses: ['VertimientosEnergia', 'VertimientosEnergia_sum'].
Columnas GWh directas en embalses: [].
Columnas de factor/productividad/conversion: [].
