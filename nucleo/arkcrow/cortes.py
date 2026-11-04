"""Actas de corte / avance de obra (Excel con fórmulas vivas + PDF).

Datos de cada corte: proyectos/<obra>/cortes/corte_NN.json
  {"corte": 2, "fecha": "2026-11-30", "desde": "2026-11-01", "hasta": "2026-11-30",
   "cantidades": {"2.03": {"cantidad": 20.0, "memoria": true, "revisar": false}, "2.04": 35.5, ...},
   "observaciones": ["..."]}
  (si la cantidad es un número solo, se asume que SÍ tiene memoria de soporte)

Contrato (ítems, unidades, VU y cantidades contratadas): se lee del último libro de costos aprobado
(proyectos/<obra>/salidas/*APU_Memoria_Balance*.xlsx, hoja BALANCE ya recalculada).

Semáforo por ítem del corte: VERDE memoria completa · ROJO memoria faltante · AZUL faltan fotos (<3) · MORADO revisar

Uso: python -m arkcrow.cortes acta <obra> <N>
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.formatting.rule import CellIsRule, FormulaRule
from openpyxl.styles import Alignment, Font, PatternFill

from . import documentos as D
from . import fotos as F
from .libro_costos import (BORDE, CANT2, CENTRO, F_ENLACE, F_ENTRADA, F_NEGRITA, F_NORMAL, F_TITULO, MONEDA, PCT,
                           RELLENO_CAP, RELLENO_ENTRADA, RELLENO_SUB, RELLENO_TITULO, RELLENO_TOTAL, SEMAFORO, _c)


def contrato_desde_libro(obra: str) -> tuple[list[dict], dict, Path]:
    libros = sorted(D.salidas(obra).glob("*APU_Memoria_Balance*.xlsx"))
    if not libros:
        raise FileNotFoundError("No hay libro de costos en salidas/. Genérelo con presupuesto-balance.")
    libro = libros[-1]
    ws = load_workbook(libro, data_only=True)["BALANCE"]
    items, aiu = [], {}
    for fila in ws.iter_rows(values_only=True):
        a = fila[0]
        if isinstance(a, str) and re.fullmatch(r"(NP-\d+|\d+\.\d+)", a.strip()) and fila[2]:
            if not isinstance(fila[4], (int, float)):
                raise ValueError(f"El libro {libro.name} no tiene valores calculados. Páselo por revisor-calidad --entregar.")
            items.append({"item": a, "desc": fila[1], "und": fila[2], "cant": fila[3], "vu": fila[4]})
        if isinstance(a, str):
            for k, rot in (("a", "Administración"), ("i", "Imprevistos"), ("u", "Utilidad"), ("iva", "IVA sobre")):
                if a.startswith(rot) and isinstance(fila[3], (int, float)):
                    aiu[k] = fila[3]
    return items, aiu, libro


def cargar_cortes(obra: str) -> dict[int, dict]:
    d = D.carpeta_obra(obra) / "cortes"
    out = {}
    for f in sorted(d.glob("corte_*.json")):
        c = json.loads(f.read_text(encoding="utf-8"))
        out[int(c["corte"])] = c
    return out


def _cant(v):
    if isinstance(v, dict):
        return float(v.get("cantidad") or 0), bool(v.get("memoria", True)), bool(v.get("revisar", False))
    return float(v or 0), True, False


def acta(obra: str, n: int) -> dict:
    items, aiu, libro = contrato_desde_libro(obra)
    cortes = cargar_cortes(obra)
    if n not in cortes:
        raise FileNotFoundError(f"No existe cortes/corte_{n:02d}.json")
    actual = cortes[n]
    codigos = {i["item"] for i in items}
    errores, avisos = [], []
    for it in actual["cantidades"]:
        if it not in codigos:
            errores.append(f"El ítem {it} del corte no está en el contrato (¿ítem no previsto sin aprobar?).")
    anterior = {i["item"]: sum(_cant(c["cantidades"].get(i["item"], 0))[0] for k, c in cortes.items() if k < n)
                for i in items}
    fotos = {}
    for r in F.cargar_indice(obra):
        fotos[r["item"]] = fotos.get(r["item"], 0) + 1
    enc = D.encabezado_obra(obra)

    wb = Workbook()
    ws = wb.active
    ws.title = f"ACTA CORTE {n:02d}"
    cols = "ABCDEFGHIJKLMNOP"
    anchos = [7, 40, 6, 10, 13, 15, 10, 10, 10, 8, 14, 14, 15, 10, 14, 11]
    for c, w in zip(cols, anchos):
        ws.column_dimensions[c].width = w
    ws.merge_cells("A1:P1")
    _c(ws, "A1", f"ACTA DE CORTE DE OBRA N° {n:02d}", F_TITULO, relleno=RELLENO_TITULO, alin=CENTRO)
    fila = 2
    for lab, val in (("Objeto", enc.get("objeto", "")), ("Contrato N°", enc.get("contrato", "")),
                     ("Contratista", enc.get("contratista", "")), ("Interventoría", enc.get("interventor", "")),
                     ("Periodo del corte", f"{actual.get('desde', '')} a {actual.get('hasta', '')}"),
                     ("Fecha del acta", actual.get("fecha", f"{date.today():%Y-%m-%d}")),
                     ("Fuente de precios", f"{libro.name} (VU y cantidades contratadas)")):
        ws.merge_cells(f"A{fila}:B{fila}")
        _c(ws, f"A{fila}", lab, F_NEGRITA, relleno=RELLENO_SUB)
        ws.merge_cells(f"C{fila}:P{fila}")
        _c(ws, f"C{fila}", val, F_ENTRADA)
        fila += 1
    fila += 1
    cab = ["Ítem", "Descripción", "Und", "Cant. contrato", "Valor unitario", "Valor contrato",
           "Cant. anterior", "Cant. este corte", "Cant. acumulada", "% avance", "Valor anterior",
           "Valor este corte", "Valor acumulado", "Saldo cant.", "Saldo valor", "Memoria"]
    for c, t in zip(cols, cab):
        _c(ws, f"{c}{fila}", t, Font(name="Arial", size=8, bold=True, color="FFFFFF"), relleno=RELLENO_TITULO, alin=CENTRO)
    ws.row_dimensions[fila].height = 30
    ws.freeze_panes = f"C{fila + 1}"
    fila += 1
    ini = fila
    for it in items:
        cant, memo, revisar = _cant(actual["cantidades"].get(it["item"], 0))
        r = fila
        _c(ws, f"A{r}", it["item"], F_NORMAL, alin=CENTRO)
        _c(ws, f"B{r}", it["desc"], F_NORMAL, alin=Alignment(wrap_text=True, vertical="center"))
        _c(ws, f"C{r}", it["und"], F_NORMAL, alin=CENTRO)
        _c(ws, f"D{r}", it["cant"], F_ENLACE, CANT2)
        _c(ws, f"E{r}", it["vu"], F_ENLACE, MONEDA)
        _c(ws, f"F{r}", f"=ROUND(D{r}*E{r},0)", F_NORMAL, MONEDA)
        _c(ws, f"G{r}", anterior[it["item"]], F_ENTRADA, CANT2, RELLENO_ENTRADA)
        _c(ws, f"H{r}", cant, F_ENTRADA, CANT2, RELLENO_ENTRADA)
        _c(ws, f"I{r}", f"=G{r}+H{r}", F_NORMAL, CANT2)
        _c(ws, f"J{r}", f"=IF(D{r}>0,I{r}/D{r},0)", F_NORMAL, PCT)
        _c(ws, f"K{r}", f"=ROUND(G{r}*E{r},0)", F_NORMAL, MONEDA)
        _c(ws, f"L{r}", f"=ROUND(H{r}*E{r},0)", F_NORMAL, MONEDA)
        _c(ws, f"M{r}", f"=K{r}+L{r}", F_NORMAL, MONEDA)
        _c(ws, f"N{r}", f"=D{r}-I{r}", F_NORMAL, CANT2)
        _c(ws, f"O{r}", f"=F{r}-M{r}", F_NORMAL, MONEDA)
        if cant <= 0:
            estado = "-"
        elif revisar:
            estado = "MORADO"
        elif not memo:
            estado = "ROJO"
        elif fotos.get(it["item"], 0) < 3:
            estado = "AZUL"
        else:
            estado = "VERDE"
        _c(ws, f"P{r}", estado, F_NEGRITA, alin=CENTRO)
        if anterior[it["item"]] + cant > it["cant"] + 1e-9:
            avisos.append(f"Ítem {it['item']}: acumulado {anterior[it['item']] + cant:.2f} supera lo contratado "
                          f"{it['cant']:.2f} {it['und']}. Requiere aprobación de mayores cantidades.")
        if estado in ("ROJO", "AZUL", "MORADO"):
            avisos.append(f"Ítem {it['item']}: semáforo {estado}.")
        ws.row_dimensions[r].height = 30
        fila += 1
    fin = fila - 1
    for estado, color in SEMAFORO.items():
        ws.conditional_formatting.add(f"P{ini}:P{fin}", CellIsRule(operator="equal", formula=[f'"{estado}"'],
                                                                    fill=PatternFill("solid", fgColor=color)))
    ws.conditional_formatting.add(f"I{ini}:J{fin}", FormulaRule(formula=[f"$I{ini}>$D{ini}"],
                                                                fill=PatternFill("solid", fgColor="FFC7CE")))
    # Totales
    res = {}

    def tot(clave, texto, f_val, pct=None, total=False):
        nonlocal fila
        rel = RELLENO_TOTAL if total else RELLENO_SUB
        ws.merge_cells(f"A{fila}:D{fila}")
        _c(ws, f"A{fila}", texto, F_NEGRITA, relleno=rel, alin=Alignment(horizontal="right"))
        _c(ws, f"E{fila}", pct, F_ENTRADA if pct is not None else F_NORMAL, PCT, rel)
        for col in "FKLMO":
            _c(ws, f"{col}{fila}", f_val(col), F_NEGRITA, MONEDA, rel)
        res[clave] = fila
        fila += 1

    tot("cd", "COSTO DIRECTO", lambda c: f"=SUM({c}{ini}:{c}{fin})", total=True)
    cd = res["cd"]
    for k, rot in (("a", "Administración"), ("i", "Imprevistos"), ("u", "Utilidad")):
        tot(k, rot, lambda c, f=fila: f"=ROUND({c}{cd}*$E${f},0)", aiu.get(k, 0))
    u = res["u"]
    tot("iva", "IVA sobre la utilidad", lambda c, f=fila: f"=ROUND({c}{u}*$E${f},0)", aiu.get("iva", 0))
    tot("total", "VALOR TOTAL", lambda c: f"={c}{cd}+{c}{res['a']}+{c}{res['i']}+{c}{res['u']}+{c}{res['iva']}", total=True)
    fila += 1
    ws.merge_cells(f"A{fila}:D{fila}")
    _c(ws, f"A{fila}", "% AVANCE FINANCIERO ACUMULADO", F_NEGRITA, relleno=RELLENO_TOTAL)
    _c(ws, f"E{fila}", f"=IF(F{res['total']}>0,M{res['total']}/F{res['total']},0)", F_NEGRITA, PCT, RELLENO_TOTAL)
    fila_av = fila
    fila += 2
    ws.merge_cells(f"A{fila}:P{fila}")
    _c(ws, f"A{fila}", "OBSERVACIONES", F_NEGRITA, relleno=RELLENO_CAP)
    for o in actual.get("observaciones", []) + avisos:
        fila += 1
        ws.merge_cells(f"A{fila}:P{fila}")
        _c(ws, f"A{fila}", f"• {o}", F_NORMAL)
    fila += 3
    for c1, c2, quien, cargo in (("A", "D", enc.get("elaboro", ""), "Residente de obra - Contratista"),
                                 ("F", "J", enc.get("interventor", ""), "Interventoría"),
                                 ("L", "P", enc.get("supervisor", ""), "Supervisión")):
        ws.merge_cells(f"{c1}{fila}:{c2}{fila}")
        _c(ws, f"{c1}{fila}", "______________________________", F_NORMAL, alin=CENTRO, borde=False)
        ws.merge_cells(f"{c1}{fila + 1}:{c2}{fila + 1}")
        _c(ws, f"{c1}{fila + 1}", quien, F_NEGRITA, alin=CENTRO, borde=False)
        ws.merge_cells(f"{c1}{fila + 2}:{c2}{fila + 2}")
        _c(ws, f"{c1}{fila + 2}", cargo, F_NORMAL, alin=CENTRO, borde=False)
    ws.page_setup.orientation = "landscape"
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToHeight = 0
    wb.calculation.fullCalcOnLoad = True
    destino = D.salidas(obra) / f"Acta_corte_{n:02d}_{actual.get('fecha', f'{date.today():%Y-%m-%d}')}.xlsx"
    wb.save(destino)
    return {"xlsx": destino, "errores": errores, "avisos": avisos, "fila_avance": fila_av, "fila_total": res["total"]}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Acta de corte")
    ap.add_argument("accion", choices=["acta"])
    ap.add_argument("obra")
    ap.add_argument("n", type=int)
    a = ap.parse_args(argv)
    r = acta(a.obra, a.n)
    from .revisor_calidad import revisar
    ok, md, rep = revisar(r["xlsx"], entregar=True)
    for e in r["errores"]:
        print("ERROR:", e)
    for e in r["avisos"]:
        print("Aviso:", e)
    pdf = D.a_pdf(r["xlsx"])
    print(f"Acta: {r['xlsx']}\nPDF: {pdf}\nRevisor: {'APROBADO' if ok and not r['errores'] else 'NO APROBADO'} ({rep.name})")


if __name__ == "__main__":
    main()
