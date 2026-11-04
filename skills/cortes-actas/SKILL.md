---
name: cortes-actas
description: Elaborar actas de corte o de avance de obra con cantidades ejecutadas por corte, acumulados, % de avance, valor del corte con AIU y semáforo de memorias. Úsala para cortes de obra, actas parciales, avance financiero o cuánto se ha ejecutado.
---

# Skill: Cortes y actas de avance

1. **Requisito:** un libro de costos aprobado en `proyectos/<obra>/salidas/` (skill `presupuesto-balance`). De ahí salen el VU, las unidades y las cantidades contratadas.
2. Crea `proyectos/<obra>/cortes/corte_NN.json`:
   ```json
   {"corte": 2, "fecha": "2026-11-30", "desde": "2026-11-16", "hasta": "2026-11-30",
    "cantidades": {"2.04": {"cantidad": 35.87, "memoria": true, "revisar": false}},
    "observaciones": ["..."]}
   ```
   Las cantidades de cortes anteriores se toman solas de los archivos `corte_01`… anteriores.
3. Ejecuta `python skills/cortes-actas/scripts/run.py acta <obra> <N>`. Genera el Excel con fórmulas, lo pasa por el revisor y crea el PDF.
4. **Columnas:** cantidad del contrato, anterior, este corte, acumulado, % de avance, valores (anterior, corte y acumulado) y saldos. El AIU se aplica al corte y al acumulado.
5. **Semáforo:** VERDE completa · ROJO sin memoria · AZUL faltan fotos (menos de 3) · MORADO revisar.
6. **Alertas:**
   - Un acumulado mayor que lo contratado se pinta en rojo y queda en observaciones: hay que pedir la aprobación de mayores cantidades o tramitarlo como NP.
   - Un ítem que no esté en el contrato es un ERROR.
