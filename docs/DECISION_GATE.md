# Puerta de calidad de datos

Estado asignado: **BLOCKED_CRITICAL_DATA**

## Razones

- No hay demanda oficial local ni desagregacion de solar, eolica, cogeneracion, importaciones u otras fuentes para reconstruir balance electrico.
- La generacion historica disponible esta agregada a Sistema en hidro_gwh y termo_gwh; no permite recomendacion por recurso.
- No hay capacidad_mw ni disponibilidad_mw temporal por recurso termico en los archivos auditados.
- embalses_manu proyecta volumen util/porcentaje mensual; no existe relacion tecnica auditada para convertir volumen util o masa a energia almacenada GWh.
- Las trayectorias proyectadas de volumen no son aportes hidricos exogenos ni pueden fijarse como almacenamiento endogeno del despacho.

## Implicacion

No se construye optimizador ni se emiten recomendaciones operativas. Se completan arquitectura, contratos, trazabilidad, adaptadores y pruebas de datos. La formulacion matematica queda documentada como especificacion condicionada a recibir datos faltantes.
