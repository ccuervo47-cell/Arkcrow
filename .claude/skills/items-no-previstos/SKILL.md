---
name: items-no-previstos
description: Crear ítems no previstos (NP-01, NP-02…) con su APU, memoria, justificación técnica y oficio de solicitud de aprobación en borrador. Úsala cuando aparezca una actividad que no está en el contrato o cuando el auditor detecte algo omitido.
---

# Skill: Ítems no previstos

1. Crea `proyectos/<obra>/np/solicitud_NN.json` (ejemplo en `proyectos/sala-juntas-prueba/np/solicitud_01.json`). Cada ítem lleva:
   - código `NP-xx`, descripción y unidad;
   - memoria y APU, en el mismo formato de `proyecto.json`;
   - `justificacion` (técnica y concreta) y `causa`.
2. Los insumos deben existir en la base de precios. Si falta uno, **dilo** y propón agregarlo marcado como SUPUESTO.
3. Ejecuta `python skills/items-no-previstos/scripts/run.py <obra> proyectos/<obra>/np/solicitud_NN.json`. Genera:
   - `NP_solicitud_NN_APU_Memoria_Balance_<fecha>.xlsx`: capítulo 12, AIU de la obra y auditado;
   - `Oficio_solicitud_NP_NN_BORRADOR_<fecha>.docx`: tabla de NP, valores, justificación y anexos.
4. El oficio es un **BORRADOR**: el usuario lo revisa, lo firma y lo envía él mismo.
5. **Normas en la justificación:** cita solo lo que esté en la base local (skill `normativa-co`). Si la norma no está, escribe "verificar en la norma" en lugar de un artículo.
