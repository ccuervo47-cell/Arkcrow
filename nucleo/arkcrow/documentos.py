"""Utilidades comunes: rutas de obra y documentos Word con el estilo de ARKCROW / R&C."""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from datetime import date
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

RAIZ = Path(__file__).resolve().parents[2]
AZUL = RGBColor(0x1F, 0x38, 0x64)


# ------------------------------------------------------------------ obras
def carpeta_obra(obra: str) -> Path:
    d = RAIZ / "proyectos" / obra
    d.mkdir(parents=True, exist_ok=True)
    return d


def salidas(obra: str) -> Path:
    d = carpeta_obra(obra) / "salidas"
    d.mkdir(exist_ok=True)
    return d


def cargar_proyecto(obra: str) -> dict:
    f = carpeta_obra(obra) / "proyecto.json"
    if not f.exists():
        raise FileNotFoundError(f"La obra '{obra}' no tiene proyecto.json ({f})")
    return json.loads(f.read_text(encoding="utf-8"))


def encabezado_obra(obra: str) -> dict:
    try:
        return cargar_proyecto(obra).get("encabezado", {})
    except FileNotFoundError:
        return {}


def fecha_co(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def pesos(x: float) -> str:
    return "$" + f"{x:,.0f}".replace(",", ".")


# ------------------------------------------------------------------ Word
def nuevo_documento(titulo: str, obra: str | None = None, borrador: bool = False, horizontal: bool = False) -> Document:
    doc = Document()
    sec = doc.sections[0]
    if horizontal:
        from docx.enum.section import WD_ORIENT
        sec.orientation = WD_ORIENT.LANDSCAPE
        sec.page_width, sec.page_height = sec.page_height, sec.page_width
    for m in ("left_margin", "right_margin"):
        setattr(sec, m, Cm(2))
    sec.top_margin = sec.bottom_margin = Cm(1.8)
    estilo = doc.styles["Normal"]
    estilo.font.name = "Arial"
    estilo.font.size = Pt(10)
    estilo.element.rPr.rFonts.set(qn("w:eastAsia"), "Arial")
    enc = encabezado_obra(obra) if obra else {}
    p = sec.header.paragraphs[0]
    p.text = (enc.get("contratista") or "R&C Redes y Construcciones S.A.S.") + \
             (f" · Contrato {enc['contrato']}" if enc.get("contrato") else "")
    p.runs[0].font.size = Pt(8)
    p.runs[0].font.color.rgb = RGBColor(0x59, 0x59, 0x59)
    if borrador:
        r = sec.header.add_paragraph().add_run("BORRADOR - NO ENVIADO - REQUIERE REVISIÓN Y FIRMA")
        r.bold = True
        r.font.size = Pt(9)
        r.font.color.rgb = RGBColor(0xC0, 0x00, 0x00)
    pie = sec.footer.paragraphs[0]
    pie.text = f"Generado con ARKCROW OBRA · {fecha_co(date.today())}"
    pie.runs[0].font.size = Pt(7)
    h = doc.add_paragraph()
    run = h.add_run(titulo.upper())
    run.bold = True
    run.font.size = Pt(13)
    run.font.color.rgb = AZUL
    h.alignment = WD_ALIGN_PARAGRAPH.CENTER
    return doc


def _sombra(celda, color="D9E1F2"):
    tcPr = celda._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), color)
    tcPr.append(shd)


def tabla(doc, encabezados: list[str], filas: list[list], anchos_cm: list[float] | None = None, tam=9):
    t = doc.add_table(rows=1, cols=len(encabezados))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(encabezados):
        c = t.rows[0].cells[i]
        c.text = ""
        r = c.paragraphs[0].add_run(str(h))
        r.bold = True
        r.font.size = Pt(tam)
        _sombra(c)
    for fila in filas:
        celdas = t.add_row().cells
        for i, v in enumerate(fila):
            celdas[i].text = ""
            r = celdas[i].paragraphs[0].add_run("" if v is None else str(v))
            r.font.size = Pt(tam)
    if anchos_cm:
        for fila in t.rows:
            for i, w in enumerate(anchos_cm):
                fila.cells[i].width = Cm(w)
    return t


def ficha(doc, pares: list[tuple[str, str]], tam=9):
    """Tabla de dos columnas etiqueta / valor."""
    t = doc.add_table(rows=0, cols=2)
    t.style = "Table Grid"
    for k, v in pares:
        c = t.add_row().cells
        c[0].text, c[1].text = "", ""
        r = c[0].paragraphs[0].add_run(k)
        r.bold = True
        r.font.size = Pt(tam)
        _sombra(c[0], "F2F2F2")
        c[1].paragraphs[0].add_run("" if v is None else str(v)).font.size = Pt(tam)
        c[0].width, c[1].width = Cm(5), Cm(12)
    return t


def subtitulo(doc, texto):
    p = doc.add_paragraph()
    r = p.add_run(texto)
    r.bold = True
    r.font.size = Pt(11)
    r.font.color.rgb = AZUL
    return p


def firmas(doc, nombres: list[tuple[str, str]]):
    doc.add_paragraph()
    t = doc.add_table(rows=2, cols=len(nombres))
    for i, (nombre, cargo) in enumerate(nombres):
        t.rows[0].cells[i].text = "\n\n______________________________"
        t.rows[1].cells[i].text = ""
        p = t.rows[1].cells[i].paragraphs[0]
        p.add_run(nombre or "").bold = True
        p.add_run(f"\n{cargo}" if cargo else "")
    return t


def a_pdf(docx: Path) -> Path | None:
    """Convierte a PDF con LibreOffice si está disponible (si no, devuelve None)."""
    from .recalculo import _soffice
    exe = _soffice()
    if not exe:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run([exe, f"-env:UserInstallation={Path(tmp, 'p').as_uri()}", "--headless", "--convert-to", "pdf",
                        "--outdir", str(docx.parent), str(docx)], capture_output=True, timeout=180)
    pdf = docx.with_suffix(".pdf")
    return pdf if pdf.exists() else None


def copiar_seguro(origen: Path, destino: Path) -> Path:
    """Copia sin sobrescribir: si existe, agrega sufijo _2, _3..."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    final, n = destino, 2
    while final.exists():
        final = destino.with_name(f"{destino.stem}_{n}{destino.suffix}")
        n += 1
    shutil.copy2(origen, final)
    return final
