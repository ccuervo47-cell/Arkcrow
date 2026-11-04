---
name: registro-fotografico
description: Organizar fotos de obra por fecha e ítem leyendo EXIF (fecha y GPS) y generar el anexo fotográfico para memorias, actas e informes. Úsala cuando el usuario pase fotos del celular, pida un anexo fotográfico o quiera saber qué ítems no tienen fotos.
---

# Skill: Registro fotográfico

1. **Organizar:** `python skills/registro-fotografico/scripts/run.py organizar <obra> <carpeta_fotos> [--item 2.03]`.
   - **Copia** las fotos (nunca mueve ni borra los originales) a `proyectos/<obra>/fotos/AAAA-MM-DD/<ítem>/`.
   - Toma el ítem del nombre del archivo (`2.03_muro.jpg`, `NP-01 cielo.jpg`) o de `--item`.
   - Lee la fecha y el GPS del EXIF. Si no hay EXIF, usa la fecha del archivo y lo marca.
2. **Anexo:** `... anexo <obra> [--item 2.03] [--desde AAAA-MM-DD] [--hasta AAAA-MM-DD]`. Genera Word y PDF con 2 fotos por fila y pie de foto (ítem, fecha, GPS).
3. **Semáforo:** `... contar <obra>` actualiza las fotos por ítem en `proyecto.json` (máximo 3). Al regenerar el balance, el semáforo pasa de AZUL a VERDE.

**Consejo para el usuario:** nombrar las fotos en el celular empezando por el ítem, por ejemplo "2.03 eje A".
