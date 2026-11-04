"""Auditor automático del libro de costos (APU + Memoria + Balance).

Revisa un .xlsx (generado por ARKCROW o editado a mano) y reporta:
  ERROR                -> el entregable NO puede salir así
  ADVERTENCIA          -> revisar antes de entregar
  OBSERVACIÓN TÉCNICA  -> criterio técnico a validar contra la práctica / NSR-10
  INFO                 -> dato informativo
Las reglas salen de memoria/lecciones.md (revisión de la prueba técnica).

Uso: python -m arkcrow.auditor libro.xlsx [--reporte salida.md]
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

from .recalculo import recalcular

TOL = 1.0  # tolerancia en pesos
ERRORES_EXCEL = ("#REF!", "#DIV/0!", "#VALUE!", "#NAME?", "#N/A", "#NUM!", "#NULL!", "Err:")
PLACEHOLDER = re.compile(r"por diligenciar|pendiente|xxx|completar|tbd|^\?+$", re.I)
SEVERIDADES = ["ERROR", "ADVERTENCIA", "OBSERVACIÓN TÉCNICA", "INFO"]


def norm(t) -> str:
    t = "" if t is None else str(t)
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", t).strip().lower()


def norm_unidad(u) -> str:
    u = norm(u).replace(" ", "").rstrip(".")
    return {"m2": "m²", "mt2": "m²", "m3": "m³", "mt3": "m³", "un": "und", "unidad": "und", "mts": "m"}.get(u, u)


def pesos(x) -> str:
    return "$" + f"{x:,.0f}".replace(",", ".") if x is not None else "-"


def dec(x, n=2) -> str:
    return f"{x:,.{n}f}".replace(",", "_").replace(".", ",").replace("_", ".") if x is not None else "-"


def num(v) -> float | None:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


@dataclass
class Hallazgo:
    severidad: str
    regla: str
    hoja: str
    celda: str
    mensaje: str
    recomendacion: str = ""


@dataclass
class Resultado:
    archivo: str
    hallazgos: list[Hallazgo] = field(default_factory=list)
    superadas: list[str] = field(default_factory=list)
    resumen: dict = field(default_factory=dict)

    def add(self, *a, **k):
        self.hallazgos.append(Hallazgo(*a, **k))

    def ok(self, texto):
        self.superadas.append(texto)

    def conteo(self):
        return {s: sum(1 for h in self.hallazgos if h.severidad == s) for s in SEVERIDADES}

    @property
    def aprobado(self):
        return self.conteo()["ERROR"] == 0


# --------------------------------------------------------------------- lectura
def _buscar(ws, patron, col=None, desde=1):
    rx = re.compile(patron, re.I)
    for fila in ws.iter_rows(min_row=desde):
        for c in fila:
            if (col is None or get_column_letter(c.column) == col) and isinstance(c.value, str) and rx.search(norm(c.value)):
                return c
    return None


def _valor_derecha(ws, celda):
    """Primer valor no vacío a la derecha de una etiqueta (respeta celdas combinadas)."""
    for col in range(celda.column + 1, celda.column + 4):
        v = ws.cell(celda.row, col).value
        if v not in (None, ""):
            return v, ws.cell(celda.row, col).coordinate
    return None, ws.cell(celda.row, celda.column + 1).coordinate


def leer_apu(ws):
    """Devuelve dict con secciones, subtotales, total y precio de una hoja APU (valores)."""
    apu = {"secciones": {}, "subtotales": {}, "hoja": ws.title}
    cel = _buscar(ws, r"^unidad$", "E")
    apu["unidad"] = _valor_derecha(ws, cel)[0] if cel else None
    cel = _buscar(ws, r"^item$", "A")
    apu["item"] = _valor_derecha(ws, cel)[0] if cel else None
    cel = _buscar(ws, r"^descripcion$", "A")
    apu["descripcion"] = _valor_derecha(ws, cel)[0] if cel else ""
    claves = [("EQ", r"^1\.\s*maquinaria"), ("MAT", r"^2\.\s*materiales"), ("TR", r"^3\.\s*transportes"),
              ("MO", r"^4\.\s*mano de obra")]
    for clave, patron in claves:
        tit = _buscar(ws, patron, "A")
        if not tit:
            continue
        filas = []
        r = tit.row + 2
        while r <= ws.max_row:
            a = ws.cell(r, 1).value
            if isinstance(a, str) and norm(a).startswith("subtotal"):
                apu["subtotales"][clave] = (num(ws.cell(r, 8).value), f"H{r}")
                break
            filas.append({"fila": r, **{col: ws.cell(r, i).value for i, col in enumerate("ABCDEFGH", start=1)}})
            r += 1
        apu["secciones"][clave] = [f for f in filas if f["A"] not in (None, "")]
    t = _buscar(ws, r"^total costo directo", "A")
    apu["total"] = (num(ws.cell(t.row, 8).value), f"H{t.row}") if t else (None, None)
    p = _buscar(ws, r"^precio unitario", "A")
    apu["precio"] = (num(ws.cell(p.row, 8).value), f"H{p.row}") if p else (None, None)
    return apu


def leer_mem(ws):
    mem = {"hoja": ws.title, "filas": []}
    cel = _buscar(ws, r"^unidad$", "A")
    mem["unidad"] = _valor_derecha(ws, cel)[0] if cel else None
    cab = _buscar(ws, r"^localizacion", "A")
    if cab:
        r = cab.row + 1
        while r <= ws.max_row and not norm(ws.cell(r, 1).value).startswith("viene memoria"):
            f = {"fila": r, "loc": ws.cell(r, 1).value,
                 "dims": [num(ws.cell(r, c).value) for c in range(2, 6)], "sub": num(ws.cell(r, 6).value)}
            if f["loc"] not in (None, "") or any(d is not None for d in f["dims"]):
                mem["filas"].append(f)
            r += 1
    for clave, patron in (("anterior", r"^viene memoria"), ("subtotal", r"^subtotal memoria"),
                          ("total", r"^total memoria")):
        c = _buscar(ws, patron, "A")
        mem[clave] = (num(ws.cell(c.row, 6).value), f"F{c.row}") if c else (None, None)
    c = _buscar(ws, r"^validacion", "A")
    mem["estado"] = _valor_derecha(ws, c)[0] if c else None
    c = _buscar(ws, r"^fotografias cargadas", "A")
    mem["fotos"] = num(ws.cell(c.row, 2).value) if c else None
    return mem


def _hoja_referida(formula, prefijo):
    if not isinstance(formula, str):
        return None
    m = re.search(r"'?(" + prefijo + r"[^'!]*)'?!", formula)
    return m.group(1) if m else None


# ----------------------------------------------------------------------- reglas
def auditar(archivo: str | Path, recalculado: str | Path | None = None) -> Resultado:
    archivo = Path(archivo)
    res = Resultado(str(archivo))
    if recalculado is None:
        recalculado = recalcular(archivo)
    wf = load_workbook(archivo)                        # fórmulas
    wv = load_workbook(recalculado, data_only=True)    # valores

    # R0 errores de fórmula ------------------------------------------------
    n_err = 0
    for ws in wv:
        for fila in ws.iter_rows():
            for c in fila:
                if isinstance(c.value, str) and c.value.startswith(ERRORES_EXCEL):
                    n_err += 1
                    if n_err <= 30:
                        res.add("ERROR", "R0 Errores de fórmula", ws.title, c.coordinate,
                                f"La celda muestra {c.value}.", "Corregir la referencia o la división.")
    if n_err == 0:
        res.ok("Ninguna celda con errores de fórmula (#REF!, #DIV/0!, #VALUE!, #NAME?...).")

    if "BALANCE" not in wv.sheetnames:
        res.add("ERROR", "R1 Balance", "-", "-", "No existe la hoja BALANCE.", "Crear el balance enlazado.")
        return res
    bf, bv = wf["BALANCE"], wv["BALANCE"]

    # columnas del balance por encabezado
    cab = _buscar(bv, r"^item$", "A")
    cols = {}
    for c in bv[cab.row]:
        t = norm(c.value)
        letra = get_column_letter(c.column)
        for clave, patron in (("item", r"^item$"), ("desc", r"^descripcion"), ("und", r"^unidad"),
                              ("cant", r"^cantidad"), ("vu", r"^valor unitario"), ("vt", r"^valor total"),
                              ("ccorte", r"^corte"), ("vcorte", r"^valor corte"), ("sem", r"semaforo|memoria"),
                              ("ref", r"referencia|comparaci|diferencia")):
            if re.search(patron, t) and clave not in cols:
                cols[clave] = letra
    faltan = [k for k in ("item", "desc", "und", "cant", "vu", "vt") if k not in cols]
    if faltan:
        res.add("ERROR", "R1 Balance", "BALANCE", f"fila {cab.row}", f"Faltan columnas: {faltan}.")
        return res

    apus = {ws.title: leer_apu(ws) for ws in wv if norm(ws.title).startswith("apu")}
    mems = {ws.title: leer_mem(ws) for ws in wv if norm(ws.title).startswith("mem")}

    items = []
    resumen_filas = {}
    for r in range(cab.row + 1, bv.max_row + 1):
        cod = bv[f"{cols['item']}{r}"].value
        etiqueta = norm(bv[f"A{r}"].value)
        for clave, patron in (("cd", r"^total costo directo"), ("a", r"^administracion"), ("i", r"^imprevistos"),
                              ("u", r"^utilidad"), ("iva", r"^iva"), ("total", r"^valor total")):
            if re.search(patron, etiqueta):
                resumen_filas[clave] = r
        und = bv[f"{cols['und']}{r}"].value
        if cod not in (None, "") and und not in (None, "") and not etiqueta.startswith(("subtotal", "total")):
            items.append(r)
    if not items:
        res.add("ERROR", "R1 Balance", "BALANCE", "-", "El balance no tiene ítems.")
        return res

    # R1 balance enlazado y sin ceros ------------------------------------
    pegados, ceros = [], []
    datos_items = []
    for r in items:
        d = {"fila": r}
        for k in ("item", "desc", "und", "cant", "vu", "vt"):
            d[k] = bv[f"{cols[k]}{r}"].value
        d["f_cant"] = bf[f"{cols['cant']}{r}"].value
        d["f_vu"] = bf[f"{cols['vu']}{r}"].value
        d["f_vt"] = bf[f"{cols['vt']}{r}"].value
        d["mem"] = _hoja_referida(d["f_cant"], "MEM")
        d["apu"] = _hoja_referida(d["f_vu"], "APU")
        datos_items.append(d)
        if not d["mem"]:
            pegados.append(f"{cols['cant']}{r}")
            res.add("ERROR", "R1 Balance enlazado", "BALANCE", f"{cols['cant']}{r}",
                    f"Ítem {d['item']}: la cantidad no está enlazada a una hoja de memoria (valor: {d['f_cant']}).",
                    "Enlazar con fórmula al TOTAL MEMORIA del ítem.")
        if not d["apu"]:
            pegados.append(f"{cols['vu']}{r}")
            res.add("ERROR", "R1 Balance enlazado", "BALANCE", f"{cols['vu']}{r}",
                    f"Ítem {d['item']}: el valor unitario no está enlazado a un APU (valor: {d['f_vu']}).",
                    "Enlazar con fórmula al PRECIO UNITARIO del APU.")
        if not (isinstance(d["f_vt"], str) and d["f_vt"].startswith("=")):
            res.add("ERROR", "R1 Balance enlazado", "BALANCE", f"{cols['vt']}{r}",
                    f"Ítem {d['item']}: el valor total es un valor pegado, no una fórmula.", "Usar =cantidad*VU.")
        for k in ("cant", "vu", "vt"):
            if not num(d[k]):
                ceros.append(f"{cols[k]}{r}")
                res.add("ERROR", "R1 Totales en cero", "BALANCE", f"{cols[k]}{r}",
                        f"Ítem {d['item']}: {k.upper()} está en cero o vacío.",
                        "El balance nunca debe quedar en cero: revisar el enlace con memoria/APU.")
        if num(d["cant"]) and num(d["vu"]) and num(d["vt"]) and abs(d["cant"] * d["vu"] - d["vt"]) > 1.0:
            res.add("ERROR", "R1 Aritmética", "BALANCE", f"{cols['vt']}{r}",
                    f"Ítem {d['item']}: {dec(d['cant'], 3)} x {pesos(d['vu'])} ≠ {pesos(d['vt'])}.")
    if not pegados:
        res.ok(f"Los {len(items)} ítems del balance toman la cantidad de su MEMORIA y el valor unitario de su APU por fórmula.")
    if not ceros:
        res.ok("Ningún ítem del balance tiene cantidad, valor unitario o total en cero.")

    # R1b resumen / AIU ---------------------------------------------------
    vt = cols["vt"]
    val = {k: num(bv[f"{vt}{f}"].value) for k, f in resumen_filas.items()}
    pct = {k: num(bv[f"D{f}"].value) for k, f in resumen_filas.items()}
    if not val.get("cd"):
        res.add("ERROR", "R1 Totales en cero", "BALANCE", f"{vt}{resumen_filas.get('cd', '?')}",
                "El TOTAL COSTO DIRECTO está en cero o no existe.")
    else:
        suma = sum(num(d["vt"]) or 0 for d in datos_items)
        if abs(suma - val["cd"]) > len(items) * TOL:
            res.add("ERROR", "R1 Aritmética", "BALANCE", f"{vt}{resumen_filas['cd']}",
                    f"Costo directo {pesos(val['cd'])} ≠ suma de ítems {pesos(suma)}.")
        else:
            res.ok(f"El costo directo ({pesos(val['cd'])}) es igual a la suma de los ítems.")
        aiu_ok = True
        for k, base in (("a", "cd"), ("i", "cd"), ("u", "cd"), ("iva", "u")):
            if k not in val or not val.get(k):
                res.add("ERROR", "R1b AIU", "BALANCE", "-", f"Falta o está en cero el componente {k.upper()} del AIU.")
                aiu_ok = False
            elif pct.get(k) is not None and val.get(base) and abs(val[base] * pct[k] - val[k]) > 1.0:
                res.add("ERROR", "R1b AIU", "BALANCE", f"{vt}{resumen_filas[k]}",
                        f"{k.upper()} = {pesos(val[k])} no corresponde a {pct[k]:.1%} de {pesos(val[base])}.")
                aiu_ok = False
        if aiu_ok and val.get("total"):
            esperado = val["cd"] + val["a"] + val["i"] + val["u"] + val["iva"]
            if abs(esperado - val["total"]) > 1:
                res.add("ERROR", "R1b AIU", "BALANCE", f"{vt}{resumen_filas['total']}",
                        f"Valor total {pesos(val['total'])} ≠ CD + A + I + U + IVA = {pesos(esperado)}.")
            else:
                res.ok("AIU aplicado y verificado: " + ", ".join(
                    f"{n} {pct[k]:.0%}" for n, k in (("A", "a"), ("I", "i"), ("U", "u"), ("IVA s/U", "iva"))) +
                       f" → total {pesos(val['total'])}.")
        res.resumen = {"costo_directo": val.get("cd"), "administracion": val.get("a"),
                       "imprevistos": val.get("i"), "utilidad": val.get("u"), "iva_utilidad": val.get("iva"),
                       "valor_total": val.get("total"), "items": len(items)}

    # R4 columnas de referencia -----------------------------------------
    if "ref" in cols:
        malas = [r for r in items if not (isinstance(bf[f"{cols['ref']}{r}"].value, str)
                                          and bf[f"{cols['ref']}{r}"].value.startswith("="))
                 or not num(bv[f"{cols['ref']}{r}"].value)]
        if malas:
            res.add("ADVERTENCIA", "R4 Columnas de referencia", "BALANCE", f"{cols['ref']}",
                    f"La columna de comparación contra precios de referencia está vacía o sin enlazar en {len(malas)} ítems.",
                    "Enlazarla a la fuente de precios o eliminarla.")

    # R2 unidades idénticas + R5 consistencia APU/MEM/BALANCE --------------
    und_ok = True
    for d in datos_items:
        apu, mem = apus.get(d["apu"]), mems.get(d["mem"])
        unidades = {"BALANCE": d["und"]}
        if apu:
            unidades["APU"] = apu["unidad"]
            if apu["precio"][0] is not None and num(d["vu"]) is not None and abs(apu["precio"][0] - d["vu"]) > TOL:
                res.add("ERROR", "R5 Consistencia", "BALANCE", f"{cols['vu']}{d['fila']}",
                        f"Ítem {d['item']}: VU del balance {pesos(d['vu'])} ≠ precio del APU {pesos(apu['precio'][0])}.")
        if mem:
            unidades["MEMORIA"] = mem["unidad"]
            if mem["total"][0] is not None and num(d["cant"]) is not None and abs(mem["total"][0] - d["cant"]) > 1e-6:
                res.add("ERROR", "R5 Consistencia", "BALANCE", f"{cols['cant']}{d['fila']}",
                        f"Ítem {d['item']}: cantidad del balance ≠ total de la memoria.")
        crudas = {k: str(v).strip() for k, v in unidades.items()}
        if len(set(crudas.values())) > 1:
            und_ok = False
            mismas = len({norm_unidad(v) for v in crudas.values()}) == 1
            res.add("ADVERTENCIA" if mismas else "ERROR", "R2 Unidades", "BALANCE", f"{cols['und']}{d['fila']}",
                    f"Ítem {d['item']}: unidades distintas {crudas}.",
                    "La unidad debe ser IDÉNTICA en APU, memoria y balance.")
    if und_ok:
        res.ok("Unidades idénticas en APU, memoria y balance para todos los ítems.")

    # R3 encabezados -------------------------------------------------------
    enc_ok = True
    if "DATOS" in wv.sheetnames:
        ws = wv["DATOS"]
        ini = _buscar(ws, r"^encabezado$", "A")
        fin = _buscar(ws, r"^parametros$", "A")
        if ini:
            for r in range(ini.row + 1, (fin.row if fin else ws.max_row)):
                lab, v = ws.cell(r, 1).value, ws.cell(r, 2).value
                if not lab:
                    continue
                if v in (None, ""):
                    enc_ok = False
                    res.add("ERROR", "R3 Encabezados", "DATOS", f"B{r}", f"Campo vacío: «{lab}».",
                            "Diligenciar: se replica en todas las hojas.")
                elif PLACEHOLDER.search(str(v)):
                    enc_ok = False
                    res.add("ADVERTENCIA", "R3 Encabezados", "DATOS", f"B{r}",
                            f"Campo «{lab}» sin dato real: «{v}».", "Completar antes de entregar.")
    # mismo rótulo -> mismo valor en todas las hojas
    rotulos = {"fecha": r"^fecha( \(dd/mm/aa\))?$", "contrato": r"^contrato n", "contratista": r"^contratista$",
               "objeto": r"^objeto", "nit": r"^nit", "supervisor": r"^supervisor$", "corte": r"^corte n"}
    vistos: dict[str, dict] = {k: {} for k in rotulos}
    for ws in wv:
        if ws.title in ("DATOS", "INSUMOS", "SUPUESTOS"):
            continue
        for fila in ws.iter_rows(max_row=16):
            for c in fila:
                if not isinstance(c.value, str):
                    continue
                for k, patron in rotulos.items():
                    if re.search(patron, norm(c.value)):
                        v, coord = _valor_derecha(ws, c)
                        if v in (None, ""):
                            enc_ok = False
                            res.add("ERROR", "R3 Encabezados", ws.title, coord, f"Encabezado «{c.value}» vacío.")
                        else:
                            vistos[k].setdefault(str(v).strip(), []).append(ws.title)
    for k, valores in vistos.items():
        if len(valores) > 1:
            enc_ok = False
            res.add("ERROR", "R3 Encabezados", "varias", "-",
                    f"El encabezado «{k}» tiene valores distintos entre hojas: " +
                    "; ".join(f"«{v}» en {', '.join(h[:3])}{'...' if len(h) > 3 else ''}" for v, h in valores.items()),
                    "Enlazar todos los encabezados a la hoja DATOS.")
    if enc_ok:
        res.ok("Encabezados llenos y consistentes en todas las hojas.")

    # R5-R7 revisión de cada APU ------------------------------------------
    prest_ok, hm_ok, tr_ok, suma_ok = True, True, True, True
    distancias = set()
    for nombre, apu in apus.items():
        sec = apu["secciones"]
        mo_sub = apu["subtotales"].get("MO", (None,))[0] or 0
        # prestaciones 52 %
        for f in sec.get("MO", []):
            j, p = num(f["B"]), num(f["C"])
            if j and (p is None or abs(p / j - 0.52) > 0.001):
                prest_ok = False
                res.add("ERROR", "R5 Prestaciones", nombre, f"C{f['fila']}",
                        f"Prestaciones = {0 if not p else p / j:.1%} del jornal (debe ser 52 %).")
        # herramienta menor
        hm = [f for f in sec.get("EQ", []) if "herramienta menor" in norm(f["A"])]
        if not hm:
            hm_ok = False
            res.add("ADVERTENCIA", "R7 Herramienta menor", nombre, "-", "El APU no incluye herramienta menor.",
                    "Incluirla como 5-10 % de la mano de obra.")
        for f in hm:
            if "%" in str(f["C"]) or "%" in str(f["B"]):
                pct_hm = num(f["D"])
                if pct_hm is None or not 0.05 <= pct_hm <= 0.10:
                    hm_ok = False
                    res.add("ADVERTENCIA", "R7 Herramienta menor", nombre, f"D{f['fila']}",
                            f"Herramienta menor = {pct_hm} (esperado 5-10 % de la MO).")
                elif abs((num(f["H"]) or 0) - pct_hm * mo_sub) > TOL:
                    hm_ok = False
                    res.add("ERROR", "R7 Herramienta menor", nombre, f"H{f['fila']}",
                            "El valor de herramienta menor no corresponde al % del subtotal de mano de obra.")
            else:
                hm_ok = False
                res.add("ADVERTENCIA", "R7 Herramienta menor", nombre, f"A{f['fila']}",
                        "Herramienta menor cobrada como alquiler/tarifa y no como % de la mano de obra.",
                        "Usar 5-10 % de la mano de obra.")
        # transportes consistentes
        mats = [(norm(f["A"]), f) for f in sec.get("MAT", [])]
        trs = {norm(f["A"]): f for f in sec.get("TR", [])}
        for desc, f in mats:
            t = trs.get(desc)
            if t is None:
                tr_ok = False
                res.add("ADVERTENCIA", "R6 Transportes", nombre, f"A{f['fila']}",
                        f"El material «{f['A']}» no tiene renglón de transporte.",
                        "Aplicar transporte a todos los materiales (o indicar 'incluido en el precio').")
            elif norm(t["B"]) != "incluido":
                if not num(t["H"]):
                    tr_ok = False
                    res.add("ERROR", "R6 Transportes", nombre, f"H{t['fila']}",
                            f"Transporte de «{f['A']}» en cero sin indicar que está incluido.")
                if num(t["D"]) is not None:
                    distancias.add(num(t["D"]))
        # sumas
        for clave, (sub, coord) in apu["subtotales"].items():
            calc = sum(num(f["H"]) or 0 for f in sec.get(clave, []))
            if sub is None or abs(calc - sub) > TOL:
                suma_ok = False
                res.add("ERROR", "R5 Suma de capítulos", nombre, coord,
                        f"Subtotal {clave} = {sub} ≠ suma de renglones {pesos(calc)}.")
        total = apu["total"][0]
        calc = sum((v or 0) for v, _ in apu["subtotales"].values())
        if total is None or abs(calc - total) > TOL:
            suma_ok = False
            res.add("ERROR", "R5 Suma de capítulos", nombre, apu["total"][1] or "-",
                    f"Total costo directo {total} ≠ suma de capítulos {pesos(calc)}.")
        elif apu["precio"][0] is None or abs(round(total) - apu["precio"][0]) > 0.5:
            suma_ok = False
            res.add("ERROR", "R5 Suma de capítulos", nombre, apu["precio"][1] or "-",
                    "El precio unitario no es el costo directo aproximado al peso.")
    if apus:
        if prest_ok:
            res.ok("Prestaciones sociales = 52 % del jornal en todas las cuadrillas.")
        if hm_ok:
            res.ok("Herramienta menor calculada como % de la mano de obra (5-10 %) en todos los APU.")
        if suma_ok:
            res.ok(f"Los {len(apus)} APU suman bien: renglones → subtotales → costo directo → precio al peso.")
        if len(distancias) > 1:
            tr_ok = False
            res.add("ADVERTENCIA", "R6 Transportes", "APU", "-",
                    f"Se usan distancias de acarreo distintas: {sorted(distancias)} km.",
                    "Confirmar que es intencional (proveedores distintos).")
        if tr_ok:
            res.ok("Transporte aplicado de forma consistente a todos los materiales "
                   f"(misma distancia: {', '.join(f'{d:g}' for d in distancias)} km; premezclados marcados 'incluido').")

    # Memorias ---------------------------------------------------------------
    estados = {}
    for d in datos_items:
        mem = mems.get(d["mem"])
        if not mem:
            continue
        estados.setdefault(mem["estado"] or "SIN ESTADO", []).append(d["item"])
        for f in mem["filas"]:
            dims = [x for x in f["dims"] if x is not None]
            if dims:
                esperado = 1.0
                for x in dims:
                    esperado *= x
                if f["sub"] is None or abs(esperado - f["sub"]) > 1e-6:
                    res.add("ERROR", "Memoria", mem["hoja"], f"F{f['fila']}", "Subtotal de la fila mal calculado.")
            altos = [x for x in f["dims"][:3] if x is not None and x > 20]
            if altos:
                res.add("ADVERTENCIA", "Memoria", mem["hoja"], f"B{f['fila']}",
                        f"Dimensión inusual ({altos} m) en «{f['loc']}».", "Verificar unidades (¿cm en vez de m?).")
    for estado, lista in estados.items():
        sev = {"VERDE": "INFO", "ROJO": "ERROR", "AZUL": "ADVERTENCIA", "MORADO": "ADVERTENCIA"}.get(estado, "ADVERTENCIA")
        texto = {"VERDE": "memoria completa", "ROJO": "memoria faltante", "AZUL": "faltan fotografías",
                 "MORADO": "marcadas para revisar"}.get(estado, "sin semáforo")
        res.add(sev, "Semáforo de memorias", "MEM", "-", f"{estado}: {len(lista)} ítem(s), {texto}: {', '.join(map(str, lista))}.",
                "Cargar las 3 fotografías por ítem antes del corte." if estado == "AZUL" else "")

    # R8 criterios técnicos (lecciones de la prueba) ---------------------------
    _tecnicas(res, datos_items, apus, mems)

    # Diferencias anómalas: concentración del presupuesto
    cd = res.resumen.get("costo_directo") or 0
    for d in datos_items:
        if cd and num(d["vt"]) and d["vt"] / cd > 0.35:
            res.add("INFO", "Anomalías", "BALANCE", f"{cols['vt']}{d['fila']}",
                    f"El ítem {d['item']} concentra el {d['vt'] / cd:.0%} del costo directo.", "Revisar su APU con detalle.")
    return res


def _tecnicas(res, items, apus, mems):
    descs = {d["item"]: norm(d["desc"]) for d in items}
    todas = " | ".join(descs.values())

    def por_patron(p):
        return [d for d in items if re.search(p, norm(d["desc"]))]

    # Mortero de nivelación 3-5 cm
    for d in por_patron(r"mortero.*nivelaci|nivelaci.*mortero"):
        m = re.search(r"e\s*=\s*(\d+(?:[.,]\d+)?)\s*(cm|m)\b", norm(d["desc"]))
        if not m:
            res.add("OBSERVACIÓN TÉCNICA", "T1 Mortero de nivelación", "BALANCE", f"B{d['fila']}",
                    f"Ítem {d['item']}: no se especifica el espesor del mortero de nivelación.",
                    "Indicar el espesor (normalmente 3-5 cm).")
            continue
        e = float(m.group(1).replace(",", "."))
        e_cm = e * 100 if m.group(2) == "m" else e
        if 3 <= e_cm <= 5:
            res.ok(f"T1 Mortero de nivelación ítem {d['item']}: e = {e_cm:g} cm, dentro del rango usual 3-5 cm.")
        else:
            res.add("OBSERVACIÓN TÉCNICA", "T1 Mortero de nivelación", "BALANCE", f"B{d['fila']}",
                    f"Ítem {d['item']}: espesor {e_cm:g} cm fuera del rango usual 3-5 cm.", "Validar con diseño.")

    # Cuantía de acero en placas 60-100 kg/m³
    for d in por_patron(r"placa"):
        apu = apus.get(d["apu"])
        if not apu or norm_unidad(apu["unidad"]) != "m³":
            continue
        kg = sum(num(f["C"]) or 0 for f in apu["secciones"].get("MAT", [])
                 if "acero" in norm(f["A"]) and norm(f["B"]) == "kg")
        if kg == 0:
            res.add("OBSERVACIÓN TÉCNICA", "T2 Cuantía de acero", apu["hoja"], "-",
                    f"Ítem {d['item']}: la placa no incluye acero de refuerzo.", "Incluir 60-100 kg/m³ o malla según diseño.")
        elif 60 <= kg <= 100:
            res.ok(f"T2 Cuantía de acero ítem {d['item']}: {kg:g} kg/m³, dentro del rango usual 60-100 kg/m³.")
        else:
            res.add("OBSERVACIÓN TÉCNICA", "T2 Cuantía de acero", apu["hoja"], "-",
                    f"Ítem {d['item']}: cuantía {kg:g} kg/m³ fuera del rango usual 60-100 kg/m³.",
                    "Validar contra el diseño estructural.")

    # Confinamiento de mampostería (NSR-10)
    mamp = por_patron(r"mamposteria|muro en bloque|muro en ladrillo")
    if mamp and not re.search(r"columnet|viga de amarre|viga de confinamiento|viga cinta|confinamiento|dovela", todas):
        ml, vanos = 0.0, 0
        for d in mamp:
            mem = mems.get(d["mem"])
            for f in (mem or {}).get("filas", []):
                largo, n = f["dims"][0], f["dims"][3]
                if largo and n and n > 0:
                    ml += largo * n
                elif n and n < 0:
                    vanos += 1
        res.add("OBSERVACIÓN TÉCNICA", "T3 Confinamiento NSR-10", "BALANCE", f"B{mamp[0]['fila']}",
                f"Hay mampostería (ítem {', '.join(d['item'] for d in mamp)}) pero no hay ítems de columnetas ni "
                f"vigas de amarre/confinamiento. Orden de magnitud: viga de amarre en la corona ≈ {dec(ml)} ml; "
                f"columnetas en las 4 esquinas, en los bordes de los {vanos} vanos y en tramos largos.",
                "Incluir columnetas y vigas de amarre según NSR-10 (Título D mampostería confinada; si son muros "
                "no estructurales, cap. A.9 elementos no estructurales). Verificar con la norma indexada y el diseño.")
    elif mamp:
        res.ok("T3 La mampostería tiene ítems de confinamiento (columnetas / vigas de amarre).")

    # Pintura de cielo raso
    cielo = por_patron(r"cielo raso|cielorraso")
    if cielo and not any(re.search(r"pintura|vinilo", t) and "cielo" in t for t in descs.values()):
        area = sum(num(d["cant"]) or 0 for d in cielo)
        res.add("OBSERVACIÓN TÉCNICA", "T4 Pintura de cielo raso", "BALANCE", f"B{cielo[0]['fila']}",
                f"Hay cielo raso ({dec(area)} m²) pero no hay ítem de pintura de cielo raso.",
                "Agregar pintura de cielo (vinilo tipo 1, 2-3 manos) o indicar que el ítem de cielo la incluye.")
    elif cielo:
        res.ok("T4 El cielo raso tiene ítem de pintura.")

    # Suministro de puertas y ventanas
    vanos = {}
    for m in mems.values():
        for f in m["filas"]:
            n = f["dims"][3]
            if n is not None and n < 0:
                cod = re.search(r"\b([pv]-?\d+)\b", norm(f["loc"]))
                tipo = "puerta" if "puerta" in norm(f["loc"]) or (cod and cod.group(1).startswith("p")) else \
                    "ventana" if "ventana" in norm(f["loc"]) or (cod and cod.group(1).startswith("v")) else None
                if tipo:
                    clave = cod.group(1).upper() if cod else norm(f["loc"])
                    vanos[clave] = (tipo, f["dims"][0], f["dims"][2])
    for tipo in ("puerta", "ventana"):
        del_tipo = {k: v for k, v in vanos.items() if v[0] == tipo}
        if del_tipo and not re.search(tipo, todas):
            lista = ", ".join(f"{k} ({dec(v[1])} x {dec(v[2])} m)" if v[1] and v[2] else k for k, v in del_tipo.items())
            res.add("OBSERVACIÓN TÉCNICA", "T5 Puertas y ventanas", "BALANCE", "-",
                    f"Las memorias descuentan vanos de {tipo} ({lista}) pero el presupuesto no incluye su suministro e instalación.",
                    f"Agregar ítem de suministro e instalación de {tipo}s (carpintería en madera/metálica) o dejar "
                    "constancia de que lo suministra el contratante.")
        elif del_tipo:
            res.ok(f"T5 Los vanos de {tipo} tienen ítem de suministro.")


# --------------------------------------------------------------------- reporte
def reporte_md(res: Resultado) -> str:
    c = res.conteo()
    estado = "✅ APROBADO (sin errores)" if res.aprobado else "❌ NO APROBADO: hay errores que corregir"
    L = [f"# Reporte del auditor ARKCROW", "",
         f"- **Archivo:** `{Path(res.archivo).name}`",
         f"- **Fecha de revisión:** {datetime.now():%d/%m/%Y %H:%M}",
         f"- **Resultado:** {estado}",
         f"- **Hallazgos:** {c['ERROR']} errores · {c['ADVERTENCIA']} advertencias · "
         f"{c['OBSERVACIÓN TÉCNICA']} observaciones técnicas · {c['INFO']} informativos", ""]
    if res.resumen:
        s = res.resumen
        L += ["## Resumen económico", "", "| Concepto | Valor |", "|---|---:|"]
        for k, n in (("costo_directo", "Costo directo"), ("administracion", "Administración"),
                     ("imprevistos", "Imprevistos"), ("utilidad", "Utilidad"), ("iva_utilidad", "IVA sobre utilidad"),
                     ("valor_total", "**Valor total**")):
            if s.get(k) is not None:
                L.append(f"| {n} | {pesos(s[k])} |")
        L.append("")
    for sev in SEVERIDADES:
        hs = [h for h in res.hallazgos if h.severidad == sev]
        if not hs:
            continue
        L += [f"## {sev} ({len(hs)})", ""]
        for h in hs:
            L.append(f"- **[{h.regla}]** `{h.hoja}!{h.celda}`: {h.mensaje}")
            if h.recomendacion:
                L.append(f"  - *Qué hacer:* {h.recomendacion}")
        L.append("")
    if res.superadas:
        L += ["## Verificaciones superadas", ""] + [f"- ✔ {t}" for t in res.superadas] + [""]
    L += ["---", "*Reglas tomadas de `memoria/lecciones.md` (revisión de la prueba técnica). Las observaciones "
          "técnicas son alertas de criterio: confirmar contra la norma indexada y el diseño antes de modificar.*"]
    return "\n".join(L)


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="Auditor del libro de costos ARKCROW")
    ap.add_argument("archivo")
    ap.add_argument("--reporte", help="ruta del reporte .md (por defecto junto al archivo)")
    ap.add_argument("--json", action="store_true", help="imprimir resultado en JSON")
    a = ap.parse_args(argv)
    res = auditar(a.archivo)
    md = reporte_md(res)
    destino = Path(a.reporte) if a.reporte else Path(a.archivo).with_name(Path(a.archivo).stem + "_AUDITORIA.md")
    destino.write_text(md, encoding="utf-8")
    if a.json:
        print(json.dumps({"aprobado": res.aprobado, "conteo": res.conteo(), "resumen": res.resumen,
                          "hallazgos": [asdict(h) for h in res.hallazgos]}, ensure_ascii=False, indent=2))
    else:
        print(md)
    print(f"\nReporte guardado en: {destino}")
    return 0 if res.aprobado else 1


if __name__ == "__main__":
    sys.exit(main())
