---
name: normativa-co
description: Consultar normas colombianas (NSR-10, RETIE, RETILAP, RAS, NTC 1500, NTC 4595, Resolución 3100 de 2019, Decreto 1072 de 2015, Resolución 0312 de 2019, Resolución 4272 de 2021) citando SIEMPRE el documento y la página de la base local. Úsala ante cualquier pregunta normativa.
---

# Skill: Normativa colombiana

1. Ejecuta `python skills/normativa-co/scripts/consultar.py "pregunta"`. Busca **solo** en `conocimiento/normas/` y devuelve fragmentos con `[archivo, p. N]`.
2. Responde con base en esos fragmentos y cita cada dato con su etiqueta.
3. Si el script dice "No tengo <norma> en la base local", **no respondas de memoria**:
   - dilo tal cual;
   - indica qué PDF agregar (ver `conocimiento/normas/LEEME.md`);
   - si hay internet, propone dejar la tarea en la cola "cuando haya internet".
4. Distingue entre lo que dice la norma (citado) y tu interpretación (márcala como interpretación).
5. **Normativa hospitalaria** (el usuario tiene experiencia en ella): Resolución 3100 de 2019 y sus estándares de infraestructura. Siempre con cita.
