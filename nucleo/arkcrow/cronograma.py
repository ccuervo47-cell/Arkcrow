"""Programación de obra: Gantt en Excel con ruta crítica (CPM) en fórmulas vivas y programado vs. ejecutado.

Especificación: proyectos/<obra>/cronograma.json
  {"inicio": "2026-11-03", "fecha_corte": "2026-11-15", "calendario": "dias calendario",
   "actividades": [{"id": "A", "actividad": "...", "item": "2.01", "duracion": 3, "predecesoras": ["X"],
                    "ejecutado": 0.5}]}
Relaciones fin-comienzo (FC) sin desfase. Duraciones en días CALENDARIO (supuesto declarado en la hoja).
Si cambia una duración o una predecesora en Excel, se recalculan fechas, holguras, ruta crítica y barras.

Uso: python -m arkcrow.cronograma <obra>
"""
from __future__ import annotations

import json
import sys
from datetime import date, timedelta

from openpyxl import Workbook
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from . import documentos as D
from .libro_costos import CENTRO, F_ENTRADA, F_NEGRITA, F_NORMAL, F_TITULO, PCT, RELLENO_ENTRADA, RELLENO_SUB, \
    RELLENO_TITULO, RELLENO_TOTAL, _c


def cpm(acts: list[dict]) -> dict[str, dict]:
    """Cálculo de control en Python (para pruebas y para validar las fórmulas)."""
    por_id = {a["id"]: a for a in acts}
    orden, visit = [], set()

    def visitar(i, pila=()):
        if i in pila:
            raise ValueError(f"Ciclo en predecesoras: {' -> '.join(pila + (i,))}")
        if i in visit:
            return
        for p in por_id[i].get("predecesoras", []):
            if p not in por_id:
                raise KeyError(f"La actividad {i} tiene una predecesora inexistente: {p}")
            visitar(p, pila + (i,))
        visit.add(i)
        orden.append(i)

    for a in acts:
        visitar(a["id"])
    r = {i: {} for i in por_id}
    for i in orden:
        es = max((r[p]["ef"] for p in por_id[i].get("predecesoras", [])), default=0)
        r[i].update(es=es, ef=es + por_id[i]["duracion"])
    fin = max(x["ef"] for x in r.values())
    sucesoras = {i: [a["id"] for a in acts if i in a.get("predecesoras", [])] for i in por_id}
    for i in reversed(orden):
        lf = min((r[s]["ls"] for s in sucesoras[i]), default=fin)
        r[i].update(lf=lf, ls=lf - por_id[i]["duracion"])
        r[i]["holgura"] = r[i]["ls"] - r[i]["es"]
    return r


