---
name: calidad-sst-checklists
description: Generar listas de chequeo de calidad (recibo de mampostería, pañetes, enchapes, drywall, pintura, instalaciones) y SST (permiso de trabajo en alturas, inspección de andamios, charla de 5 minutos). Úsala para recibir obra, inspecciones o formatos de seguridad.
---

# Skill: Listas de chequeo de calidad y SST

1. `python skills/calidad-sst-checklists/scripts/run.py listar` muestra las listas disponibles.
2. `... generar <obra> <clave|todas|charla> --lugar "Eje A" [--tema alturas]` genera el Excel.
3. **Cómo funciona la hoja:**
   - Cada ítem se marca SI, NO o N.A.
   - Los ítems con ★ son críticos: un NO en ellos da **NO APROBADO** aunque el resto cumpla.
   - Calcula solo el % de cumplimiento y el resultado (APROBADO / CON OBSERVACIONES / NO APROBADO / PENDIENTE).
4. **Criterios:** son de práctica usual. Las tolerancias marcadas SUPUESTO se confirman con las especificaciones del proyecto.
5. **Normas:** las referencias a normas (Res. 4272/2021, RETIE, NSR-10) se verifican con `normativa-co` sobre la norma indexada. No cites artículos de memoria.
