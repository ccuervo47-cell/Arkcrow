"""Generador del libro de costos (APU + Memoria de cantidades + Balance) con fórmulas vivas.

Principio: cada dato vive en UN solo lugar y todo lo demás lo enlaza con fórmulas.
  DATOS     -> encabezados y parámetros (AIU, prestaciones, herramienta menor, distancia)
  INSUMOS   -> precios (copiados de la base SQLite)
  APU x.xx  -> descripción, unidad y precio unitario del ítem
  MEM x.xx  -> cantidades (largo x ancho x alto x cantidad; vanos en negativo)
  BALANCE   -> enlaza cantidad (MEM), unidad/descr./valor unitario (APU) y aplica AIU

Uso:  python -m arkcrow.libro_costos proyectos/<obra>/proyecto.json
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule, FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from . import db

FUENTE = "Arial"
F_NORMAL = Font(name=FUENTE, size=9)
F_NEGRITA = Font(name=FUENTE, size=9, bold=True)
F_TITULO = Font(name=FUENTE, size=12, bold=True, color="FFFFFF")
F_ENTRADA = Font(name=FUENTE, size=9, color="0000FF")          # dato digitado
F_ENLACE = Font(name=FUENTE, size=9, color="008000")           # enlace a otra hoja
F_ENLACE_N = Font(name=FUENTE, size=9, color="008000", bold=True)
RELLENO_TITULO = PatternFill("solid", fgColor="1F3864")
RELLENO_CAP = PatternFill("solid", fgColor="D9E1F2")
RELLENO_SUB = PatternFill("solid", fgColor="F2F2F2")
RELLENO_ENTRADA = PatternFill("solid", fgColor="FFF2CC")
RELLENO_TOTAL = PatternFill("solid", fgColor="FCE4D6")
FINO = Side(style="thin", color="808080")
BORDE = Border(left=FINO, right=FINO, top=FINO, bottom=FINO)
MONEDA = '"$"#,##0;("$"#,##0);"-"'
CANT = '#,##0.000;(#,##0.000);"-"'
CANT2 = '#,##0.00;(#,##0.00);"-"'
PCT = "0.0%"
ENVOLVER = Alignment(wrap_text=True, vertical="center")
CENTRO = Alignment(horizontal="center", vertical="center", wrap_text=True)

SEMAFORO = {"VERDE": "C6EFCE", "ROJO": "FFC7CE", "AZUL": "BDD7EE", "MORADO": "E4C1F9"}

# Campos del encabezado: clave -> etiqueta (orden en la hoja DATOS)
CAMPOS = [
    ("fecha", "Fecha de elaboración (DD/MM/AA)"),
    ("corte", "Corte N°"),
    ("fecha_corte", "Fecha de corte (DD/MM/AA)"),
    ("minima_cuantia", "¿Mínima cuantía? (SI/NO)"),
    ("invitacion", "Invitación N°"),
    ("contrato", "Contrato N°"),
    ("objeto", "Objeto del contrato"),
    ("contratista", "Contratista"),
    ("nit_contratista", "NIT / C.C. contratista"),
    ("representante", "Representante del contratista"),
    ("interventor", "Interventor / Interventoría"),
    ("supervisor", "Supervisor"),
    ("cargo_supervisor", "Cargo del supervisor"),
    ("elaboro", "Elaboró"),
    ("unidad_gestora", "Unidad gestora (aprobación)"),
]
PARAMS = [
    ("prestaciones", "Prestaciones sociales (% del jornal)", PCT),
    ("herramienta_menor", "Herramienta menor (% de la mano de obra)", PCT),
    ("distancia_km", "Distancia de acarreo de materiales (km)", "0.0"),
    ("administracion", "Administración (A)", PCT),
    ("imprevistos", "Imprevistos (I)", PCT),
    ("utilidad", "Utilidad (U)", PCT),
    ("iva_utilidad", "IVA sobre la utilidad", PCT),
]


def _c(ws, ref, valor=None, fuente=F_NORMAL, fmt=None, relleno=None, alin=None, borde=True):
    celda = ws[ref]
    if valor is not None:
        celda.value = valor
    celda.font = fuente
    if fmt:
        celda.number_format = fmt
    if relleno:
        celda.fill = relleno
    celda.alignment = alin or Alignment(vertical="center")
    if borde:
        celda.border = BORDE
    return celda


def _titulo(ws, rango, texto):
    ws.merge_cells(rango)
    ini = rango.split(":")[0]
    _c(ws, ini, texto, F_TITULO, relleno=RELLENO_TITULO, alin=CENTRO)
    ws.row_dimensions[ws[ini].row].height = 22


def _hoja(nombre):
    return f"'{nombre}'"


class LibroCostos:
    def __init__(self, proyecto: dict, insumos: dict):
        self.p = proyecto
        self.ins = insumos
        self.wb = Workbook()
        self.ref = {}          # clave de encabezado/parámetro -> referencia absoluta en DATOS
        self.ins_ref = {}      # código de insumo -> fila en INSUMOS
        self.items = []        # metadatos por ítem (celdas clave)

    # ------------------------------------------------------------------ DATOS
    def hoja_datos(self):
        ws = self.wb.active
        ws.title = "DATOS"
        ws.column_dimensions["A"].width = 44
        ws.column_dimensions["B"].width = 70
        _titulo(ws, "A1:B1", "DATOS GENERALES DEL CONTRATO Y PARÁMETROS")
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.page_setup.fitToHeight = 0
        _c(ws, "A2", "Diligencie SOLO las celdas amarillas (texto azul). Todas las hojas toman los encabezados y "
                     "parámetros de aquí, por eso siempre son consistentes.", F_NORMAL, alin=ENVOLVER, borde=False)
        ws.merge_cells("A2:B2")
        ws.row_dimensions[2].height = 28
        fila = 4
        _c(ws, f"A{fila}", "ENCABEZADO", F_NEGRITA, relleno=RELLENO_CAP)
        _c(ws, f"B{fila}", "", relleno=RELLENO_CAP)
        fila += 1
        enc = self.p["encabezado"]
        for clave, etiqueta in CAMPOS:
            _c(ws, f"A{fila}", etiqueta, F_NEGRITA)
            _c(ws, f"B{fila}", enc.get(clave, ""), F_ENTRADA, relleno=RELLENO_ENTRADA, alin=ENVOLVER)
            self.ref[clave] = f"DATOS!$B${fila}"
            fila += 1
        fila += 1
        _c(ws, f"A{fila}", "PARÁMETROS", F_NEGRITA, relleno=RELLENO_CAP)
        _c(ws, f"B{fila}", "", relleno=RELLENO_CAP)
        fila += 1
        par = self.p["parametros"]
        for clave, etiqueta, fmt in PARAMS:
            _c(ws, f"A{fila}", etiqueta, F_NEGRITA)
            _c(ws, f"B{fila}", par[clave], F_ENTRADA, fmt=fmt, relleno=RELLENO_ENTRADA,
               alin=Alignment(horizontal="left"))
            self.ref[clave] = f"DATOS!$B${fila}"
            fila += 1
        fila += 1
        _c(ws, f"A{fila}", "Código de colores", F_NEGRITA, borde=False)
        leyenda = [("Texto azul / fondo amarillo", "Dato que se digita"),
                   ("Texto verde", "Enlace a otra hoja (no digitar)"),
                   ("Texto negro", "Fórmula de cálculo (no digitar)")]
        for a, b in leyenda:
            fila += 1
            _c(ws, f"A{fila}", a, F_NORMAL, borde=False)
            _c(ws, f"B{fila}", b, F_NORMAL, borde=False)

    # --------------------------------------------------------------- INSUMOS
    def hoja_insumos(self):
        ws = self.wb.create_sheet("INSUMOS")
        _titulo(ws, "A1:I1", "BASE DE PRECIOS DE INSUMOS (copiada de datos/arkcrow.sqlite)")
        cab = ["Código", "Tipo", "Descripción", "Unidad", "Precio", "Transporte", "Factor transp.", "Fuente", "Estado"]
        anchos = [13, 6, 46, 9, 13, 11, 12, 60, 16]
        for i, (t, w) in enumerate(zip(cab, anchos), start=1):
            col = get_column_letter(i)
            ws.column_dimensions[col].width = w
            _c(ws, f"{col}3", t, F_NEGRITA, relleno=RELLENO_CAP, alin=CENTRO)
        fila = 4
        for cod, r in self.ins.items():
            valores = [cod, r["tipo"], r["descripcion"], r["unidad"], r["precio"], r["transp_tipo"] or "",
                       r["transp_factor"] if r["transp_factor"] is not None else "", r["fuente"], r["estado"]]
            for i, v in enumerate(valores, start=1):
                col = get_column_letter(i)
                fmt = MONEDA if i == 5 else ("0.000000" if i == 7 else None)
                _c(ws, f"{col}{fila}", v, F_ENTRADA if i == 5 else F_NORMAL, fmt=fmt,
                   relleno=RELLENO_ENTRADA if i == 5 else None)
            self.ins_ref[cod] = fila
            fila += 1
        ws.freeze_panes = "A4"

    def _precio(self, cod):
        return f"INSUMOS!$E${self.ins_ref[cod]}"

    # ------------------------------------------------------------- SUPUESTOS
    def hoja_supuestos(self):
        ws = self.wb.create_sheet("SUPUESTOS")
        _titulo(ws, "A1:D1", "SUPUESTOS Y CRITERIOS DEL CÁLCULO")
        for i, (t, w) in enumerate(zip(["Parámetro", "Valor", "Unidad", "Fuente / nota"], [36, 14, 12, 80]), start=1):
            col = get_column_letter(i)
            ws.column_dimensions[col].width = w
            _c(ws, f"{col}3", t, F_NEGRITA, relleno=RELLENO_CAP, alin=CENTRO)
        for f, fila in enumerate(self.p.get("supuestos", []), start=4):
            for i, v in enumerate(fila, start=1):
                _c(ws, f"{get_column_letter(i)}{f}", v, F_NORMAL, alin=ENVOLVER)

    # ------------------------------------------------------------------- APU
    def _encabezado(self, ws, fila, pares, ancho_total="H"):
        """Escribe pares (etiqueta, fórmula) en dos columnas: A-D y E-H."""
        for i in range(0, len(pares), 2):
            for j, (lab, val) in enumerate(pares[i:i + 2]):
                cl, cv, cf = ("A", "B", "D") if j == 0 else ("E", "F", ancho_total)
                if lab is None:
                    continue
                _c(ws, f"{cl}{fila}", lab, F_NEGRITA, relleno=RELLENO_SUB, alin=ENVOLVER)
                ws.merge_cells(f"{cv}{fila}:{cf}{fila}")
                _c(ws, f"{cv}{fila}", val, F_ENLACE, alin=ENVOLVER)
            fila += 1
        return fila

    def _linea(self, ws, fila, etiqueta, valor_ref, col_fin="H"):
        _c(ws, f"A{fila}", etiqueta, F_NEGRITA, relleno=RELLENO_SUB)
        ws.merge_cells(f"B{fila}:{col_fin}{fila}")
        _c(ws, f"B{fila}", valor_ref, F_ENLACE if str(valor_ref).startswith("=") else F_ENTRADA, alin=ENVOLVER)
        ws.row_dimensions[fila].height = 26
        return fila + 1

    def hoja_apu(self, item, meta):
        ws = self.wb.create_sheet(f"APU {item['codigo']}")
        nombre = _hoja(ws.title)
        meta["apu"] = ws.title
        for col, w in zip("ABCDEFGH", [44, 12, 12, 13, 12, 13, 12, 15]):
            ws.column_dimensions[col].width = w
        _titulo(ws, "A1:H1", "ANÁLISIS DE PRECIO UNITARIO (APU)")
        r = self.ref
        fila = self._encabezado(ws, 2, [
            ("Fecha", f"={r['fecha']}"), (None, None),
            ("¿Mínima cuantía?", f"={r['minima_cuantia']}"), ("Invitación N°", f"={r['invitacion']}"),
            ("Contrato N°", f"={r['contrato']}"), ("Contratista", f"={r['contratista']}"),
            ("Interventor", f"={r['interventor']}"), ("Supervisor", f"={r['supervisor']}"),
            ("Cargo supervisor", f"={r['cargo_supervisor']}"), (None, None),
        ])
        # tipo de ítem (dato propio del ítem)
        ws.merge_cells("F2:H2")
        tipo = item.get("tipo_item", "Ítem de la propuesta económica")
        _c(ws, "E2", "Tipo de ítem", F_NEGRITA, relleno=RELLENO_SUB)
        _c(ws, "F2", tipo, F_ENTRADA, relleno=RELLENO_ENTRADA)
        dv = DataValidation(type="list", formula1='"Ítem de la propuesta económica,Ítem no previsto"')
        ws.add_data_validation(dv)
        dv.add("F2")
        fila = self._linea(ws, fila, "Objeto", f"={r['objeto']}")
        _c(ws, f"A{fila}", "Ítem", F_NEGRITA, relleno=RELLENO_SUB)
        ws.merge_cells(f"B{fila}:D{fila}")
        _c(ws, f"B{fila}", item["codigo"], F_ENTRADA, relleno=RELLENO_ENTRADA)
        _c(ws, f"E{fila}", "Unidad", F_NEGRITA, relleno=RELLENO_SUB)
        ws.merge_cells(f"F{fila}:H{fila}")
        _c(ws, f"F{fila}", item["unidad"], F_ENTRADA, relleno=RELLENO_ENTRADA, alin=CENTRO)
        meta["apu_item"] = f"{nombre}!$B${fila}"
        meta["apu_unidad"] = f"{nombre}!$F${fila}"
        fila += 1
        _c(ws, f"A{fila}", "Descripción", F_NEGRITA, relleno=RELLENO_SUB)
        ws.merge_cells(f"B{fila}:H{fila}")
        _c(ws, f"B{fila}", item["descripcion"], F_ENTRADA, relleno=RELLENO_ENTRADA, alin=ENVOLVER)
        ws.row_dimensions[fila].height = 36
        meta["apu_desc"] = f"{nombre}!$B${fila}"
        fila += 1
        _c(ws, f"A{fila}", "Cantidad (de la memoria)", F_NEGRITA, relleno=RELLENO_SUB)
        ws.merge_cells(f"B{fila}:D{fila}")
        meta["apu_cant_celda"] = f"B{fila}"   # se llena cuando exista la memoria
        meta["apu_ws"] = ws
        fila += 2

        apu = item["apu"]
        subtotales = {}

        # 1. EQUIPO -------------------------------------------------------
        fila = self._cap(ws, fila, "1. MAQUINARIA / EQUIPO",
                         ["Descripción", "Tipo", "Unidad tarifa", "Tarifa", "Rendimiento\n(und/día)", "", "", "Valor unitario"])
        ini = fila
        for cod, rend in apu["equipo"]:
            ins = self.ins[cod]
            _c(ws, f"A{fila}", f"={_hoja('INSUMOS')}!$C${self.ins_ref[cod]}", F_ENLACE, alin=ENVOLVER)
            _c(ws, f"B{fila}", "Alquiler", F_NORMAL, alin=CENTRO)
            _c(ws, f"C{fila}", ins["unidad"], F_NORMAL, alin=CENTRO)
            _c(ws, f"D{fila}", f"={self._precio(cod)}", F_ENLACE, MONEDA)
            _c(ws, f"E{fila}", rend, F_ENTRADA, CANT2, RELLENO_ENTRADA)
            _c(ws, f"H{fila}", f"=IF(E{fila}>0,D{fila}/E{fila},0)", F_NORMAL, MONEDA)
            for col in "FG":
                _c(ws, f"{col}{fila}")
            fila += 1
        fila_hm = fila  # herramienta menor: % de la mano de obra (se completa al conocer el subtotal MO)
        _c(ws, f"A{fila}", "Herramienta menor", F_NORMAL)
        _c(ws, f"B{fila}", "Global", F_NORMAL, alin=CENTRO)
        _c(ws, f"C{fila}", "% MO", F_NORMAL, alin=CENTRO)
        _c(ws, f"D{fila}", f"={r['herramienta_menor']}", F_ENLACE, PCT)
        for col in "EFG":
            _c(ws, f"{col}{fila}")
        fila += 1
        fila, subtotales["EQ"] = self._subtotal(ws, fila, ini, "Subtotal maquinaria / equipo")

        # 2. MATERIALES ---------------------------------------------------
        fila = self._cap(ws, fila, "2. MATERIALES",
                         ["Descripción", "Unidad", "Cantidad", "Precio unitario", "", "", "", "Valor unitario"])
        ini = fila
        filas_mat = []
        for cod, cant in apu["materiales"]:
            ins = self.ins[cod]
            _c(ws, f"A{fila}", f"={_hoja('INSUMOS')}!$C${self.ins_ref[cod]}", F_ENLACE, alin=ENVOLVER)
            _c(ws, f"B{fila}", f"={_hoja('INSUMOS')}!$D${self.ins_ref[cod]}", F_ENLACE, alin=CENTRO)
            _c(ws, f"C{fila}", cant, F_ENTRADA, CANT, RELLENO_ENTRADA)
            _c(ws, f"D{fila}", f"={self._precio(cod)}", F_ENLACE, MONEDA)
            for col in "EFG":
                _c(ws, f"{col}{fila}")
            _c(ws, f"H{fila}", f"=C{fila}*D{fila}", F_NORMAL, MONEDA)
            filas_mat.append((cod, fila))
            fila += 1
        fila, subtotales["MAT"] = self._subtotal(ws, fila, ini, "Subtotal materiales")

        # 3. TRANSPORTES --------------------------------------------------
        fila = self._cap(ws, fila, "3. TRANSPORTES",
                         ["Material", "Unidad", "Cantidad", "Distancia (km)", "Cant. x dist.", "Tarifa", "", "Valor unitario"])
        ini = fila
        for cod, fmat in filas_mat:
            ins = self.ins[cod]
            _c(ws, f"A{fila}", f"=A{fmat}", F_NORMAL, alin=ENVOLVER)
            if ins["transp_tipo"] == "incluido":
                _c(ws, f"B{fila}", "incluido", F_NORMAL, alin=CENTRO)
                ws.merge_cells(f"C{fila}:G{fila}")
                _c(ws, f"C{fila}", "Transporte incluido en el precio del proveedor (puesto en obra)", F_NORMAL, alin=CENTRO)
                _c(ws, f"H{fila}", 0, F_NORMAL, MONEDA)
            else:
                ton = ins["transp_tipo"] == "ton"
                tarifa = "TR-TON" if ton else "TR-M3"
                fac = f"{_hoja('INSUMOS')}!$G${self.ins_ref[cod]}"
                _c(ws, f"B{fila}", "ton" if ton else "m³", F_NORMAL, alin=CENTRO)
                _c(ws, f"C{fila}", f"=C{fmat}*{fac}", F_NORMAL, "0.000000")
                _c(ws, f"D{fila}", f"={r['distancia_km']}", F_ENLACE, "0.0")
                _c(ws, f"E{fila}", f"=C{fila}*D{fila}", F_NORMAL, "0.0000")
                _c(ws, f"F{fila}", f"={self._precio(tarifa)}", F_ENLACE, MONEDA)
                _c(ws, f"G{fila}")
                _c(ws, f"H{fila}", f"=E{fila}*F{fila}", F_NORMAL, MONEDA)
            fila += 1
        fila, subtotales["TR"] = self._subtotal(ws, fila, ini, "Subtotal transportes")

        # 4. MANO DE OBRA -------------------------------------------------
        fila = self._cap(ws, fila, "4. MANO DE OBRA",
                         ["Descripción", "Jornal", "Prestaciones", "Jornal total", "Rendimiento\n(und/día)", "", "", "Valor unitario"])
        ini = fila
        for cod, rend in apu["mano_obra"]:
            _c(ws, f"A{fila}", f"={_hoja('INSUMOS')}!$C${self.ins_ref[cod]}", F_ENLACE)
            _c(ws, f"B{fila}", f"={self._precio(cod)}", F_ENLACE, MONEDA)
            _c(ws, f"C{fila}", f"=B{fila}*{r['prestaciones']}", F_NORMAL, MONEDA)
            _c(ws, f"D{fila}", f"=B{fila}+C{fila}", F_NORMAL, MONEDA)
            _c(ws, f"E{fila}", rend, F_ENTRADA, CANT2, RELLENO_ENTRADA)
            for col in "FG":
                _c(ws, f"{col}{fila}")
            _c(ws, f"H{fila}", f"=IF(E{fila}>0,D{fila}/E{fila},0)", F_NORMAL, MONEDA)
            fila += 1
        fila, subtotales["MO"] = self._subtotal(ws, fila, ini, "Subtotal mano de obra")
        _c(ws, f"H{fila_hm}", f"=D{fila_hm}*{subtotales['MO']}", F_NORMAL, MONEDA)

        # CIERRE ------------------------------------------------------------
        fila += 1
        ws.merge_cells(f"A{fila}:G{fila}")
        _c(ws, f"A{fila}", "TOTAL COSTO DIRECTO", F_NEGRITA, relleno=RELLENO_TOTAL)
        _c(ws, f"H{fila}", "=" + "+".join(subtotales[k] for k in ("EQ", "MAT", "TR", "MO")), F_NEGRITA, MONEDA, RELLENO_TOTAL)
        fila_cd = fila
        fila += 1
        ws.merge_cells(f"A{fila}:G{fila}")
        _c(ws, f"A{fila}", "PRECIO UNITARIO (aproximado al peso)", F_NEGRITA, relleno=RELLENO_TOTAL)
        _c(ws, f"H{fila}", f"=ROUND(H{fila_cd},0)", F_NEGRITA, MONEDA, RELLENO_TOTAL)
        meta["apu_precio"] = f"{nombre}!$H${fila}"
        fila += 3
        for col_ini, col_fin, txt, quien in (("A", "C", "ELABORÓ (empresa que elabora)", f"={r['contratista']}"),
                                             ("E", "H", "APROBÓ (unidad gestora)", f"={r['unidad_gestora']}")):
            ws.merge_cells(f"{col_ini}{fila}:{col_fin}{fila}")
            ws[f"{col_ini}{fila}"].border = Border(top=Side(style="thin"))
            _c(ws, f"{col_ini}{fila}", txt, F_NEGRITA, alin=CENTRO, borde=False)
            ws.merge_cells(f"{col_ini}{fila + 1}:{col_fin}{fila + 1}")
            _c(ws, f"{col_ini}{fila + 1}", quien, F_ENLACE, alin=CENTRO, borde=False)
        ws.merge_cells(f"A{fila + 2}:C{fila + 2}")
        _c(ws, f"A{fila + 2}", f"={r['elaboro']}", F_ENLACE, alin=CENTRO, borde=False)
        ws.page_setup.fitToWidth = 1
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.page_setup.fitToHeight = 0

    def _cap(self, ws, fila, titulo, cab):
        ws.merge_cells(f"A{fila}:H{fila}")
        _c(ws, f"A{fila}", titulo, F_NEGRITA, relleno=RELLENO_CAP)
        fila += 1
        for col, t in zip("ABCDEFGH", cab):
            _c(ws, f"{col}{fila}", t, F_NEGRITA, relleno=RELLENO_SUB, alin=CENTRO)
        ws.row_dimensions[fila].height = 24
        return fila + 1

    def _subtotal(self, ws, fila, ini, texto):
        ws.merge_cells(f"A{fila}:G{fila}")
        _c(ws, f"A{fila}", texto, F_NEGRITA, relleno=RELLENO_SUB, alin=Alignment(horizontal="right"))
        fin = max(ini, fila - 1)
        _c(ws, f"H{fila}", f"=SUM(H{ini}:H{fin})" if fila > ini else 0, F_NEGRITA, MONEDA, RELLENO_SUB)
        return fila + 2, f"$H${fila}"

    # ---------------------------------------------------------------- MEMORIA
    def hoja_memoria(self, item, capitulo, meta):
        ws = self.wb.create_sheet(f"MEM {item['codigo']}")
        nombre = _hoja(ws.title)
        meta["mem"] = ws.title
        for col, w in zip("ABCDEFGH", [44, 11, 11, 11, 11, 14, 4, 4]):
            ws.column_dimensions[col].width = w
        _titulo(ws, "A1:F1", "MEMORIA DE CANTIDADES")
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.page_setup.fitToHeight = 1
        ws.print_area = "A1:F60"
        r = self.ref
        filas = [
            ("Fecha (DD/MM/AA)", f"={r['fecha']}", "Corte N°", f"={r['corte']}"),
            ("Contrato N°", f"={r['contrato']}", "Interventoría", f"={r['interventor']}"),
            ("Contratista", f"={r['contratista']}", "NIT / C.C.", f"={r['nit_contratista']}"),
            ("Representante del contratista", f"={r['representante']}", None, None),
        ]
        fila = 2
        for a, av, b, bv in filas:
            _c(ws, f"A{fila}", a, F_NEGRITA, relleno=RELLENO_SUB)
            if b is None:
                ws.merge_cells(f"B{fila}:F{fila}")
            else:
                ws.merge_cells(f"B{fila}:C{fila}")
                _c(ws, f"D{fila}", b, F_NEGRITA, relleno=RELLENO_SUB)
                ws.merge_cells(f"E{fila}:F{fila}")
                _c(ws, f"E{fila}", bv, F_ENLACE, alin=ENVOLVER)
            _c(ws, f"B{fila}", av, F_ENLACE, alin=ENVOLVER)
            fila += 1
        for lab, val in (("Objeto del contrato", f"={r['objeto']}"),
                         ("Capítulo", f"{capitulo['codigo']}. {capitulo['nombre']}"),
                         ("Ítem", f"={meta['apu_item']}"),
                         ("Descripción", f"={meta['apu_desc']}"),
                         ("Unidad", f"={meta['apu_unidad']}"),
                         ("Plano de referencia", item.get("plano", ""))):
            _c(ws, f"A{fila}", lab, F_NEGRITA, relleno=RELLENO_SUB)
            ws.merge_cells(f"B{fila}:F{fila}")
            es_f = str(val).startswith("=")
            _c(ws, f"B{fila}", val, F_ENLACE if es_f else F_ENTRADA, relleno=None if es_f else RELLENO_ENTRADA,
               alin=ENVOLVER)
            if lab in ("Objeto del contrato", "Descripción"):
                ws.row_dimensions[fila].height = 30
            if lab == "Unidad":
                meta["mem_unidad"] = f"{nombre}!$B${fila}"
            fila += 1
        fila += 1
        for col, t in zip("ABCDEF", ["Localización / elemento", "Largo (m)", "Ancho (m)", "Alto (m)",
                                     "Cantidad\n(vanos en -)", "Subtotal"]):
            _c(ws, f"{col}{fila}", t, F_NEGRITA, relleno=RELLENO_CAP, alin=CENTRO)
        ws.row_dimensions[fila].height = 26
        fila += 1
        ini = fila
        filas_det = list(item["memoria"]) + [["", None, None, None, None]] * 3   # filas libres para el usuario
        for loc, l, a, h, n in filas_det:
            _c(ws, f"A{fila}", loc, F_ENTRADA, relleno=RELLENO_ENTRADA, alin=ENVOLVER)
            for col, v in zip("BCDE", (l, a, h, n)):
                _c(ws, f"{col}{fila}", v, F_ENTRADA, CANT2 if col != "E" else "0;-0", RELLENO_ENTRADA)
            _c(ws, f"F{fila}", f"=IF(COUNT(B{fila}:E{fila})=0,0,PRODUCT(B{fila}:E{fila}))", F_NORMAL, CANT2)
            fila += 1
        fin = fila - 1
        rojo_neg = CellIsRule(operator="lessThan", formula=["0"], font=Font(name=FUENTE, size=9, color="C00000"))
        ws.conditional_formatting.add(f"F{ini}:F{fin}", rojo_neg)
        _c(ws, f"A{fila}", "Viene memoria anterior", F_NEGRITA, relleno=RELLENO_SUB)
        ws.merge_cells(f"B{fila}:E{fila}")
        _c(ws, f"B{fila}", "")
        _c(ws, f"F{fila}", 0, F_ENTRADA, CANT2, RELLENO_ENTRADA)
        f_ant = fila
        fila += 1
        _c(ws, f"A{fila}", "Subtotal memoria (este corte)", F_NEGRITA, relleno=RELLENO_SUB)
        ws.merge_cells(f"B{fila}:E{fila}")
        _c(ws, f"B{fila}", "")
        _c(ws, f"F{fila}", f"=SUM(F{ini}:F{fin})", F_NEGRITA, CANT2, RELLENO_SUB)
        f_sub = fila
        fila += 1
        _c(ws, f"A{fila}", "TOTAL MEMORIA", F_NEGRITA, relleno=RELLENO_TOTAL)
        ws.merge_cells(f"B{fila}:E{fila}")
        _c(ws, f"B{fila}", f"={meta['apu_unidad']}", F_ENLACE, relleno=RELLENO_TOTAL, alin=CENTRO)
        _c(ws, f"F{fila}", f"=F{f_ant}+F{f_sub}", F_NEGRITA, CANT2, RELLENO_TOTAL)
        meta["mem_total"] = f"{nombre}!$F${fila}"
        meta["mem_subtotal"] = f"{nombre}!$F${f_sub}"
        fila += 2
        # Fotografías
        ws.merge_cells(f"A{fila}:F{fila}")
        _c(ws, f"A{fila}", "REGISTRO FOTOGRÁFICO (3 fotografías)", F_NEGRITA, relleno=RELLENO_CAP, alin=CENTRO)
        fila += 1
        for k, (c1, c2) in enumerate((("A", "A"), ("B", "D"), ("E", "F")), start=1):
            ws.merge_cells(f"{c1}{fila}:{c2}{fila + 7}")
            _c(ws, f"{c1}{fila}", f"FOTO {k}\n(pegar aquí)", F_NORMAL, alin=CENTRO)
        fila += 8
        _c(ws, f"A{fila}", "Fotografías cargadas (0 a 3)", F_NEGRITA, relleno=RELLENO_SUB)
        _c(ws, f"B{fila}", item.get("fotos", 0), F_ENTRADA, "0", RELLENO_ENTRADA)
        f_fotos = fila
        fila += 1
        _c(ws, f"A{fila}", "¿Marcar para revisar? (SI/NO)", F_NEGRITA, relleno=RELLENO_SUB)
        _c(ws, f"B{fila}", item.get("revisar", "NO"), F_ENTRADA, None, RELLENO_ENTRADA)
        dv = DataValidation(type="list", formula1='"SI,NO"')
        ws.add_data_validation(dv)
        dv.add(f"B{fila}")
        f_rev = fila
        fila += 1
        _c(ws, f"A{fila}", "VALIDACIÓN (semáforo)", F_NEGRITA, relleno=RELLENO_TOTAL)
        ws.merge_cells(f"B{fila}:C{fila}")
        _c(ws, f"B{fila}",
           f'=IF(F{f_ant + 2}<=0,"ROJO",IF(B{f_rev}="SI","MORADO",IF(B{f_fotos}<3,"AZUL","VERDE")))',
           F_NEGRITA, alin=CENTRO)
        self._formato_semaforo(ws, f"B{fila}")
        meta["mem_estado"] = f"{nombre}!$B${fila}"
        ws.merge_cells(f"D{fila}:F{fila}")
        _c(ws, f"D{fila}", "VERDE completa · ROJO faltante · AZUL faltan fotos · MORADO revisar",
           Font(name=FUENTE, size=7), alin=ENVOLVER)
        # Cantidad del APU = total de la memoria
        apu_ws = meta["apu_ws"]
        _c(apu_ws, meta["apu_cant_celda"], f"={meta['mem_total']}", F_ENLACE, CANT2)

    @staticmethod
    def _formato_semaforo(ws, rango):
        for estado, color in SEMAFORO.items():
            ws.conditional_formatting.add(rango, CellIsRule(operator="equal", formula=[f'"{estado}"'],
                                                            fill=PatternFill("solid", fgColor=color)))

    # ---------------------------------------------------------------- BALANCE
    def hoja_balance(self):
        ws = self.wb.create_sheet("BALANCE", 1)
        r = self.ref
        for col, w in zip("ABCDEFGHI", [8, 52, 7, 11, 14, 16, 11, 16, 11]):
            ws.column_dimensions[col].width = w
        _titulo(ws, "A1:I1", "BALANCE / PRESUPUESTO")
        fila = 2
        for lab, val in (("Objeto", f"={r['objeto']}"), ("Contrato N°", f"={r['contrato']}"),
                         ("Contratista", f"={r['contratista']}"), ("NIT / C.C.", f"={r['nit_contratista']}"),
                         ("Fecha", f"={r['fecha']}"), ("Corte N°", f"={r['corte']}"),
                         ("Fecha de corte", f"={r['fecha_corte']}")):
            ws.merge_cells(f"A{fila}:B{fila}")
            _c(ws, f"A{fila}", lab, F_NEGRITA, relleno=RELLENO_SUB)
            ws.merge_cells(f"C{fila}:I{fila}")
            _c(ws, f"C{fila}", val, F_ENLACE, alin=ENVOLVER)
            if lab == "Objeto":
                ws.row_dimensions[fila].height = 26
            fila += 1
        fila += 1
        cab = ["Ítem", "Descripción", "Unidad", "Cantidad", "Valor unitario", "Valor total",
               "Corte 01\n(cantidad)", "Valor corte 01", "Memoria\n(semáforo)"]
        for col, t in zip("ABCDEFGHI", cab):
            _c(ws, f"{col}{fila}", t, F_NEGRITA, relleno=RELLENO_TITULO, alin=CENTRO)
            ws[f"{col}{fila}"].font = Font(name=FUENTE, size=9, bold=True, color="FFFFFF")
        ws.row_dimensions[fila].height = 28
        ws.freeze_panes = f"A{fila + 1}"
        fila += 1
        subt_f, subt_h = [], []
        for cap in self.p["capitulos"]:
            ws.merge_cells(f"B{fila}:I{fila}")
            _c(ws, f"A{fila}", cap["codigo"], F_NEGRITA, relleno=RELLENO_CAP, alin=CENTRO)
            _c(ws, f"B{fila}", cap["nombre"], F_NEGRITA, relleno=RELLENO_CAP)
            fila += 1
            ini = fila
            for item in cap["items"]:
                m = next(x for x in self.items if x["codigo"] == item["codigo"])
                _c(ws, f"A{fila}", f"={m['apu_item']}", F_ENLACE, alin=CENTRO)
                _c(ws, f"B{fila}", f"={m['apu_desc']}", F_ENLACE, alin=ENVOLVER)
                _c(ws, f"C{fila}", f"={m['apu_unidad']}", F_ENLACE, alin=CENTRO)
                _c(ws, f"D{fila}", f"={m['mem_total']}", F_ENLACE, CANT2)
                _c(ws, f"E{fila}", f"={m['apu_precio']}", F_ENLACE, MONEDA)
                _c(ws, f"F{fila}", f"=ROUND(D{fila}*E{fila},0)", F_NORMAL, MONEDA)
                _c(ws, f"G{fila}", f"={m['mem_subtotal']}", F_ENLACE, CANT2)
                _c(ws, f"H{fila}", f"=ROUND(G{fila}*E{fila},0)", F_NORMAL, MONEDA)
                _c(ws, f"I{fila}", f"={m['mem_estado']}", F_ENLACE_N, alin=CENTRO)
                ws.row_dimensions[fila].height = 36
                fila += 1
            self._formato_semaforo(ws, f"I{ini}:I{fila - 1}")
            ws.merge_cells(f"A{fila}:E{fila}")
            _c(ws, f"A{fila}", f"SUBTOTAL CAPÍTULO {cap['codigo']}", F_NEGRITA, relleno=RELLENO_SUB,
               alin=Alignment(horizontal="right"))
            _c(ws, f"F{fila}", f"=SUM(F{ini}:F{fila - 1})", F_NEGRITA, MONEDA, RELLENO_SUB)
            _c(ws, f"G{fila}", "", relleno=RELLENO_SUB)
            _c(ws, f"H{fila}", f"=SUM(H{ini}:H{fila - 1})", F_NEGRITA, MONEDA, RELLENO_SUB)
            _c(ws, f"I{fila}", "", relleno=RELLENO_SUB)
            subt_f.append(f"F{fila}")
            subt_h.append(f"H{fila}")
            fila += 1
        fila += 1
        filas_res = {}

        def resumen(clave, texto, f_formula, h_formula, pct_ref=None, total=False):
            nonlocal fila
            ws.merge_cells(f"A{fila}:C{fila}")
            relleno = RELLENO_TOTAL if total else RELLENO_SUB
            _c(ws, f"A{fila}", texto, F_NEGRITA, relleno=relleno, alin=Alignment(horizontal="right"))
            _c(ws, f"D{fila}", f"={pct_ref}" if pct_ref else "", F_ENLACE, PCT, relleno)
            _c(ws, f"E{fila}", "", relleno=relleno)
            _c(ws, f"F{fila}", f_formula, F_NEGRITA, MONEDA, relleno)
            _c(ws, f"G{fila}", "", relleno=relleno)
            _c(ws, f"H{fila}", h_formula, F_NEGRITA, MONEDA, relleno)
            filas_res[clave] = fila
            fila += 1

        resumen("cd", "TOTAL COSTO DIRECTO", "=" + "+".join(subt_f), "=" + "+".join(subt_h), total=True)
        cd = filas_res["cd"]
        resumen("a", "Administración", f"=ROUND(F{cd}*D{fila},0)", f"=ROUND(H{cd}*D{fila},0)", r["administracion"])
        resumen("i", "Imprevistos", f"=ROUND(F{cd}*D{fila},0)", f"=ROUND(H{cd}*D{fila},0)", r["imprevistos"])
        resumen("u", "Utilidad", f"=ROUND(F{cd}*D{fila},0)", f"=ROUND(H{cd}*D{fila},0)", r["utilidad"])
        u = filas_res["u"]
        resumen("iva", "IVA sobre la utilidad", f"=ROUND(F{u}*D{fila},0)", f"=ROUND(H{u}*D{fila},0)", r["iva_utilidad"])
        a, i, iva = filas_res["a"], filas_res["i"], filas_res["iva"]
        resumen("aiu", "TOTAL AIU + IVA", f"=F{a}+F{i}+F{u}+F{iva}", f"=H{a}+H{i}+H{u}+H{iva}")
        resumen("total", "VALOR TOTAL", f"=F{cd}+F{filas_res['aiu']}", f"=H{cd}+H{filas_res['aiu']}", total=True)
        resumen("avance", "% de avance del corte", "", f"=IF(F{filas_res['total']}>0,H{filas_res['total']}/F{filas_res['total']},0)")
        ws[f"H{filas_res['avance']}"].number_format = PCT
        # Resalta en rojo cualquier total en cero (lección 1 de la prueba)
        ws.conditional_formatting.add(f"F{cd}:F{filas_res['total']}",
                                      FormulaRule(formula=[f"AND(ISNUMBER(F{cd}),F{cd}=0)"],
                                                  fill=PatternFill("solid", fgColor="FF0000")))
        fila += 2
        for col_ini, col_fin, txt, quien in (("A", "C", "ELABORÓ", f"={r['elaboro']}"),
                                             ("F", "I", "APROBÓ (unidad gestora)", f"={r['unidad_gestora']}")):
            ws.merge_cells(f"{col_ini}{fila}:{col_fin}{fila}")
            _c(ws, f"{col_ini}{fila}", txt, F_NEGRITA, alin=CENTRO, borde=False)
            ws[f"{col_ini}{fila}"].border = Border(top=Side(style="thin"))
            ws.merge_cells(f"{col_ini}{fila + 1}:{col_fin}{fila + 1}")
            _c(ws, f"{col_ini}{fila + 1}", quien, F_ENLACE, alin=CENTRO, borde=False)
        ws.page_setup.orientation = "landscape"
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.page_setup.fitToHeight = 0

    # ---------------------------------------------------------------- ARMADO
    def construir(self) -> Workbook:
        self.hoja_datos()
        self.hoja_insumos()
        for cap in self.p["capitulos"]:
            for item in cap["items"]:
                faltan = [c for sec in ("equipo", "materiales", "mano_obra") for c, _ in item["apu"][sec]
                          if c not in self.ins]
                if faltan:
                    raise KeyError(f"Ítem {item['codigo']}: insumos no existen en la base: {faltan}")
                meta = {"codigo": item["codigo"]}
                self.hoja_apu(item, meta)
                self.hoja_memoria(item, cap, meta)
                self.items.append(meta)
        self.hoja_balance()
        self.hoja_supuestos()
        # Orden: DATOS, BALANCE, MEM..., APU..., INSUMOS, SUPUESTOS
        orden = ["DATOS", "BALANCE"] + [m["mem"] for m in self.items] + [m["apu"] for m in self.items] + \
                ["INSUMOS", "SUPUESTOS"]
        self.wb._sheets = [self.wb[n] for n in orden]
        self.wb.active = 1
        self.wb.calculation.fullCalcOnLoad = True
        for m in self.items:
            m.pop("apu_ws", None)
        return self.wb


def generar(ruta_proyecto: str | Path, salida: str | Path | None = None) -> Path:
    ruta_proyecto = Path(ruta_proyecto)
    proyecto = json.loads(ruta_proyecto.read_text(encoding="utf-8"))
    libro = LibroCostos(proyecto, db.insumos())
    wb = libro.construir()
    if salida is None:
        carpeta = ruta_proyecto.parent / "salidas"
        carpeta.mkdir(exist_ok=True)
        salida = carpeta / f"{proyecto.get('nombre_archivo', 'Costos')}_{date.today():%Y-%m-%d}.xlsx"
    wb.save(salida)
    return Path(salida)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("Uso: python -m arkcrow.libro_costos proyectos/<obra>/proyecto.json [salida.xlsx]")
    print(generar(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None))
