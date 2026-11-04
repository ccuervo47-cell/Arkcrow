---
name: memoria-cantidades
description: Calcular cantidades de obra desde dimensiones, planos PDF o modelos IFC, restando vanos, y generar la hoja de memoria por ítem con espacio para tres fotos y semáforo. Úsala cuando el usuario pida cantidades, metrados, áreas de muro, memoria de cantidades o cuántos m²/ml/m³ hay.
---

# Skill: Memoria de cantidades

## Formato
- **Encabezado:** fecha (DD/MM/AA), corte N°, objeto, contratista, NIT/C.C., representante, contrato N°, interventoría, capítulo, ítem y unidad.
- **Cuerpo:** plano de referencia y filas con localización, largo, ancho, alto y cantidad. El subtotal es el producto de los valores llenos. Los **vanos van con cantidad negativa**.
- **Cierre:** tres fotografías, viene memoria anterior, subtotal (este corte), total memoria y semáforo.
- **Semáforo:** VERDE completa · ROJO faltante (total ≤ 0) · AZUL faltan fotos · MORADO marcada para revisar.

## Pasos
1. **Recintos rectangulares:** usa `python skills/memoria-cantidades/scripts/recinto.py --ext LxA --int LxA --alto H --vano "COD:ANCHOxALTO:puerta"`. Da las filas de placa, piso, mampostería (a ejes), acabados de dos caras, guardaescoba y la longitud de la viga de amarre. Con `--json` las da listas para `proyecto.json`.
2. **Planos PDF o IFC:** usa la skill `lectura-planos-bim` para extraer las dimensiones y luego el paso 1.
3. Pon las filas en `"memoria"` de cada ítem en `proyectos/<obra>/proyecto.json` y genera con `presupuesto-balance`.
4. Marca como **SUPUESTO** toda medida que no salga del plano (p. ej. una ventana sin cota). Queda en la hoja SUPUESTOS.

## Reglas
- La mampostería se mide a ejes. Pañetes, estucos y pinturas, por cara (interior y exterior), descontando el vano en cada cara.
- El guardaescoba descuenta el ancho de las puertas, no el de las ventanas.
- La unidad de la memoria se enlaza a la del APU. Nunca la escribas a mano.