def generar(obra: str) -> dict:
    spec = json.loads((D.carpeta_obra(obra) / "cronograma.json").read_text(encoding="utf-8"))
    acts = spec["actividades"]
    control = cpm(acts)
    inicio = date.fromisoformat(spec["inicio"])
    corte = date.fromisoformat(spec["fecha_corte"]) if spec.get("fecha_corte") else None
    dur_total = max(v["ef"] for v in control.values())
    enc = D.encabezado_obra(obra)

    wb = Workbook()
    ws = wb.active
    ws.title = "CRONOGRAMA"
    _c(ws, "A1", "PROGRAMACIÓN DE OBRA - DIAGRAMA DE GANTT Y RUTA CRÍTICA", F_TITULO, relleno=RELLENO_TITULO)
    ws.merge_cells("A1:O1")
    params = [("Obra / objeto", enc.get("objeto", obra)), ("Fecha de inicio", inicio), ("Fecha de corte", corte),
              ("Calendario", "Días calendario, relaciones fin-comienzo (SUPUESTO; ajustar si se trabaja L-S)")]
    for k, (lab, val) in enumerate(params, start=2):
        ws.merge_cells(f"A{k}:B{k}")
        _c(ws, f"A{k}", lab, F_NEGRITA, relleno=RELLENO_SUB)
        ws.merge_cells(f"C{k}:M{k}")
        celda = _c(ws, f"C{k}", val, F_ENTRADA, relleno=RELLENO_ENTRADA, alin=Alignment(horizontal="left"))
        if isinstance(val, date):
            celda.number_format = "DD/MM/YYYY"
    INI, CORTE = "$C$3", "$C$4"
    cab = ["ID", "Actividad", "Ítem", "Duración (d)", "Predecesoras", "Inicio", "Fin", "Inicio temprano (d)",
           "Fin temprano (d)", "Inicio tardío (d)", "Fin tardío (d)", "Holgura (d)", "¿Crítica?", "% programado",
           "% ejecutado", "Desviación"]
    h = 7
    for i, t in enumerate(cab, start=1):
        _c(ws, f"{get_column_letter(i)}{h}", t, Font(name="Arial", size=8, bold=True, color="FFFFFF"),
           relleno=RELLENO_TITULO, alin=CENTRO)
    ws.row_dimensions[h].height = 36
    anchos = [5, 34, 7, 8, 11, 10, 10, 8, 8, 8, 8, 8, 8, 9, 9, 9]
    for i, w in enumerate(anchos, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    fila_de = {a["id"]: h + 1 + k for k, a in enumerate(acts)}
    ult = h + len(acts)
    FIN_PROY = f"$I${ult + 2}"
    for a in acts:
        r = fila_de[a["id"]]
        preds = a.get("predecesoras", [])
        sucs = [b["id"] for b in acts if a["id"] in b.get("predecesoras", [])]
        _c(ws, f"A{r}", a["id"], F_NEGRITA, alin=CENTRO)
        _c(ws, f"B{r}", a["actividad"], F_NORMAL)
        _c(ws, f"C{r}", a.get("item", ""), F_NORMAL, alin=CENTRO)
        _c(ws, f"D{r}", a["duracion"], F_ENTRADA, "0", RELLENO_ENTRADA, CENTRO)
        _c(ws, f"E{r}", ",".join(preds), F_NORMAL, alin=CENTRO)
        _c(ws, f"H{r}", "=MAX(" + ",".join(f"I{fila_de[p]}" for p in preds) + ")" if preds else 0, F_NORMAL, "0", alin=CENTRO)
        _c(ws, f"I{r}", f"=H{r}+D{r}", F_NORMAL, "0", alin=CENTRO)
        _c(ws, f"K{r}", "=MIN(" + ",".join(f"J{fila_de[s]}" for s in sucs) + ")" if sucs else f"={FIN_PROY}",
           F_NORMAL, "0", alin=CENTRO)
        _c(ws, f"J{r}", f"=K{r}-D{r}", F_NORMAL, "0", alin=CENTRO)
        _c(ws, f"L{r}", f"=J{r}-H{r}", F_NORMAL, "0", alin=CENTRO)
        _c(ws, f"M{r}", f'=IF(L{r}=0,"SÍ","NO")', F_NEGRITA, alin=CENTRO)
        _c(ws, f"F{r}", f"={INI}+H{r}", F_NORMAL, "DD/MM/YY", alin=CENTRO)
        _c(ws, f"G{r}", f"={INI}+I{r}-1", F_NORMAL, "DD/MM/YY", alin=CENTRO)
        _c(ws, f"N{r}", f"=IF(D{r}=0,0,MAX(0,MIN(1,({CORTE}-F{r}+1)/D{r})))", F_NORMAL, PCT, alin=CENTRO)
        _c(ws, f"O{r}", a.get("ejecutado", 0), F_ENTRADA, PCT, RELLENO_ENTRADA, CENTRO)
        _c(ws, f"P{r}", f"=O{r}-N{r}", F_NORMAL, '0.0%;[Red]-0.0%', alin=CENTRO)
    # resumen
    _c(ws, f"A{ult + 2}", "Duración total del proyecto (d)", F_NEGRITA, relleno=RELLENO_TOTAL)
    ws.merge_cells(f"A{ult + 2}:H{ult + 2}")
    _c(ws, f"I{ult + 2}", f"=MAX(I{h + 1}:I{ult})", F_NEGRITA, "0", RELLENO_TOTAL, CENTRO)
    _c(ws, f"A{ult + 3}", "Fecha de terminación", F_NEGRITA, relleno=RELLENO_TOTAL)
    ws.merge_cells(f"A{ult + 3}:H{ult + 3}")
    _c(ws, f"I{ult + 3}", f"={INI}+{FIN_PROY}-1", F_NEGRITA, "DD/MM/YY", RELLENO_TOTAL, CENTRO)
    _c(ws, f"A{ult + 4}", "Avance programado / ejecutado ponderado por duración", F_NEGRITA, relleno=RELLENO_TOTAL)
    ws.merge_cells(f"A{ult + 4}:H{ult + 4}")
    _c(ws, f"N{ult + 4}", f"=SUMPRODUCT(N{h + 1}:N{ult},D{h + 1}:D{ult})/SUM(D{h + 1}:D{ult})", F_NEGRITA, PCT, RELLENO_TOTAL, CENTRO)
    _c(ws, f"O{ult + 4}", f"=SUMPRODUCT(O{h + 1}:O{ult},D{h + 1}:D{ult})/SUM(D{h + 1}:D{ult})", F_NEGRITA, PCT, RELLENO_TOTAL, CENTRO)
    _c(ws, f"P{ult + 4}", f"=O{ult + 4}-N{ult + 4}", F_NEGRITA, '0.0%;[Red]-0.0%', RELLENO_TOTAL, CENTRO)
    # Gantt
    c0 = len(cab) + 2
    dias = dur_total + 5
    for d in range(dias):
        col = get_column_letter(c0 + d)
        ws.column_dimensions[col].width = 3.2
        _c(ws, f"{col}{h - 1}", f"={INI}+{d}", Font(name="Arial", size=6), "DD", alin=CENTRO)
        _c(ws, f"{col}{h}", f"={INI}+{d}", Font(name="Arial", size=6, color="FFFFFF"), "MMM", RELLENO_TITULO, CENTRO)
    ws.column_dimensions[get_column_letter(c0 - 1)].width = 1
    primera, ultima = get_column_letter(c0), get_column_letter(c0 + dias - 1)
    rango = f"{primera}{h + 1}:{ultima}{ult}"
    ws.conditional_formatting.add(rango, FormulaRule(
        formula=[f'AND({primera}${h - 1}>=$F{h + 1},{primera}${h - 1}<=$G{h + 1},$M{h + 1}="SÍ")'],
        fill=PatternFill("solid", fgColor="C00000")))
    ws.conditional_formatting.add(rango, FormulaRule(
        formula=[f"AND({primera}${h - 1}>=$F{h + 1},{primera}${h - 1}<=$G{h + 1})"],
        fill=PatternFill("solid", fgColor="4472C4")))
    ws.conditional_formatting.add(rango, FormulaRule(
        formula=[f"AND({primera}${h - 1}={CORTE})"], fill=PatternFill("solid", fgColor="FFE699")))
    ws.conditional_formatting.add(f"P{h + 1}:P{ult}", FormulaRule(
        formula=[f"P{h + 1}<-0.1"], fill=PatternFill("solid", fgColor="FFC7CE")))
    _c(ws, f"A{ult + 6}", "Barras: rojo = ruta crítica · azul = con holgura · columna amarilla = fecha de corte. "
                          "Desviación en rojo: atraso mayor al 10 %.", Font(name="Arial", size=8, italic=True), borde=False)
    ws.freeze_panes = f"C{h + 1}"
    ws.page_setup.orientation = "landscape"
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToHeight = 0
    wb.calculation.fullCalcOnLoad = True
    destino = D.salidas(obra) / f"Cronograma_{date.today():%Y-%m-%d}.xlsx"
    wb.save(destino)
    criticas = [a["id"] for a in acts if control[a["id"]]["holgura"] == 0]
    return {"xlsx": destino, "duracion": dur_total, "fin": inicio + timedelta(days=dur_total - 1),
            "ruta_critica": criticas, "control": control, "fila_de": fila_de}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    r = generar(sys.argv[1])
    from .revisor_calidad import revisar
    ok, _, rep = revisar(r["xlsx"], entregar=True)
    print(f"Cronograma: {r['xlsx']}\nDuración: {r['duracion']} días · terminación {r['fin']:%d/%m/%Y}\n"
          f"Ruta crítica: {' -> '.join(r['ruta_critica'])}\nRevisor: {'APROBADO' if ok else 'NO APROBADO'}")
