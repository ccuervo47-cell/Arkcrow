# Empresa: R&C Redes y Construcciones S.A.S.

- **Sede:** Bogotá.
- **Rol del usuario:** arquitecto residente de obra.
- **Líneas de trabajo vistas en los formatos:** obra civil, eléctricas, detección de incendios, datos/redes/sonido, dotaciones, carpinterías, hidrosanitarias y gas, aire acondicionado / extracción.

## AIU que usa la empresa (valores por defecto, configurables)

| Componente | Porcentaje | Base |
|---|---|---|
| Administración (A) | 13 % | sobre el costo directo |
| Imprevistos (I) | 3 % | sobre el costo directo |
| Utilidad (U) | 8 % | sobre el costo directo |
| IVA | 19 % | **sobre la utilidad** (no sobre el total) |

**Valor total** = costo directo + A + I + U + IVA sobre U. Equivale a un factor de ≈ 1,2552 sobre el costo directo.

**Prestaciones sociales en los APU:** 52 % del jornal.

## Formatos de la empresa
Las plantillas Excel con fórmulas vivas están en `plantillas/` y la descripción completa en `conocimiento/empresa/formatos_RC.md`.

1. **APU:**
   - Encabezado: fecha, tipo de ítem (propuesta económica / no previsto), mínima cuantía, invitación, contrato, objeto, contratista, interventor, supervisor y cargo, ítem, descripción, unidad y cantidad.
   - Capítulos: equipo, materiales, transportes y mano de obra.
   - Cierre: total costo directo, precio al peso y firmas.
2. **Memoria de cantidades:**
   - Encabezado con corte N° y NIT/C.C.
   - Filas con localización, largo, ancho, alto y cantidad; los vanos van en negativo.
   - Tres fotos, viene memoria anterior / subtotal / total, y validación.
   - **Semáforo:** VERDE completa · ROJO faltante · AZUL faltan fotos · MORADO revisar.
3. **Balance / presupuesto:**
   - Columnas: ítem, descripción, unidad, cantidad, valor unitario, valor total, corte 01 y valor del corte.
   - 12 capítulos base: preliminares, obra civil, eléctricas, detección de incendios, datos y sonido, dotaciones, carpintería en madera, carpintería metálica, hidrosanitarias y gas, aire / extracción, aseo, y no previstos (NP-01…).

## Cargos y jornales de referencia (prueba, oct-2026, POR ACTUALIZAR)

| Cargo | Jornal |
|---|---:|
| Arquitecto | 200.000 |
| Residente | 150.000 |
| Oficial | 60.000 |
| Instalador | 80.000 |
| Ayudante | 60.000 |
| Técnico electricista | 80.000 |

Equipos, materiales y transportes: `datos/arkcrow.sqlite` (tabla `insumos`).

## Contactos de trabajo
- **Arq. Sergio Arévalo:** Subdirección de Proyectos (supervisor en la prueba técnica).
- *(Agregar aquí contactos de obra, interventoría y proveedores. Solo nombre, cargo y canal de trabajo; nunca documentos de identidad.)*
