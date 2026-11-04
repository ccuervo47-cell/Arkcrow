"""Revisor de calidad: ÚLTIMA etapa obligatoria antes de entregar un archivo.

- .xlsx: recalcula todas las fórmulas, busca errores (#REF!, #DIV/0!...), y si es un libro de costos
        (tiene hoja BALANCE) ejecuta el auditor completo. Con --entregar, reemplaza el archivo por la
        versión recalculada (abre con valores en cualquier visor, celular incluido) sin perder fórmulas.
- .docx: verifica que abre, que no tiene marcadores sin llenar ({{...}}, XXX, POR DILIGENCIAR).
- .pdf : verifica que abre y cuenta páginas.

Uso: python -m arkcrow.revisor_calidad archivo [--entregar]
Código de salida 0 = aprobado, 1 = hay errores.
"""
from __future__ import annotations

import re
import shutil
import sys
import zipfile
from pathlib import Path

from openpyxl import load_workbook

from . import auditor
from .recalculo import recalcular

MARCADORES = re.compile(r"\{\{.*?\}\}|\bXXX\b|POR DILIGENCIAR|\[\s*completar\s*\]", re.I)


def revisar_xlsx(ruta: Path, entregar: bool) -> tuple[bool, str]:
    copia = recalcular(ruta)
    wf = load_workbook(ruta)
    n_form = sum(1 for ws in wf for f in ws.iter_rows() for c in f if isinstance(c.value, str) and c.value.startswith("="))
    if "BALANCE" in wf.sheetnames:
        res = auditor.auditar(ruta, copia)
        md = auditor.reporte_md(res)
        ok = res.aprobado
    else:
        wv = load_workbook(copia, data_only=True)
        errores = [f"{ws.title}!{c.coordinate} = {c.value}" for ws in wv for f in ws.iter_rows() for c in f
                   if isinstance(c.value, str) and c.value.startswith(auditor.ERRORES_EXCEL)]
        ok = not errores
        md = "# Revisión de calidad\n\n" + (f"- {len(errores)} celdas con error:\n" + "\n".join(f"  - {e}" for e in errores[:50])
                                           if errores else "- ✔ Sin errores de fórmula.")
    md += f"\n\n*Fórmulas en el libro: {n_form}. Recalculado con motor externo antes de revisar.*\n"
    if entregar and ok:
        wc = load_workbook(copia)
        n_copia = sum(1 for ws in wc for f in ws.iter_rows() for c in f if isinstance(c.value, str) and c.value.startswith("="))
        if n_copia == n_form:   # solo se reemplaza si la versión recalculada conserva todas las fórmulas
            shutil.copy(copia, ruta)
            md += "*El archivo entregado ya incluye los valores calculados (fórmulas intactas).*\n"
    return ok, md


def revisar_docx(ruta: Path) -> tuple[bool, str]:
    try:
        with zipfile.ZipFile(ruta) as z:
            xml = z.read("word/document.xml").decode("utf-8", "ignore")
    except Exception as e:  # noqa: BLE001
        return False, f"# Revisión de calidad\n\n- ❌ El documento no abre: {e}\n"
    texto = re.sub(r"<[^>]+>", "", xml)
    marcas = sorted(set(MARCADORES.findall(texto)))
    if marcas:
        return False, "# Revisión de calidad\n\n- ❌ Marcadores sin llenar: " + ", ".join(marcas) + "\n"
    return True, "# Revisión de calidad\n\n- ✔ El documento abre y no tiene marcadores sin llenar.\n"


def revisar_pdf(ruta: Path) -> tuple[bool, str]:
    datos = ruta.read_bytes()
    if not datos.startswith(b"%PDF"):
        return False, "# Revisión de calidad\n\n- ❌ El archivo no es un PDF válido.\n"
    paginas = len(re.findall(rb"/Type\s*/Page[^s]", datos))
    return paginas > 0, f"# Revisión de calidad\n\n- {'✔' if paginas else '❌'} PDF con {paginas} página(s).\n"


def revisar(ruta: str | Path, entregar: bool = False) -> tuple[bool, str, Path]:
    ruta = Path(ruta)
    ext = ruta.suffix.lower()
    if ext in (".xlsx", ".xlsm"):
        ok, md = revisar_xlsx(ruta, entregar)
    elif ext == ".docx":
        ok, md = revisar_docx(ruta)
    elif ext == ".pdf":
        ok, md = revisar_pdf(ruta)
    else:
        raise ValueError(f"Tipo de archivo no soportado: {ext}")
    reporte = ruta.with_name(ruta.stem + "_REVISION.md")
    reporte.write_text(md, encoding="utf-8")
    return ok, md, reporte


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("Uso: python -m arkcrow.revisor_calidad archivo [--entregar]")
    ok, md, rep = revisar(sys.argv[1], "--entregar" in sys.argv)
    print(md)
    print(f"\n{'APROBADO' if ok else 'NO APROBADO'} - reporte: {rep}")
    sys.exit(0 if ok else 1)
