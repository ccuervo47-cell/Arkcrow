---
name: lectura-planos-bim
description: Extraer cantidades de planos AutoCAD (DXF; DWG con ODA File Converter) por capa (m², ml, bloques), de modelos IFC (muros, vanos, puertas, ventanas, espacios, áreas) con ifcopenshell offline y de planos PDF (marcas P-/V-, cotas, áreas, escalas). Úsala cuando el usuario entregue un IFC exportado de Revit o un plano en PDF para sacar cantidades.
---

# Skill: Lectura de planos y BIM

## IFC (offline, ifcopenshell)
- **Resumen:** `python skills/lectura-planos-bim/scripts/run.py ifc modelo.ifc`. Da longitud, altura y espesor de muros, área bruta, vanos, área neta por cara, puertas, ventanas y espacios.
- **Filas para la memoria:** `... ifc modelo.ifc --memoria` las da listas para `proyecto.json` (skill `memoria-cantidades`).
- **De dónde salen las cantidades:** usa las base quantities del IFC si existen. Recomiéndale exportar desde Revit con "Export base quantities". Si no existen, las calcula de la geometría; esto vale para muros **rectos** (los curvos quedan con aviso).
- **Prueba:** con `proyectos/sala-juntas-prueba/ejemplos/sala_juntas_prueba.ifc` (sintético) da 37,935 m² de mampostería neta, 13,84 ml a ejes y 10,974 m² de piso, igual que la memoria.

## AutoCAD: DXF y DWG (offline)
- **Cantidades por capa:** `python skills/lectura-planos-bim/scripts/cad.py plano.dxf [--excel] [--memoria] [--capas "VERDE|ADOQUIN"] [--unidades mm|cm|m]`.
- **Qué mide en cada capa:**
  - **m²** de polilíneas cerradas y círculos, y aparte los **m² de sombreados** (restando los huecos);
  - **ml** de líneas, polilíneas abiertas, arcos y splines;
  - **conteo de bloques** por nombre (árboles, luminarias, bancas…);
  - textos y cotas.
- **Opciones:**
  - `--excel` genera la tabla de cantidades junto al plano;
  - `--memoria` da las filas para `proyecto.json` (skill `memoria-cantidades`).
- **Unidades:** salen de `$INSUNITS`. Si el plano no las trae, se deducen del tamaño del dibujo y se avisa; en ese caso **confírmalas con el usuario** o usa `--unidades`.
- **DWG:** se lee solo si está instalado **ODA File Converter** (gratuito). Si no, pide al usuario guardar el plano como DXF desde AutoCAD (`GUARDARCOMO` > AutoCAD DXF).
- **Base de conocimiento:** los DXF subidos a `conocimiento/` se indexan con un resumen por capa, así que el chat puede responder "¿cuántos árboles hay en el plano?" con cita de la capa.
- **Límites (avísalos siempre):**
  - las áreas dependen de que estén dibujadas como **polilíneas cerradas o sombreados**; las líneas sueltas solo suman ml;
  - las capas mal organizadas dan cantidades mezcladas;
  - no se leen referencias externas (xref) ni el espacio papel.
- **Prueba:** con el plano sintético `tests/dxf_prueba.py` da 53,14 m² de zona verde, 11 m² de adoquín, 15,14 ml de bordillo, 7 árboles y 3 luminarias.

## PDF de planos
`... pdf plano.pdf` extrae por página las marcas de puertas y ventanas, las áreas en m², las escalas y las cotas. Solo sirve en PDF vectoriales con texto; un PDF escaneado necesita OCR.

## Revit (opcional, no obligatorio)
- **pyRevit:** un script puede exportar tablas de planificación a CSV o IFC con base quantities. Es lo más simple y no requiere servidor.
- **Servidor MCP de Revit (comunitario):** permite consultar el modelo abierto desde un agente. Instálalo solo con aprobación de TI, porque requiere un complemento en Revit.
- En los dos casos, el flujo recomendado es exportar a IFC y usar esta skill; funciona sin Revit y sin internet.
