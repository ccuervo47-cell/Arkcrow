---
name: bitacora-informe-diario
description: Registrar la bitácora diaria de obra (clima, personal, equipos, actividades, novedades, fotos), por texto o dictado de voz offline, y exportar el informe semanal en Word/PDF. Úsala cuando el usuario cuente qué pasó hoy en obra, dicte la bitácora o pida el informe semanal.
---

# Skill: Bitácora e informe diario/semanal

## Registrar el día
1. Pasa lo que cuenta el usuario a este formato (texto plano):
   ```
   Clima: mañana soleado, tarde lluvia 2 h
   Personal: 1 oficial, 3 ayudantes, 2 instaladores drywall (Empresa X)
   Equipos: 4 andamio multidireccional 8 h; 1 taladro 6 h
   Actividades:
   - 2.03 mampostería ejes 1 y 2, 18 m2, 50 %
   Novedades: ...
   Visitas: ...
   ```
2. Guarda el día con: `python skills/bitacora-informe-diario/scripts/run.py registrar <obra> --texto archivo.txt --fecha AAAA-MM-DD`.
   - Queda en `proyectos/<obra>/bitacora/AAAA-MM-DD.json`.
   - Si ya hay registro de ese día, se **agrega** al existente; nunca lo sobrescribe.
3. **Dictado de voz offline:** `... registrar <obra> --audio nota.m4a`. Usa Whisper local (modelo en `modelos/whisper-small`, que se descarga una sola vez con internet). Muéstrale al usuario la transcripción para que la confirme.

## Informe semanal
- Ejecuta `python skills/bitacora-informe-diario/scripts/run.py informe <obra> --semana AAAA-MM-DD`.
- Genera Word y PDF en `salidas/` con:
  - personal en hombres-día;
  - clima y horas de lluvia;
  - actividades con cantidad y avance;
  - equipos, novedades y visitas;
  - fotos y firmas.
- Pásalo por **revisor-calidad**.

## Reglas
- Las cantidades se reportan con su unidad.
- Si el usuario no da un dato, se deja vacío; no se inventa.
