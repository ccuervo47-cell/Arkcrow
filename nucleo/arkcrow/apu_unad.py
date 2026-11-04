"""Genera APU en la geometría del formato UNAD F-14-3-5, en un libro APARTE (no modifica el oficial).

Por qué aparte: el formato oficial trae logos, casillas de verificación y cuadros de texto que openpyxl borraría.
El libro generado conserva las mismas posiciones (ítem en B32, secciones en las filas 37/49/66/76, costo directo en
M83 y precio en M85), así que los valores se pueden pasar al formato oficial fila por fila.

Entradas:
  - el libro oficial (para leer BALANCE: descripción, unidad, cantidad y VU; y PRECIOS existentes)
  - una especificación JSON con precios nuevos (SUPUESTOS) e insumos/rendimientos por ítem
Convenciones:
  - Rendimiento en la especificación = unidades por día de la cuadrilla. En la hoja se escribe como el formato UNAD:
    días por unidad (K = 1 / rendimiento).
  - Herramienta menor = % de la mano de obra (lección de la prueba técnica).
  - Transporte: fracción de viaje = Σ(cantidad × peso en t) / capacidad del camión; los materiales "puestos en obra"
    se marcan como transporte incluido.

Uso:
  python -m arkcrow.apu_unad OFICIAL.xlsx especificacion.json salida.xlsx          (genera los APU)
  python -m arkcrow.apu_unad plantilla OFICIAL.xlsx especificacion.json plantilla.xlsx   (para llenar cotizaciones)
  python -m arkcrow.apu_unad cotizar especificacion.json cotizaciones_llenas.xlsx   (guarda las cotizaciones)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Font, PatternFill

from .libro_costos import BORDE, F_NEGRITA, F_NORMAL, F_TITULO, MONEDA, RELLENO_CAP, RELLENO_SUB, RELLENO_TITULO, \
    RELLENO_TOTAL, _c

AMARILLO = PatternFill("solid", fgColor="FFF2CC")
FILAS = {"EQ": (37, 43), "MAT": (49, 60), "TR": (66, 70), "MO": (76, 80)}
BLOQUES = {"EQ": ("B", "H", "I"), "MAT": ("K", "R", "S"), "TR": ("U", "Z", "AA"), "MO": ("AC", None, "AJ")}


def leer_oficial(ruta: Path) -> tuple[dict, dict]:
    wv = load_workbook(ruta, data_only=True)
    b = wv["BALANCE"]
    items = {}
    for r in range(1, b.max_row + 1):
        cod = b[f"B{r}"].value
        if cod is not None and "." in str(cod) and b[f"D{r}"].value:
            items[str(cod).strip()] = {"desc": b[f"C{r}"].value, "und": b[f"D{r}"].value, "cant": b[f"E{r}"].value,
                                       "vu": b[f"F{r}"].value}
    p = wv["PRECIOS "] if "PRECIOS " in wv.sheetnames else wv["PRECIOS"]
    precios = {k: [] for k in BLOQUES}
    for k, (cd, cu, cp) in BLOQUES.items():
        for r in range(4, p.max_row + 1):
            d = p[f"{cd}{r}"].value
            if d and p[f"{cp}{r}"].value is not None:
                precios[k].append([str(d).strip(), p[f"{cu}{r}"].value if cu else None, p[f"{cp}{r}"].value, "PRECIOS oficial"])
    return items, precios


def construir(oficial: str | Path, spec: dict, salida: str | Path) -> Path:
    items, precios = leer_oficial(Path(oficial))
    fuente = spec.get("fuente_supuesto", "SUPUESTO - cotizar")
    cotizados = {_k(d): c for d, c in spec.get("cotizaciones", {}).items()}
    for k in ("EQ", "MO"):
        for fila in spec["precios_nuevos"].get(k, []):
            if k == "EQ":
                precios["EQ"].append([fila[0], fila[1], fila[2], fuente])
            else:
                precios["MO"].append([fila[0], None, fila[1], fuente])
    pesos = dict(spec.get("pesos_existentes", {}))
    for d, u, pr, peso in spec["precios_nuevos"]["MAT"]:
        precios["MAT"].append([d, u, pr, fuente])
        pesos[d] = peso
    for k in precios:                       # las cotizaciones reemplazan supuestos y precios oficiales
        for fila in precios[k]:
            c = cotizados.get(_k(fila[0]))
            if c:
                fila[2] = c["precio"]
                fila[3] = f"COTIZACIÓN {c.get('proveedor', '')} {c.get('fecha', '')}".strip()
    nombres = {k: {_k(f[0]) for f in v} for k, v in precios.items()}
    for a in spec["apus"]:   # todo insumo usado debe existir en PRECIOS
        for sec, clave in (("eq", "EQ"), ("mat", "MAT"), ("mo", "MO")):
            for d, _ in a.get(sec, []):
                if _k(d) not in nombres[clave]:
                    raise KeyError(f"APU {a['item']}: «{d}» no está en PRECIOS ({clave}).")

    wb = Workbook()
    ley = wb.active
    ley.title = "LEEME"
    _leeme(ley, spec)
    res = wb.create_sheet("RESUMEN")
    pr = wb.create_sheet("PRECIOS ")
    fila_precio = _hoja_precios(pr, precios)
    filas_res = {}
    _c(res, "B2", spec.get("titulo", "APU"), F_TITULO, relleno=RELLENO_TITULO)
    res.merge_cells("B2:K2")
    cab = ["Ítem", "Descripción (BALANCE oficial)", "Und", "Cantidad", "VU balance oficial", "VU APU ARKCROW",
           "Diferencia", "Valor balance", "Valor APU ARKCROW", "Notas / supuestos"]
    for i, t in enumerate(cab):
        col = "BCDEFGHIJK"[i]
        _c(res, f"{col}4", t, Font(name="Arial", size=9, bold=True, color="FFFFFF"), relleno=RELLENO_TITULO,
           alin=Alignment(wrap_text=True, horizontal="center", vertical="center"))
    for col, w in zip("BCDEFGHIJK", [7, 52, 6, 10, 14, 14, 10, 16, 16, 60]):
        res.column_dimensions[col].width = w
    r = 5
    for a in spec["apus"]:
        filas_res[a["item"]] = r
        r += 1
    for a in spec["apus"]:
        it = items.get(a["item"])
        if not it:
            raise KeyError(f"El ítem {a['item']} no está en el BALANCE oficial.")
        ws = wb.create_sheet(a["item"])
        _hoja_apu(ws, a, it, spec, pesos, filas_res[a["item"]])
        fr = filas_res[a["item"]]
        _c(res, f"B{fr}", a["item"], F_NORMAL)
        _c(res, f"C{fr}", it["desc"], F_NORMAL, alin=Alignment(wrap_text=True, vertical="center"))
        _c(res, f"D{fr}", it["und"], F_NORMAL)
        _c(res, f"E{fr}", it["cant"], Font(name="Arial", size=9, color="0000FF"), "#,##0.00")
        _c(res, f"F{fr}", it["vu"], Font(name="Arial", size=9, color="0000FF"), MONEDA)
        _c(res, f"G{fr}", f"='{a['item']}'!M85", Font(name="Arial", size=9, color="008000"), MONEDA)
        _c(res, f"H{fr}", f"=IF(F{fr}>0,G{fr}/F{fr}-1,0)", F_NORMAL, '+0%;-0%;0%')
        _c(res, f"I{fr}", f"=ROUND(E{fr}*F{fr},0)", F_NORMAL, MONEDA)
        _c(res, f"J{fr}", f"=ROUND(E{fr}*G{fr},0)", F_NORMAL, MONEDA)
        _c(res, f"K{fr}", a.get("nota", ""), Font(name="Arial", size=8), alin=Alignment(wrap_text=True, vertical="center"))
        res.row_dimensions[fr].height = 30
    fin = r - 1
    _c(res, f"C{r}", "TOTAL (ítems de esta hoja)", F_NEGRITA, relleno=RELLENO_TOTAL)
    for col in "IJ":
        _c(res, f"{col}{r}", f"=SUM({col}5:{col}{fin})", F_NEGRITA, MONEDA, RELLENO_TOTAL)
    _c(res, f"H{r}", f"=IF(I{r}>0,J{r}/I{r}-1,0)", F_NEGRITA, '+0%;-0%;0%', RELLENO_TOTAL)
    from openpyxl.formatting.rule import CellIsRule
    res.conditional_formatting.add(f"H5:H{fin}", CellIsRule(operator="lessThan", formula=["-0.3"],
                                                            fill=PatternFill("solid", fgColor="FFC7CE")))
    res.conditional_formatting.add(f"H5:H{fin}", CellIsRule(operator="greaterThan", formula=["0.3"],
                                                            fill=PatternFill("solid", fgColor="FFEB9C")))
    res.freeze_panes = "D5"
    res.page_setup.orientation = "landscape"
    res.sheet_properties.pageSetUpPr.fitToPage = True
    res.page_setup.fitToHeight = 0
    wb.calculation.fullCalcOnLoad = True
    salida = Path(salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    wb.save(salida)
    del fila_precio
    return salida


def _k(t) -> str:
    return " ".join(str(t).split()).lower()


def _leeme(ws, spec):
    textos = [
        ("APU COMPLEMENTARIOS - GENERADOS POR ARKCROW", True),
        ("Libro APARTE del formato oficial F-14-3-5: el oficial tiene logos, casillas y cuadros de texto que no se "
         "deben alterar. Las hojas de APU conservan las mismas filas y columnas del formato oficial.", False),
        ("Precios con fondo amarillo = SUPUESTO ARKCROW (mercado estimado 2026): COTIZAR. Fondo verde = COTIZACIÓN del "
         "usuario (proveedor y fecha en el comentario de la celda).", False),
        ("Rendimientos (columna K) en días por unidad, como el formato UNAD. Herramienta menor = 5 % de la mano de obra.", False),
        (f"Prestaciones = {spec.get('prestaciones', 0.94):.0%} del jornal, igual que los APU oficiales (R&C usa 52 %: confirmar).", False),
        ("Transporte: fracción de viaje según el peso de los materiales; los materiales 'puestos en obra' lo incluyen.", False),
        ("RESUMEN compara cada APU con el valor unitario del balance oficial. Rojo: el APU da 30 % menos; amarillo: 30 % más.", False),
        ("Estos APU NO están pasados por un cuadre de precios: muestran el costo estimado real con los supuestos indicados.", False),
    ]
    ws.column_dimensions["B"].width = 120
    for i, (t, neg) in enumerate(textos, start=2):
        c = ws[f"B{i}"]
        c.value = t
        c.font = Font(name="Arial", size=12 if neg else 10, bold=neg)
        c.alignment = Alignment(wrap_text=True)


def _hoja_precios(ws, precios) -> dict:
    tit = {"EQ": "I. MAQUINARIA / EQUIPO", "MAT": "II. MATERIALES", "TR": "III. TRANSPORTE", "MO": "IV. MANO DE OBRA"}
    for k, (cd, cu, cp) in BLOQUES.items():
        _c(ws, f"{cd}2", tit[k], F_NEGRITA, relleno=RELLENO_CAP)
        _c(ws, f"{cd}3", "DESCRIPCIÓN", F_NEGRITA, relleno=RELLENO_SUB)
        if cu:
            _c(ws, f"{cu}3", "UND/TIPO", F_NEGRITA, relleno=RELLENO_SUB)
        _c(ws, f"{cp}3", "PRECIO / TARIFA / JORNAL", F_NEGRITA, relleno=RELLENO_SUB)
        ws.column_dimensions[cd].width = 46
        for r, (d, u, p, fuente) in enumerate(precios[k], start=4):
            _c(ws, f"{cd}{r}", d, F_NORMAL)
            if cu:
                _c(ws, f"{cu}{r}", u, F_NORMAL)
            celda = _c(ws, f"{cp}{r}", p, Font(name="Arial", size=9, color="0000FF"), MONEDA)
            if fuente.startswith("COTIZACIÓN"):
                celda.fill = PatternFill("solid", fgColor="C6EFCE")
                celda.comment = Comment(fuente, "ARKCROW")
            elif fuente != "PRECIOS oficial":
                celda.fill = AMARILLO
                celda.comment = Comment(fuente, "ARKCROW")
    return {}


def _vlookup(clave: str, cel: str, col: int) -> str:
    cd = BLOQUES[clave][0]
    ultima = {"EQ": "I", "MAT": "S", "TR": "AA", "MO": "AK"}[clave]
    return f"=VLOOKUP({cel},'PRECIOS '!${cd}$4:${ultima}$400,{col},0)"


def _hoja_apu(ws, a, it, spec, pesos, fila_resumen):
    for col, w in zip("BCDEFGHIJKLM", [44, 6, 6, 6, 6, 10, 11, 12, 13, 13, 4, 15]):
        ws.column_dimensions[col].width = w
    _c(ws, "C2", "FORMATO DE ANÁLISIS DE PRECIOS UNITARIOS (geometría F-14-3-5) - COMPLEMENTO ARKCROW", F_TITULO,
       relleno=RELLENO_TITULO)
    ws.merge_cells("C2:M2")
    _c(ws, "B31", "ÍTEM", F_NEGRITA, relleno=RELLENO_SUB)
    _c(ws, "C31", "DESCRIPCIÓN", F_NEGRITA, relleno=RELLENO_SUB)
    _c(ws, "K31", "UNIDAD", F_NEGRITA, relleno=RELLENO_SUB)
    _c(ws, "M31", "CANTIDAD", F_NEGRITA, relleno=RELLENO_SUB)
    _c(ws, "B32", a["item"], F_NEGRITA)
    ws.merge_cells("C32:J32")
    _c(ws, "C32", f"=RESUMEN!C{fila_resumen}", Font(name="Arial", size=9, color="008000"),
       alin=Alignment(wrap_text=True, vertical="center"))
    ws.row_dimensions[32].height = 42
    _c(ws, "K32", f"=RESUMEN!D{fila_resumen}", Font(name="Arial", size=9, color="008000"))
    _c(ws, "M32", f"=RESUMEN!E{fila_resumen}", Font(name="Arial", size=9, color="008000"), "#,##0.00")
    azul = Font(name="Arial", size=9, color="0000FF")

    def seccion(titulo, fila_tit, cab):
        _c(ws, f"B{fila_tit}", titulo, F_NEGRITA, relleno=RELLENO_CAP)
        ws.merge_cells(f"B{fila_tit}:M{fila_tit}")
        for col, t in cab.items():
            _c(ws, f"{col}{fila_tit + 2}", t, F_NEGRITA, relleno=RELLENO_SUB, alin=Alignment(wrap_text=True))

    # I. EQUIPO  (fila 37 = herramienta menor como % de la MO)
    seccion("I. MAQUINARIA / EQUIPO", 34, {"B": "DESCRIPCIÓN", "H": "TIPO", "J": "TARIFA / %", "K": "RENDIMIENTO (días/und)",
                                           "M": "Vr. UNITARIO"})
    _c(ws, "B37", "Herramienta menor (% de la mano de obra)", F_NORMAL)
    _c(ws, "H37", "%", F_NORMAL)
    _c(ws, "J37", spec.get("herramienta_menor", 0.05), azul, "0%")
    _c(ws, "M37", "=ROUND(J37*M81,2)", F_NORMAL, MONEDA)
    for i, (d, rend) in enumerate(a.get("eq", []), start=38):
        if i > FILAS["EQ"][1]:
            raise ValueError(f"APU {a['item']}: demasiados equipos")
        _c(ws, f"B{i}", d, F_NORMAL)
        _c(ws, f"H{i}", _vlookup("EQ", f"B{i}", 7), F_NORMAL)
        _c(ws, f"J{i}", _vlookup("EQ", f"B{i}", 8), F_NORMAL, MONEDA)
        _c(ws, f"K{i}", round(1 / rend, 6), azul, "0.000000")
        ws[f"K{i}"].comment = Comment(f"Rendimiento: {rend:g} und/día", "ARKCROW")
        _c(ws, f"M{i}", f"=K{i}*J{i}", F_NORMAL, MONEDA)
    _c(ws, "B44", "SUBTOTAL", F_NEGRITA)
    _c(ws, "M44", "=ROUND(SUM(M37:M43),2)", F_NEGRITA, MONEDA, RELLENO_SUB)

    # II. MATERIALES
    seccion("II. MATERIALES", 46, {"B": "DESCRIPCIÓN", "I": "UNIDAD", "J": "CANTIDAD", "K": "PRECIO UNIT.", "M": "Vr. UNITARIO"})
    toneladas, incluidos = 0.0, []
    for i, (d, cant) in enumerate(a.get("mat", []), start=49):
        if i > FILAS["MAT"][1]:
            raise ValueError(f"APU {a['item']}: demasiados materiales")
        _c(ws, f"B{i}", d, F_NORMAL)
        _c(ws, f"I{i}", _vlookup("MAT", f"B{i}", 8), F_NORMAL)
        _c(ws, f"J{i}", cant, azul, "#,##0.0000")
        _c(ws, f"K{i}", _vlookup("MAT", f"B{i}", 9), F_NORMAL, MONEDA)
        _c(ws, f"M{i}", f"=K{i}*J{i}", F_NORMAL, MONEDA)
        peso = pesos.get(d)
        if peso == "incluido":
            incluidos.append(d)
        elif peso is not None:
            toneladas += float(peso) * float(cant)
    _c(ws, "B61", "SUBTOTAL", F_NEGRITA)
    _c(ws, "M61", "=ROUND(SUM(M49:M60),2)", F_NEGRITA, MONEDA, RELLENO_SUB)

    # III. TRANSPORTES
    seccion("III. TRANSPORTES", 63, {"B": "MATERIAL", "G": "UNIDAD", "H": "CANTIDAD (1)", "I": "DISTANCIA (2)",
                                     "J": "CANT. x DIST.", "K": "TARIFA", "M": "Vr. UNITARIO"})
    filas_tr = list(a.get("tr", []))
    if not filas_tr and toneladas > 0:
        cap = spec["transporte"]["capacidad_t"]
        filas_tr = [[spec["transporte"]["descripcion"], round(toneladas / cap, 6)]]
    for i, (d, cant) in enumerate(filas_tr, start=66):
        _c(ws, f"B{i}", d, F_NORMAL)
        _c(ws, f"G{i}", _vlookup("TR", f"B{i}", 6), F_NORMAL)
        _c(ws, f"H{i}", cant, azul, "0.000000")
        _c(ws, f"I{i}", 1, azul)
        _c(ws, f"J{i}", f"=H{i}*I{i}", F_NORMAL, "0.000000")
        _c(ws, f"K{i}", _vlookup("TR", f"B{i}", 7), F_NORMAL, MONEDA)
        _c(ws, f"M{i}", f"=K{i}*J{i}", F_NORMAL, MONEDA)
        if not a.get("tr"):
            ws[f"H{i}"].comment = Comment(f"{toneladas:.4f} t de materiales / {spec['transporte']['capacidad_t']} t por viaje",
                                          "ARKCROW")
    if incluidos:
        _c(ws, "B70", "Transporte incluido en el precio (puesto en obra): " + "; ".join(incluidos)[:180],
           Font(name="Arial", size=8, italic=True))
    _c(ws, "B71", "SUBTOTAL", F_NEGRITA)
    _c(ws, "M71", "=ROUND(SUM(M66:M70),2)", F_NEGRITA, MONEDA, RELLENO_SUB)

    # IV. MANO DE OBRA
    seccion("IV. MANO DE OBRA", 73, {"B": "DESCRIPCIÓN", "H": "JORNAL", "I": "PRESTACIONES", "J": "JORNAL TOTAL",
                                     "K": "RENDIMIENTO (días/und)", "M": "Vr. UNITARIO"})
    for i, (d, rend) in enumerate(a.get("mo", []), start=76):
        if i > FILAS["MO"][1]:
            raise ValueError(f"APU {a['item']}: demasiadas personas en la cuadrilla")
        _c(ws, f"B{i}", d, F_NORMAL)
        _c(ws, f"H{i}", _vlookup("MO", f"B{i}", 8), F_NORMAL, MONEDA)
        _c(ws, f"I{i}", f"=H{i}*{spec.get('prestaciones', 0.94)}", F_NORMAL, MONEDA)
        _c(ws, f"J{i}", f"=H{i}+I{i}", F_NORMAL, MONEDA)
        _c(ws, f"K{i}", round(1 / rend, 6), azul, "0.000000")
        ws[f"K{i}"].comment = Comment(f"Rendimiento de la cuadrilla: {rend:g} und/día", "ARKCROW")
        _c(ws, f"M{i}", f"=K{i}*J{i}", F_NORMAL, MONEDA)
    _c(ws, "B81", "SUBTOTAL", F_NEGRITA)
    _c(ws, "M81", "=ROUND(SUM(M76:M80),2)", F_NEGRITA, MONEDA, RELLENO_SUB)

    _c(ws, "B83", "TOTAL COSTO DIRECTO", F_NEGRITA, relleno=RELLENO_TOTAL)
    _c(ws, "M83", "=ROUND(M44+M61+M71+M81,2)", F_NEGRITA, MONEDA, RELLENO_TOTAL)
    _c(ws, "B85", "Precio Unitario Total Aproximado al peso", F_NEGRITA, relleno=RELLENO_TOTAL)
    _c(ws, "M85", "=ROUND(M83,0)", F_NEGRITA, MONEDA, RELLENO_TOTAL)
    _c(ws, "N84", "VU balance oficial", Font(name="Arial", size=8))
    _c(ws, "O85", f"=RESUMEN!F{fila_resumen}", Font(name="Arial", size=9, color="008000"), MONEDA)
    _c(ws, "P84", "Diferencia", Font(name="Arial", size=8))
    _c(ws, "P85", "=IF(O85>0,M85/O85-1,0)", F_NORMAL, '+0%;-0%;0%')
    if a.get("nota"):
        _c(ws, "B87", "Notas / supuestos: " + a["nota"], Font(name="Arial", size=9, italic=True), borde=False)
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToHeight = 0
    ws.print_area = "B30:P88"


def plantilla_cotizaciones(oficial: str | Path, spec: dict, salida: str | Path) -> Path:
    """Excel para llenar: insumos SUPUESTOS (y opcionalmente los oficiales) con columnas de cotización."""
    _, precios = leer_oficial(Path(oficial))
    usados = {_k(d) for a in spec["apus"] for sec in ("eq", "mat", "mo") for d, _ in a.get(sec, [])}
    wb = Workbook()
    ws = wb.active
    ws.title = "COTIZACIONES"
    cab = ["Tipo", "Insumo (no cambiar el texto)", "Unidad", "Precio actual", "Origen del precio actual",
           "PRECIO COTIZADO", "Proveedor", "Fecha (DD/MM/AAAA)", "Observación"]
    for i, t in enumerate(cab, 1):
        c = ws.cell(1, i, t)
        c.font = Font(name="Arial", bold=True, color="FFFFFF")
        c.fill = RELLENO_TITULO
    filas = []
    for d, u, p, *peso in spec["precios_nuevos"]["MAT"]:
        filas.append(("Material", d, u, p, "SUPUESTO ARKCROW"))
    for d, t, p in spec["precios_nuevos"].get("EQ", []):
        filas.append(("Equipo", d, t, p, "SUPUESTO ARKCROW"))
    for d, p in spec["precios_nuevos"].get("MO", []):
        filas.append(("Mano de obra", d, "jornal", p, "SUPUESTO ARKCROW"))
    nombres_nuevos = {_k(f[1]) for f in filas}
    for clave, tipo in (("MAT", "Material"), ("EQ", "Equipo"), ("MO", "Mano de obra")):
        for d, u, p, _ in precios[clave]:
            if _k(d) in usados and _k(d) not in nombres_nuevos:
                filas.append((tipo, d, u or "jornal", p, "PRECIOS oficial (usado en estos APU)"))
    for r, f in enumerate(filas, 2):
        for i, v in enumerate(f, 1):
            ws.cell(r, i, v).font = Font(name="Arial", size=9)
        ws.cell(r, 4).number_format = MONEDA
        for col in (6, 7, 8, 9):
            ws.cell(r, col).fill = AMARILLO
        ws.cell(r, 6).number_format = MONEDA
    for col, w in zip("ABCDEFGHI", [12, 62, 8, 14, 34, 16, 26, 16, 36]):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "C2"
    ws["K1"] = "Llene solo las columnas amarillas. Deje vacío PRECIO COTIZADO si no tiene cotización de ese insumo."
    ws["K1"].font = Font(name="Arial", size=9, italic=True)
    wb.save(salida)
    return Path(salida)


def aplicar_cotizaciones(spec: dict, ruta_cotizaciones: str | Path) -> tuple[dict, list[str]]:
    """Lee la plantilla llena y guarda las cotizaciones en la especificación. Devuelve (spec, avisos)."""
    from datetime import date, datetime
    wv = load_workbook(ruta_cotizaciones, data_only=True)["COTIZACIONES"]
    cot, avisos = dict(spec.get("cotizaciones", {})), []
    for r in range(2, wv.max_row + 1):
        d, p_act, p = wv.cell(r, 2).value, wv.cell(r, 4).value, wv.cell(r, 6).value
        if not d or p in (None, ""):
            continue
        if not isinstance(p, (int, float)) or p <= 0:
            avisos.append(f"Fila {r} «{d}»: precio cotizado no válido ({p}); se ignora.")
            continue
        f = wv.cell(r, 8).value
        fecha = f.strftime("%d/%m/%Y") if isinstance(f, (date, datetime)) else (str(f) if f else "")
        if not wv.cell(r, 7).value:
            avisos.append(f"Fila {r} «{d}»: falta el proveedor.")
        if isinstance(p_act, (int, float)) and p_act and not (0.2 <= p / p_act <= 5):
            avisos.append(f"«{d}»: la cotización ({p:,.0f}) difiere más de 5 veces del precio anterior ({p_act:,.0f}); "
                          "revise unidad o ceros.")
        cot[str(d).strip()] = {"precio": p, "proveedor": str(wv.cell(r, 7).value or ""), "fecha": fecha,
                               "obs": str(wv.cell(r, 9).value or "")}
    spec = {**spec, "cotizaciones": cot}
    return spec, avisos


def main(argv=None):
    a = argv or sys.argv[1:]
    if a and a[0] == "plantilla":            # plantilla OFICIAL.xlsx spec.json salida.xlsx
        spec = json.loads(Path(a[2]).read_text(encoding="utf-8"))
        print(plantilla_cotizaciones(a[1], spec, a[3]))
        return
    if a and a[0] == "cotizar":              # cotizar spec.json cotizaciones.xlsx  (actualiza el JSON)
        ruta = Path(a[1])
        spec, avisos = aplicar_cotizaciones(json.loads(ruta.read_text(encoding="utf-8")), a[2])
        ruta.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{len(spec['cotizaciones'])} cotización(es) guardadas en {ruta.name}")
        for x in avisos:
            print("⚠", x)
        return
    if len(a) < 3:
        sys.exit(__doc__)
    spec = json.loads(Path(a[1]).read_text(encoding="utf-8"))
    out = construir(a[0], spec, a[2])
    print(out)


if __name__ == "__main__":
    main()
