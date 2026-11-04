---
name: revisor-calidad
description: Última etapa OBLIGATORIA antes de entregar cualquier Excel, Word o PDF. Abre el archivo, recalcula fórmulas, verifica totales y reporta errores. Úsala siempre antes de decir "listo" o de entregar un archivo.
---

# Skill: Revisor de calidad

## Pasos
1. Ejecuta `python skills/revisor-calidad/scripts/revisar.py <archivo> --entregar`.
2. Qué hace según el tipo de archivo:
   - **.xlsx:** recalcula con LibreOffice (o con Excel en Windows) y busca #REF!, #DIV/0!, #VALUE! y #NAME?. Si el libro tiene BALANCE, corre el auditor completo. Con `--entregar`, el archivo queda con los valores calculados y conserva todas las fórmulas.
   - **.docx:** verifica que abra y que no queden marcadores sin llenar ({{...}}, XXX, POR DILIGENCIAR).
   - **.pdf:** verifica que abra y cuenta las páginas.
3. Si el resultado es **NO APROBADO**, no entregues el archivo: corrige y vuelve a revisar.
4. Muéstrale al usuario el resumen de `<archivo>_REVISION.md`.

## Requisito
Un motor de cálculo: LibreOffice (sirve la versión portable, sin permisos de administrador) o Excel con `pywin32`.
