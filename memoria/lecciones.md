# Lecciones de la prueba técnica (reglas de calidad del asistente)

Salen de la revisión de la prueba "Construcción de sala de juntas (habitación compacta) según planos Revit" (R&C, oct-2026). El auditor (`nucleo/arkcrow/auditor.py`) las verifica automáticamente.

| # | Regla | Cómo se verifica |
|---|---|---|
| 1 | El BALANCE **nunca** queda en cero. Se enlaza con fórmulas a la memoria (cantidades) y a los APU (precios). | R1, R1b |
| 2 | Las unidades son **idénticas** en APU, memoria y balance. | R2 |
| 3 | Los encabezados (objeto, contrato, contratista, fecha, corte, nombres y documentos) están llenos y son iguales en todas las hojas. | R3 |
| 4 | Las columnas de comparación contra precios de referencia están enlazadas, o se eliminan. | R4 |
| 5 | Criterios técnicos: mortero de nivelación de 3–5 cm; acero de 60–100 kg/m³ en placas; confinamiento de la mampostería según NSR-10 (columnetas y vigas de amarre); pintura de cielo raso; suministro de puertas y ventanas. | T1–T5 |
| 6 | El transporte se aplica de forma consistente a **todos** los materiales. | R6 |
| 7 | La herramienta menor es un **% de la mano de obra (5–10 %)**. | R7 |
