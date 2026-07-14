# Matriz de unidades

| Dominio | Variable | Unidad auditada | Conversion permitida | Estado |
|---|---|---|---|---|
| Precios | precio_oferta_cop_kwh | COP/kWh | ninguna; no usar COP/MWh en salidas | disponible con limitaciones |
| Precios | precio_bolsa | COP/kWh segun archivo heredado | ninguna; requiere confirmacion por metrica XM | disponible con limitaciones |
| Generacion | hidro_gwh, termo_gwh | GWh/dia agregado Sistema | suma temporal permitida | proxy admisible solo para backtesting |
| Generacion | hidro_kwh, termo_kwh | kWh/dia agregado Sistema | kWh / 1e6 = GWh | proxy admisible solo para backtesting |
| Termicas | capacidad_mw | MW | MW * horas / 1000 = GWh si existe capacidad validada | no disponible |
| Termicas | disponibilidad_mw | MW | MW * horas / 1000 = GWh si existe disponibilidad temporal validada | no disponible |
| Embalses | VolumenUtilPorcentaje | fraccion o porcentaje segun archivo | no convertir a GWh sin curva volumen-energia | disponible con limitaciones |
| Embalses | CapacidadUtilMasa, VolumenUtilDiarioMasa | masa/volumen local | no convertir a energia sin relacion tecnica | disponible con limitaciones |
| Aportes | Value, AportesPorc, AportesHidricosMasa | indice/masa/porcentaje segun fuente | no convertir a GWh sin factor tecnico | disponible con limitaciones |
| Costos | GWh x COP/kWh | miles de millones COP | GWh * 1e6 * COP/kWh / 1e9 | formula validada |
