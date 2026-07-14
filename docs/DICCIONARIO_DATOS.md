# Diccionario de datos

| Variable | Definicion | Unidad | Estado |
|---|---|---|---|
| `fecha` | Fecha del periodo | fecha ISO | disponible con limitaciones |
| `escenario_id` | Identificador de escenario | texto | disponible con limitaciones |
| `probabilidad` | Probabilidad del escenario por fecha | 0-1 | disponible con limitaciones |
| `codigo_embalse` | Codigo de embalse | texto XM/local | disponible con limitaciones |
| `volumen_util` | Volumen util observado o proyectado | masa/porcentaje segun fuente | disponible con limitaciones |
| `energia_almacenada_gwh` | Energia almacenada equivalente | GWh | prohibido estimarla sin informacion adicional |
| `aporte` | Aporte hidrico | unidad no validada / indice | disponible con limitaciones |
| `generacion_gwh` | Generacion por recurso o agregado | GWh | proxy admisible solo para backtesting |
| `demanda_gwh` | Demanda electrica total | GWh | no disponible |
| `solar_gwh` | Generacion solar | GWh | no disponible |
| `eolica_gwh` | Generacion eolica | GWh | no disponible |
| `cogeneracion_gwh` | Cogeneracion | GWh | no disponible |
| `importacion_neta_gwh` | Importacion neta | GWh | no disponible |
| `capacidad_mw` | Capacidad efectiva por recurso | MW | no disponible |
| `disponibilidad_mw` | Disponibilidad temporal por recurso | MW | no disponible |
| `precio_oferta_cop_kwh` | Precio de oferta auditado | COP/kWh | disponible con limitaciones |
