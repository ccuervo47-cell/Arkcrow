---
name: presupuesto-balance
description: Armar el balance/presupuesto enlazado con fórmulas a memorias y APU, aplicar AIU y ejecutar el auditor automático. Úsala para presupuestos, balances, AIU, costo directo, valor total de obra o para auditar un Excel de costos.
---

# Skill: Presupuesto / Balance + Auditor

## Formato
- **Columnas:** ítem, descripción, unidad, cantidad, valor unitario, valor total, corte 01 (cantidad), valor corte y semáforo de memoria.
- **Capítulos base:** 1 Preliminares · 2 Obra civil · 3 Eléctricas · 4 Detección de incendios · 5 Datos, redes y sonido · 6 Dotaciones · 7 Carpintería en madera · 8 Carpintería metálica · 9 Hidrosanitarias y gas · 10 Aire acondicionado / extracción · 11 Aseo · 12 No previstos (NP-01…).
- **AIU (configurable en la hoja DATOS):** A 13 % · I 3 % · U 8 % · IVA 19 % sobre la utilidad.

## Cómo está armado el libro
`DATOS` (encabezados y parámetros) → `MEM x.xx` (cantidades) → `APU x.xx` (precios) → `BALANCE`. Cada dato vive en un solo lugar y todo lo demás lo enlaza con fórmulas. Por eso el balance nunca queda en cero ni con encabezados distintos entre hojas.

## Pasos
1. Crea o edita `proyectos/<obra>/proyecto.json`. Copia `plantillas/proyecto_plantilla.json` o el ejemplo `proyectos/sala-juntas-prueba/proyecto.json`.
2. Ejecuta `python skills/presupuesto-balance/scripts/armar_balance.py proyectos/<obra>/proyecto.json`. Genera el Excel, lo recalcula, lo audita y deja `_REVISION.md`.
3. Lee el reporte al usuario:
   - Los **ERRORES** bloquean la entrega.
   - Las **ADVERTENCIAS** se corrigen o se justifican.
   - Las **OBSERVACIONES TÉCNICAS** se consultan con él antes de cambiar el alcance.
4. Para auditar un Excel hecho a mano: `python skills/presupuesto-balance/scripts/auditar.py <archivo.xlsx>`.

## Qué revisa el auditor (memoria/lecciones.md)
- **R0** errores de fórmula.
- **R1** balance enlazado y sin ceros.
- **R1b** AIU correcto.
- **R2** unidades idénticas.
- **R3** encabezados llenos e iguales en todas las hojas.
- **R4** columnas de referencia enlazadas.
- **R5** sumas del APU y 52 % de prestaciones.
- **R6** transporte en todos los materiales.
- **R7** herramienta menor al 5–10 % de la MO.
- **T1** mortero de 3–5 cm.
- **T2** acero de 60–100 kg/m³ en placas.
- **T3** confinamiento NSR-10.
- **T4** pintura de cielo raso.
- **T5** suministro de puertas y ventanas.
- Semáforo de memorias y concentración anómala de costos.
