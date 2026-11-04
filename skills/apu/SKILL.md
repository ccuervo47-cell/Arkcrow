---
name: apu
description: Generar o revisar Análisis de Precio Unitario (APU) en el formato de R&C. Úsala cuando el usuario pida un APU, un precio unitario, una cuadrilla, rendimientos o consumos de un ítem, o quiera revisar un APU existente.
---

# Skill: APU (Análisis de Precio Unitario)

## Formato de la empresa
- **Encabezado:** fecha, tipo de ítem (propuesta económica / no previsto), mínima cuantía SI/NO, invitación N°, contrato N°, objeto, contratista, interventor, supervisor y cargo, ítem, descripción, unidad y cantidad.
- **Capítulos:**
  1. Maquinaria / equipo: tarifa ÷ rendimiento. La herramienta menor va como **% de la mano de obra (5–10 %)**.
  2. Materiales: cantidad × precio.
  3. Transportes: cantidad (t o m³) × distancia × tarifa. Va en **todos** los materiales; si el precio ya lo incluye, se marca "incluido".
  4. Mano de obra: jornal + **prestaciones del 52 %**, dividido por el rendimiento.
- **Cierre:** total costo directo, precio unitario aproximado al peso y firmas (elaboró / unidad gestora).

## Pasos
1. Busca los precios en `datos/arkcrow.sqlite` (tabla `insumos`). Si un insumo no existe, **dilo**. No inventes el precio: propón agregarlo marcado como SUPUESTO.
2. Toma los consumos y rendimientos de `templates/rendimientos_tipicos.md`. Son supuestos de práctica usual; márcalos así y pide los de la obra si existen.
3. Escribe el ítem en `proyectos/<obra>/proyecto.json` (sección `apu` con los códigos de insumo) y genera el libro con `python skills/presupuesto-balance/scripts/armar_balance.py proyectos/<obra>/proyecto.json`. Todo cálculo se hace con código, nunca de memoria.
4. Para revisar un APU existente, usa `python skills/presupuesto-balance/scripts/auditar.py <libro.xlsx>`. Revisa las sumas, las unidades, el 52 %, la herramienta menor y los transportes.
5. Termina siempre con **revisor-calidad**.

## APU en el formato UNAD F-14-3-5 (libro complementario)
Cuando faltan APU en un libro oficial de la UNAD:
1. Escribe la especificación JSON en `proyectos/<obra>/`. Ejemplo: `proyectos/corozal-2026/apu_faltantes.json`, con los precios nuevos marcados SUPUESTO y los insumos y rendimientos (und/día) por ítem.
2. Ejecuta `python -m arkcrow.apu_unad OFICIAL.xlsx especificacion.json salida.xlsx`.
3. Resultado: un libro **aparte** con la misma geometría (B32, M83, M85), una hoja PRECIOS y una hoja RESUMEN que compara contra el VU del balance.
4. **No modifiques el libro oficial con openpyxl:** borra logos, casillas y cuadros de texto. Los valores se pasan al oficial fila por fila.
5. **No "cuadres" rendimientos** para llegar al VU del balance. Reporta la diferencia y deja que el usuario decida.

## Reglas
- Las unidades del APU deben ser idénticas a las de la memoria y el balance.
- No pegues valores donde va una fórmula.
