# Brechas de datos 2

- `demanda_oficial_sin`: FOUND_METADATA_ONLY - MetricId, URL y MaxDays son metadata; no contienen valores de demanda.
- `generacion_agregada`: FOUND_WITH_LIMITATIONS - No incluye solar, eolica, cogeneracion, importaciones, exportaciones ni otras fuentes desagregadas.
- `generacion_por_recurso`: FOUND_WITH_LIMITATIONS - Solo muestra de carbon por 7 dias; no cubre generacion por recurso de todo el SIN ni horizonte historico completo.
- `capacidad_termica`: FOUND_WITH_LIMITATIONS - Cubre carbon, no toda la flota termica gas/liquidos/biogas/biomasa/GLP/ACPM/JET-A1.
- `disponibilidad_termica`: FOUND_METADATA_ONLY - No existe disponibilidad fisica MW, indisponibilidad ni mantenimiento futuro. Horas con generacion no equivalen a disponibilidad.
- `relacion_volumen_energia`: MISSING_CRITICAL - No hay energia_almacenada_gwh, factor de conversion, productividad ni curva cota-volumen. No se puede calcular GWh conservados ni valor del agua COP/kWh.
- `almacenamiento_porcentaje`: FOUND_WITH_LIMITATIONS - Sirve como trayectoria indicativa, envolvente o indice; no representa energia almacenada GWh.
- `aportes_hidricos`: FOUND_WITH_LIMITATIONS - No es GWh. Permite escenarios relativos o indices, no balance hidrico energetico sin conversion tecnica.
- `escenarios_probabilidades`: FOUND_VALID - Probabilidades asociadas a trayectorias de volumen util, no a aportes energeticos.
- `limite_termico_agregado`: FOUND_WITH_LIMITATIONS - Suficiente solo para bloque carbon parcial; no representa gas, liquidos ni demas termicas.
- `precio_por_recurso`: FOUND_WITH_LIMITATIONS - No suple capacidad ni disponibilidad; requiere union por codigo.
- `codigo_union`: FOUND_WITH_LIMITATIONS - Valido para carbon; faltan homologaciones completas de otros combustibles.
- `combustible`: FOUND_WITH_LIMITATIONS - Combustible disponible como categoria; no incluye costos de combustible ni restricciones logisticas.