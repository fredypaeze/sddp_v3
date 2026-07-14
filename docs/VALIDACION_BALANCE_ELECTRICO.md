# Validacion de balance electrico

La validacion no debe forzar una igualdad sin revisar definiciones XM.

Balance conceptual:

```text
generacion nacional
+ importaciones
- exportaciones
- consumos auxiliares u otros ajustes disponibles
≈ demanda SIN
+ perdidas o componentes aplicables
```

Metricas base:

- Generacion nacional: `Gene` por Sistema.
- Demanda SIN: `DemaSIN` diaria y `DemaReal` horaria como contraste.
- Importaciones: `ImpoEner` por Sistema.
- Exportaciones: `ExpoEner` por Sistema.
- Perdidas: si se requiere, revisar `PerdidasEner` en catalogo local antes de integrarla.

Validaciones posteriores:

- Alinear granularidad horaria/diaria antes de comparar.
- Conservar kWh original y derivar GWh.
- Documentar diferencias por definicion de demanda, generacion neta, fronteras y perdidas.
- No usar `hidro + termica` como demanda sin cuantificar solar, eolica, cogeneracion, importaciones, exportaciones y otras fuentes.

