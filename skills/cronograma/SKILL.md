---
name: cronograma
description: Programación de obra con diagrama de Gantt en Excel, ruta crítica (CPM) en fórmulas vivas y comparación programado vs. ejecutado a una fecha de corte. Úsala para cronogramas, Gantt, ruta crítica, atrasos o reprogramación.
---

# Skill: Cronograma

1. Crea `proyectos/<obra>/cronograma.json`:
   - `inicio` y `fecha_corte`;
   - actividades con `id`, `actividad`, `item`, `duracion` (días), `predecesoras` y `ejecutado` (0 a 1).
2. Saca las duraciones de los rendimientos de los APU (cantidad ÷ rendimiento ÷ cuadrillas) y márcalas como SUPUESTO.
3. Ejecuta `python skills/cronograma/scripts/run.py <obra>`. Genera `salidas/Cronograma_<fecha>.xlsx`.
4. **Qué calcula en el Excel, con fórmulas:**
   - inicio y fin temprano y tardío, holgura y si la actividad es crítica;
   - fechas, % programado al corte y desviación;
   - barras del Gantt: rojo = ruta crítica, azul = con holgura, columna amarilla = fecha de corte.
   Si el usuario cambia una duración en Excel, todo se recalcula.
5. **Limitaciones:**
   - días calendario y relaciones fin-comienzo sin desfase;
   - el Gantt muestra la duración total más 5 días; si la obra se alarga mucho, regenera el archivo.
6. **Al reportar:** da la ruta crítica, la fecha de terminación y las actividades con atraso de más del 10 %.
