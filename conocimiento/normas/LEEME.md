# Normas: qué PDFs poner en esta carpeta

El asistente **solo cita normas que estén indexadas aquí**. Si una norma no está, lo dice y no la inventa.

Descargue los PDF oficiales con internet, guárdelos en esta carpeta y ejecute `iniciar` (o `python -m arkcrow.conocimiento indexar`).

| Norma | Archivo sugerido | Fuente oficial |
|---|---|---|
| NSR-10, Títulos A a K (mínimo A, D, E y J) | `NSR-10_Titulo_X.pdf` | Ministerio de Vivienda / Comisión Asesora Permanente para el Régimen de Construcciones Sismo Resistentes |
| RETIE (Res. 40117 de 2024 o vigente) | `RETIE.pdf` | Ministerio de Minas y Energía |
| RETILAP | `RETILAP.pdf` | Ministerio de Minas y Energía |
| RAS (Res. 0330 de 2017) | `RAS_Res0330_2017.pdf` | Ministerio de Vivienda |
| NTC 1500 Código Colombiano de Fontanería | `NTC1500.pdf` | ICONTEC (documento con licencia: usar la copia de la empresa) |
| NTC 4595 Planeamiento y diseño de instalaciones escolares | `NTC4595.pdf` | ICONTEC (con licencia) |
| Resolución 3100 de 2019 (habilitación de servicios de salud) | `Res3100_2019.pdf` | Ministerio de Salud y Protección Social |
| Decreto 1072 de 2015 (Libro 2, Parte 2, Título 4, Cap. 6: SG-SST) | `Dec1072_2015.pdf` | Ministerio del Trabajo |
| Resolución 0312 de 2019 (estándares mínimos SG-SST) | `Res0312_2019.pdf` | Ministerio del Trabajo |
| Resolución 4272 de 2021 (trabajo en alturas) | `Res4272_2021.pdf` | Ministerio del Trabajo |

**Consejos:**
- Prefiera los PDF con texto seleccionable. En un PDF escaneado no se puede buscar sin OCR.
- Para documentos de la obra (especificaciones, contratos, presupuestos), use `conocimiento/obras/<obra>/`.
- Lo que sea confidencial va en `conocimiento/confidencial/`, o con la palabra "CONFIDENCIAL" en el nombre del archivo. Nunca se envía a la nube sin su confirmación.
