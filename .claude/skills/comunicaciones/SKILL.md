---
name: comunicaciones
description: Redactar correos, oficios, actas de comité y solicitudes a interventoría o supervisión en tono profesional colombiano. Todo queda como BORRADOR y nunca se envía. Úsala cuando el usuario pida escribir, responder o solicitar algo por escrito.
---

# Skill: Comunicaciones (solo borradores)

- **Correo:** `python skills/comunicaciones/scripts/run.py correo <obra> --para "..." --asunto "..." --puntos "..." "..."`.
  Genera `.eml` (Outlook lo abre como borrador) y `.txt`.
- **Oficio:** `... oficio <obra> --para "..." --cargo "..." --asunto "..." --puntos ...`. Genera un .docx con la marca BORRADOR.
- **Acta de comité:** `... acta <obra> datos.json`. Incluye asistentes, orden del día, desarrollo y compromisos; ejemplo en `proyectos/sala-juntas-prueba/ejemplos/comite_01.json`.
- **Con modelo disponible:** `--redactar "instrucción"` hace que el modelo proponga el cuerpo, dejando [COMPLETAR] donde falten datos.

## Reglas
- **Nunca se envía nada.** Este módulo no tiene código de envío. Los borradores quedan en `proyectos/<obra>/borradores/`.
- **Tono:** profesional, cordial y concreto. Usa referencia al contrato, asunto claro y puntos numerados.
- **Datos:** no inventes fechas, valores ni compromisos. Lo que falte va como [COMPLETAR].
- **Confidencial:** si el texto incluye información confidencial, recuérdale al usuario antes de enviarlo por su cuenta.
