# Reporte del auditor ARKCROW

- **Archivo:** `SalaJuntas_APU_Memoria_Balance_2026-11-04.xlsx`
- **Fecha de revisión:** 04/11/2026 13:14
- **Resultado:** ✅ APROBADO (sin errores)
- **Hallazgos:** 0 errores · 3 advertencias · 4 observaciones técnicas · 0 informativos

## Resumen económico

| Concepto | Valor |
|---|---:|
| Costo directo | $9.722.027 |
| Administración | $1.263.864 |
| Imprevistos | $291.661 |
| Utilidad | $777.762 |
| IVA sobre utilidad | $147.775 |
| **Valor total** | $12.203.089 |

## ADVERTENCIA (3)

- **[R3 Encabezados]** `DATOS!B13`: Campo «NIT / C.C. contratista» sin dato real: «POR DILIGENCIAR».
  - *Qué hacer:* Completar antes de entregar.
- **[R3 Encabezados]** `DATOS!B14`: Campo «Representante del contratista» sin dato real: «POR DILIGENCIAR».
  - *Qué hacer:* Completar antes de entregar.
- **[Semáforo de memorias]** `MEM!-`: AZUL: 9 ítem(s), faltan fotografías: 2.01, 2.02, 2.03, 2.04, 2.05, 2.06, 2.07, 2.08, 2.09.
  - *Qué hacer:* Cargar las 3 fotografías por ítem antes del corte.

## OBSERVACIÓN TÉCNICA (4)

- **[T3 Confinamiento NSR-10]** `BALANCE!B14`: Hay mampostería (ítem 2.03) pero no hay ítems de columnetas ni vigas de amarre/confinamiento. Orden de magnitud: viga de amarre en la corona ≈ 13,84 ml; columnetas en las 4 esquinas, en los bordes de los 2 vanos y en tramos largos.
  - *Qué hacer:* Incluir columnetas y vigas de amarre según NSR-10 (Título D mampostería confinada; si son muros no estructurales, cap. A.9 elementos no estructurales). Verificar con la norma indexada y el diseño.
- **[T4 Pintura de cielo raso]** `BALANCE!B18`: Hay cielo raso (10,97 m²) pero no hay ítem de pintura de cielo raso.
  - *Qué hacer:* Agregar pintura de cielo (vinilo tipo 1, 2-3 manos) o indicar que el ítem de cielo la incluye.
- **[T5 Puertas y ventanas]** `BALANCE!-`: Las memorias descuentan vanos de puerta (P-101) pero el presupuesto no incluye su suministro e instalación.
  - *Qué hacer:* Agregar ítem de suministro e instalación de puertas (carpintería en madera/metálica) o dejar constancia de que lo suministra el contratante.
- **[T5 Puertas y ventanas]** `BALANCE!-`: Las memorias descuentan vanos de ventana (V-39 (1,50 x 1,20 m)) pero el presupuesto no incluye su suministro e instalación.
  - *Qué hacer:* Agregar ítem de suministro e instalación de ventanas (carpintería en madera/metálica) o dejar constancia de que lo suministra el contratante.

## Verificaciones superadas

- ✔ Ninguna celda con errores de fórmula (#REF!, #DIV/0!, #VALUE!, #NAME?...).
- ✔ Los 9 ítems del balance toman la cantidad de su MEMORIA y el valor unitario de su APU por fórmula.
- ✔ Ningún ítem del balance tiene cantidad, valor unitario o total en cero.
- ✔ El costo directo ($9.722.027) es igual a la suma de los ítems.
- ✔ AIU aplicado y verificado: A 13%, I 3%, U 8%, IVA s/U 19% → total $12.203.089.
- ✔ Unidades idénticas en APU, memoria y balance para todos los ítems.
- ✔ Prestaciones sociales = 52 % del jornal en todas las cuadrillas.
- ✔ Herramienta menor calculada como % de la mano de obra (5-10 %) en todos los APU.
- ✔ Los 9 APU suman bien: renglones → subtotales → costo directo → precio al peso.
- ✔ Transporte aplicado de forma consistente a todos los materiales (misma distancia: 20 km; premezclados marcados 'incluido').
- ✔ T1 Mortero de nivelación ítem 2.02: e = 4 cm, dentro del rango usual 3-5 cm.
- ✔ T2 Cuantía de acero ítem 2.01: 80 kg/m³, dentro del rango usual 60-100 kg/m³.

---
*Reglas tomadas de `memoria/lecciones.md` (revisión de la prueba técnica). Las observaciones técnicas son alertas de criterio: confirmar contra la norma indexada y el diseño antes de modificar.*

*Fórmulas en el libro: 848. Recalculado con motor externo antes de revisar.*
*El archivo entregado ya incluye los valores calculados (fórmulas intactas).*
