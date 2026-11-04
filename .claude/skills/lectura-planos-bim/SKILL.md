---
name: lectura-planos-bim
description: Extraer información de modelos IFC (muros, vanos, puertas, ventanas, espacios, áreas) con ifcopenshell offline y de planos PDF (marcas P-/V-, cotas, áreas, escalas). Úsala cuando el usuario entregue un IFC exportado de Revit o un plano en PDF para sacar cantidades.
---

# Skill: Lectura de planos y BIM

## IFC (offline, ifcopenshell)
- **Resumen:** `python skills/lectura-planos-bim/scripts/run.py ifc modelo.ifc`. Da longitud, altura y espesor de muros, área bruta, vanos, área neta por cara, puertas, ventanas y espacios.
- **Filas para la memoria:** `... ifc modelo.ifc --memoria` las da listas para `proyecto.json` (skill `memoria-cantidades`).
- **De dónde salen las cantidades:** usa las base quantities del IFC si existen. Recomiéndale exportar desde Revit con "Export base quantities". Si no existen, las calcula de la geometría; esto vale para muros **rectos** (los curvos quedan con aviso).
- **Prueba:** con `proyectos/sala-juntas-prueba/ejemplos/sala_juntas_prueba.ifc` (sintético) da 37,935 m² de mampostería neta, 13,84 ml a ejes y 10,974 m² de piso, igual que la memoria.

## PDF de planos
`... pdf plano.pdf` extrae por página las marcas de puertas y ventanas, las áreas en m², las escalas y las cotas. Solo sirve en PDF vectoriales con texto; un PDF escaneado necesita OCR.

## Revit (opcional, no obligatorio)
- **pyRevit:** un script puede exportar tablas de planificación a CSV o IFC con base quantities. Es lo más simple y no requiere servidor.
- **Servidor MCP de Revit (comunitario):** permite consultar el modelo abierto desde un agente. Instálalo solo con aprobación de TI, porque requiere un complemento en Revit.
- En los dos casos, el flujo recomendado es exportar a IFC y usar esta skill; funciona sin Revit y sin internet.
