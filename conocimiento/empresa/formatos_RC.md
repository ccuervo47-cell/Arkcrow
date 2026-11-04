# Formatos de R&C Redes y Construcciones S.A.S.

Fuente: descripción de formatos entregada por el usuario (oct-2026). Plantillas en `plantillas/`.

## 2.1 APU (Análisis de Precio Unitario)

**Encabezado:**
- fecha;
- tipo de ítem (ítem de la propuesta económica o ítem no previsto);
- si es mínima cuantía (SI/NO);
- invitación N°;
- contrato N°;
- objeto;
- contratista;
- interventor;
- supervisor y cargo;
- ítem, descripción, unidad y cantidad.

**Capítulos de cada APU:**
1. **Maquinaria / Equipo:** descripción, tipo (alquiler o global), tarifa, rendimiento y valor unitario.
2. **Materiales:** descripción, unidad, cantidad, precio unitario y valor unitario.
3. **Transportes:** material, unidad, cantidad, distancia (km), cantidad × distancia, tarifa y valor unitario.
4. **Mano de obra:** descripción, jornal, prestaciones (**52 % del jornal**), jornal total, rendimiento y valor unitario.

**Cierre:** total costo directo y precio unitario aproximado al peso, con firmas de aprobación de la empresa que elabora y de la unidad gestora.

## 2.2 Memoria de cantidades

**Encabezado:**
- fecha (DD/MM/AA);
- corte N°;
- objeto del contrato;
- contratista y NIT/C.C.;
- representante del contratista;
- contrato N°;
- interventoría;
- capítulo e ítem;
- unidad.

**Cuerpo:**
- plano de referencia;
- filas con localización, largo, ancho, alto, cantidad y subtotal (los vanos se restan con valores negativos);
- tres fotografías;
- "viene memoria anterior", subtotal memoria y total memoria;
- validación.

**Código de colores del balance:**
- VERDE = memoria completa;
- ROJO = memoria faltante;
- AZUL = faltan fotos;
- MORADO = revisar.

## 2.3 Balance / Presupuesto

**Columnas:** ítem, descripción, unidad, cantidad, valor unitario, valor total, corte 01 y valor del corte.

**Capítulos base:**
1. Preliminares
2. Obra civil (mampostería, demolición, pañete y acabados)
3. Instalaciones eléctricas
4. Detección de incendios
5. Datos, redes y sonido
6. Dotaciones
7. Carpintería en madera
8. Carpintería metálica
9. Hidráulicas, sanitarias y gas
10. Aire acondicionado / extracción
11. Aseo
12. Ítems no previstos (NP-01, NP-02, …)

**AIU por defecto (configurable):**
- Administración 13 %;
- Imprevistos 3 %;
- Utilidad 8 %;
- IVA 19 % sobre la utilidad.

