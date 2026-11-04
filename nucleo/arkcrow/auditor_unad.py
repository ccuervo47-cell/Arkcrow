"""Auditor del formato UNAD F-14-3-5 (APU + BALANCE + PRECIOS + FORMATO), con cruce opcional contra un plano DXF.

Revisa (reglas de memoria/lecciones.md adaptadas al formato UNAD):
  - Encabezado de FORMATO: objeto coherente con el presupuesto, contrato, supervisor, interventor.
  - BALANCE: cada ítem con su hoja de APU, APU calculado, precio del APU = valor unitario del balance,
    errores (#N/A, #VALUE!...), fórmula del costo directo, AIU.
  - Cada APU: insumos que no existen en PRECIOS, insumos que no corresponden al ítem (APU copiado de otro
    proyecto), prestaciones, herramienta menor como % de la MO, transporte por material, rendimientos "cuadrados".
  - Hojas sobrantes (APU sin ítem en el balance).
  - Opcional: cruce de cantidades del presupuesto contra capas/bloques de un DXF.

Uso: python -m arkcrow.auditor_unad APUS.xlsx [--dxf plano.dxf] [--salida carpeta]
"""
from __future__ import annotations

import argparse
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from openpyxl import load_workbook

ERR = ("#N/A", "#VALUE!", "#REF!", "#DIV/0!", "#NAME?", "#NUM!")
STOP = set("de del la las el los en con para por y o a e un una incluye segun según suministro instalacion "
           "instalación tipo x mm cm m2 m3 ml und todo todos sus al".split())


def _n(t) -> str:
    t = unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", t).strip()


def _palabras(t) -> set[str]:
    return {w for w in re.findall(r"[a-z]{4,}", _n(t)) if w not in STOP}


def _err(v) -> bool:
    return isinstance(v, str) and v.startswith(ERR)


def _pesos(x) -> str:
    return "$" + f"{x:,.0f}".replace(",", ".") if isinstance(x, (int, float)) else str(x)


@dataclass
class Hallazgo:
    severidad: str          # ERROR | ADVERTENCIA | OBSERVACIÓN
    tema: str
    lugar: str
    detalle: str
    accion: str = ""


@dataclass
class Auditoria:
    archivo: str
    hallazgos: list[Hallazgo] = field(default_factory=list)
    items: list[dict] = field(default_factory=list)
    resumen: dict = field(default_factory=dict)
    cruce: list[dict] = field(default_factory=list)

    def add(self, *a):
        self.hallazgos.append(Hallazgo(*a))


def _balance(wf, wv) -> tuple[list[dict], dict]:
    ws, vs = wf["BALANCE"], wv["BALANCE"]
    items, res = [], {}
    for r in range(1, ws.max_row + 1):
        cod, desc = vs[f"B{r}"].value, vs[f"C{r}"].value
        etiqueta = _n(vs[f"E{r}"].value)
        if etiqueta.startswith("costos directos"):
            res["cd"], res["fila_cd"], res["formula_cd"] = vs[f"G{r}"].value, r, ws[f"G{r}"].value
        for k, pat in (("A", r"^a$"), ("I", r"^i$"), ("U", r"^u$"), ("IVA", r"^i ?/ ?u$|^iva"), ("total", r"^valor total")):
            if re.match(pat, etiqueta):
                res[k] = (vs[f"F{r}"].value, vs[f"G{r}"].value)
        if cod is not None and re.fullmatch(r"\d+\.\d+", str(cod).strip()) and vs[f"D{r}"].value:
            items.append({"item": str(cod).strip(), "desc": str(desc or ""), "und": vs[f"D{r}"].value,
                          "cant": vs[f"E{r}"].value, "vu": vs[f"F{r}"].value, "vt": vs[f"G{r}"].value, "fila": r,
                          "f_cant": ws[f"E{r}"].value, "f_vu": ws[f"F{r}"].value})
    return items, res


def _insumos_precios(wv) -> set[str]:
    p = wv["PRECIOS "] if "PRECIOS " in wv.sheetnames else wv["PRECIOS"]
    nombres = set()
    for col in ("B", "K", "U", "AC"):
        for r in range(4, p.max_row + 1):
            v = p[f"{col}{r}"].value
            if v:
                nombres.add(_n(v))
    return nombres


def _apu(wf, wv, hoja: str) -> dict:
    ws, vs = wf[hoja], wv[hoja]
    a = {"hoja": hoja, "item": str(vs["B32"].value or "").strip(), "desc": vs["C32"].value, "und": vs["K32"].value,
         "cd": vs["M83"].value, "pu": vs["M85"].value, "insumos": [], "errores": []}
    secciones = {"EQ": range(37, 44), "MAT": range(49, 61), "TR": range(66, 71), "MO": range(76, 81)}
    for sec, filas in secciones.items():
        for r in filas:
            b = ws[f"B{r}"].value
            if b and str(b).strip():
                a["insumos"].append({"sec": sec, "fila": r, "desc": str(b).strip(), "vu": vs[f"M{r}"].value,
                                     "rend": vs[f"K{r}"].value, "cant": vs[f"J{r}"].value,
                                     "f_prest": ws[f"I{r}"].value if sec == "MO" else None,
                                     "jornal": vs[f"H{r}"].value if sec == "MO" else None,
                                     "prest": vs[f"I{r}"].value if sec == "MO" else None})
                if _err(vs[f"M{r}"].value):
                    a["errores"].append(f"B{r} «{b}» -> {vs[f'M{r}'].value}")
    return a


def auditar(ruta: str | Path, dxf: str | Path | None = None) -> Auditoria:
    ruta = Path(ruta)
    wf, wv = load_workbook(ruta), load_workbook(ruta, data_only=True)
    au = Auditoria(ruta.name)
    items, res = _balance(wf, wv)
    au.items = items
    precios = _insumos_precios(wv)
    hojas_apu = [n for n in wf.sheetnames if re.fullmatch(r"\d+\.\d+", n.strip())]

    # ---------------- encabezado
    if "FORMATO" in wv.sheetnames:
        f = wv["FORMATO"]
        objeto, contrato = str(f["B19"].value or ""), str(f["J15"].value or "").strip(" ,.")
        titulo = " ".join(str(wv["BALANCE"][c].value or "") for c in ("B2", "B3"))
        comunes = _palabras(objeto) & (_palabras(titulo) | set().union(*[_palabras(i["desc"]) for i in items]))
        clave_titulo = _palabras(titulo) - {"presupuesto", "unad"}
        if clave_titulo and not (_palabras(objeto) & clave_titulo):
            au.add("ERROR", "Encabezado", "FORMATO!B19",
                   f"El OBJETO no corresponde a este presupuesto («{titulo.strip()}»): dice «{objeto[:160]}…».",
                   "Copiar el objeto exacto de la invitación de este proceso; todas las hojas lo toman de FORMATO.")
        if not contrato:
            au.add("ADVERTENCIA", "Encabezado", "FORMATO!J15", "CONTRATO No. vacío.",
                   "Normal en etapa de invitación; diligenciar al adjudicar.")
        for celda, nombre in (("C27", "Supervisor"), ("K27", "Cargo del supervisor"), ("C25", "Interventor")):
            v = str(f[celda].value or "").strip(" .,")
            if not v:
                au.add("ADVERTENCIA", "Encabezado", f"FORMATO!{celda}", f"{nombre} vacío o con «.».", "Diligenciar o poner N/A.")
        del comunes

    # ---------------- balance
    formula_cd = str(res.get("formula_cd") or "")
    if "/2" in formula_cd.replace(" ", ""):
        au.add("ADVERTENCIA", "Balance", f"BALANCE!G{res.get('fila_cd')}",
               f"El costo directo se calcula como {formula_cd}: suma ítems y subtotales y divide por 2.",
               "Funciona solo si TODOS los subtotales de capítulo están completos; usar la suma de los subtotales.")
    suma = sum(i["vt"] for i in items if isinstance(i["vt"], (int, float)))
    if isinstance(res.get("cd"), (int, float)) and abs(suma - res["cd"]) > len(items):
        au.add("ERROR", "Balance", "BALANCE", f"Costo directo {_pesos(res['cd'])} ≠ suma de ítems {_pesos(suma)}.")
    for i in items:
        for k in ("f_cant", "f_vu"):
            if not (isinstance(i[k], str) and i[k].startswith("=")):
                pass  # en el formato UNAD las cantidades y VU del balance se digitan: se reporta abajo como observación
    au.add("OBSERVACIÓN", "Balance", "BALANCE!E:F",
           "Cantidades y valores unitarios del balance están digitados (no enlazados a memorias ni a los APU). "
           "El APU toma la descripción, unidad y cantidad del balance, pero el valor unitario del balance no sale del APU.",
           "Enlazar F (valor unitario) al precio del APU o dejar la columna de comparación funcionando.")

    # ---------------- APU por ítem
    por_hoja = {n.strip(): n for n in hojas_apu}
    sin_hoja, sin_calculo, copiados, ok = [], [], [], []
    prest_vistos, hm_mal, rend_cuadrado, tr_global = set(), [], [], []
    for it in items:
        hoja = por_hoja.get(it["item"])
        it["estado"] = "sin APU"
        if not hoja:
            sin_hoja.append(it["item"])
            continue
        a = _apu(wf, wv, hoja)
        it["apu"] = a
        # insumos que no corresponden al ítem
        mats = [x for x in a["insumos"] if x["sec"] == "MAT"]
        palabras_item = _palabras(it["desc"])
        ajenos = [x["desc"] for x in mats if not (_palabras(x["desc"]) & palabras_item)]
        faltan = [x["desc"] for x in a["insumos"] if _n(x["desc"]) not in precios and x["sec"] != "EQ"
                  and _err(x["vu"])]
        ajenos_txt = "; ".join(m[:45] for m in ajenos[:4])
        if _err(a["cd"]) or _err(a["pu"]):
            it["estado"] = "APU no calcula"
            sin_calculo.append(it["item"])
            if mats and len(ajenos) == len(mats):
                copiados.append(it["item"])
                it["estado"] = "APU de otro proyecto"
            au.add("ERROR", "APU", f"'{hoja}'!M83",
                   f"Ítem {it['item']} «{it['desc'][:60]}»: el APU no calcula ({a['cd']})"
                   + (f"; sus materiales no corresponden al ítem: {ajenos_txt}" if it["estado"] == "APU de otro proyecto" else "")
                   + (f". Sin precio en PRECIOS: {', '.join(faltan[:4])}" if faltan else "") + ".",
                   "Elaborar el APU con los insumos reales del ítem y agregarlos a la hoja PRECIOS.")
        elif isinstance(a["pu"], (int, float)) and isinstance(it["vu"], (int, float)) and abs(a["pu"] - it["vu"]) > 0.5:
            it["estado"] = "APU ≠ balance"
            au.add("ERROR", "APU", f"'{hoja}'!M85", f"Ítem {it['item']}: precio APU {_pesos(a['pu'])} ≠ balance {_pesos(it['vu'])}.")
        else:
            it["estado"] = "OK"
            ok.append(it["item"])
            # APU que calcula: los insumos se revisan como observación (pueden ser complementarios válidos)
            mat_vu = sum(x["vu"] for x in mats if isinstance(x["vu"], (int, float)))
            if mats and len(ajenos) == len(mats) and isinstance(a["pu"], (int, float)) and a["pu"] and mat_vu / a["pu"] < 0.5 \
                    and _n(it["desc"]).startswith("suministro"):
                au.add("OBSERVACIÓN", "APU", f"'{hoja}'!B49",
                       f"Ítem {it['item']} «{it['desc'][:55]}» incluye suministro pero sus materiales son solo: {ajenos_txt}.",
                       "Verificar que el material principal del ítem esté en el capítulo de materiales.")
        for x in a["insumos"]:
            if x["sec"] == "MO" and isinstance(x["jornal"], (int, float)) and x["jornal"] and isinstance(x["prest"], (int, float)):
                prest_vistos.add(round(x["prest"] / x["jornal"], 2))
            if x["sec"] in ("MO", "EQ") and isinstance(x["rend"], float) and len(repr(x["rend"]).split(".")[-1]) > 8:
                rend_cuadrado.append(it["item"])
                break
        hm = [x for x in a["insumos"] if x["sec"] == "EQ" and "herramienta menor" in _n(x["desc"])]
        mo = sum(x["vu"] for x in a["insumos"] if x["sec"] == "MO" and isinstance(x["vu"], (int, float)))
        for x in hm:
            if isinstance(x["vu"], (int, float)) and mo and not (0.04 <= x["vu"] / mo <= 0.11):
                hm_mal.append(f"{it['item']} ({x['vu'] / mo:.1%} de la MO)")
        trs = [x for x in a["insumos"] if x["sec"] == "TR"]
        if mats and trs and all("transporte de materiales" in _n(x["desc"]) for x in trs):
            tr_global.append(it["item"])

    if sin_hoja:
        au.add("ERROR", "Balance", "BALANCE!I:K", f"{len(sin_hoja)} ítems sin hoja de APU: {', '.join(sin_hoja)}. "
               "La columna «Valor APU» queda en «No existe» y «Dif» en #VALUE!.",
               "Crear el APU de cada ítem (una hoja con el número del ítem).")
    sobrantes = [n for n in hojas_apu if n.strip() not in {i["item"] for i in items}]
    if sobrantes:
        au.add("ADVERTENCIA", "Hojas sobrantes", ", ".join(sobrantes[:6]) + ("…" if len(sobrantes) > 6 else ""),
               f"{len(sobrantes)} hojas de APU no corresponden a ningún ítem del balance (quedan en #N/A).",
               "Eliminarlas antes de entregar (o confirmar que faltan ítems en el balance).")
    if prest_vistos:
        au.add("OBSERVACIÓN", "Prestaciones", "APU!I76",
               f"Prestaciones aplicadas: {', '.join(f'{p:.0%}' for p in sorted(prest_vistos))} del jornal. "
               "Formato R&C usa 52 %.", "Confirmar el factor prestacional exigido por la UNAD / la empresa.")
    if hm_mal:
        au.add("ADVERTENCIA", "Herramienta menor", "APU!B37",
               f"Herramienta menor fuera de 5-10 % de la MO (se calcula como tarifa × rendimiento): {', '.join(hm_mal[:8])}.",
               "Calcularla como % del subtotal de mano de obra (lección de la prueba técnica).")
    if rend_cuadrado:
        au.add("OBSERVACIÓN", "Rendimientos", "APU!K76",
               f"Rendimientos con muchos decimales (ajustados para dar un precio exacto) en: {', '.join(sorted(set(rend_cuadrado)))}.",
               "Usar rendimientos reales de obra; si se ajusta el precio, hacerlo con cantidades justificables.")
    if tr_global:
        au.add("OBSERVACIÓN", "Transportes", "APU!B66",
               f"Transporte como un viaje global y no por material en: {', '.join(tr_global[:10])}.",
               "Aplicar transporte a cada material (lección de la prueba técnica) o justificar el global.")
    # unidades sospechosas
    for it in items:
        d = _n(it["desc"])
        if ("tierra" in d or "relleno" in d or "recebo" in d) and _n(it["und"]) == "m2":
            au.add("ADVERTENCIA", "Unidades", f"BALANCE!D{it['fila']}",
                   f"Ítem {it['item']} «{it['desc'][:60]}» en m²: los suministros de tierra/relleno suelen ir en m³.",
                   "Confirmar la unidad (si es m², la descripción debe indicar el espesor).")
    au.resumen = {"items": len(items), "apu_ok": len(ok), "apu_con_errores": len(sin_calculo), "sin_apu": len(sin_hoja),
                  "insumos_ajenos": len(copiados), "hojas_sobrantes": len(sobrantes), "costo_directo": res.get("cd"),
                  "aiu": {k: res.get(k) for k in ("A", "I", "U", "IVA")}, "valor_total": (res.get("total") or (None, None))[1]}
    if dxf:
        au.cruce = cruzar_con_plano(items, dxf)
    return au


# ------------------------------------------------------------------ cruce plano vs presupuesto
REGLAS_CRUCE = [  # (palabras del ítem, unidad, cómo medir en el plano)
    ({"adoquin"}, "m2", ("capa", r"adoquin")),
    ({"concreto", "estampado"}, "m2", ("capa", r"concreto")),
    ({"deck"}, "m2", ("capa", r"achu-madera|deck")),
    ({"plantas", "ornamentales"}, "m2", ("capa", r"vegetacion|cesped|zonas? verdes")),
    ({"arboles"}, "und", ("bloque", r"arbol|2d-ar|tree")),
    ({"bancas"}, "und", ("bloque", r"banca")),
    ({"luminaria"}, "und", ("bloque", r"(^|[^a-z])lum|cajalum|poste|reflector")),
    ({"gravilla"}, "m3", ("capa", r"gravilla")),
]


def cruzar_con_plano(items, dxf) -> list[dict]:
    from .cad import leer
    r = leer(dxf)
    filas = []
    for it in items:
        pal = _palabras(it["desc"])
        for claves, und, (tipo, patron) in REGLAS_CRUCE:
            if not claves <= pal and not (len(claves) == 1 and claves & pal):
                continue
            if _n(it["und"]) != und:          # solo se comparan cantidades de la misma unidad
                continue
            rx = re.compile(patron, re.I)
            if tipo == "capa":
                capas = [c for c in r["capas"] if rx.search(_n(c["capa"]))]
                valor = sum(max(c["m2"], c["m2_sombreado"]) for c in capas)
                fuente = ", ".join(f"{c['capa']} ({max(c['m2'], c['m2_sombreado']):,.1f} m²)" for c in capas)
            else:
                bl = {b: n for b, n in r["bloques_total"].items() if rx.search(_n(b))}
                valor = sum(bl.values())
                fuente = ", ".join(f"{b}: {n}" for b, n in bl.items())
            if not fuente:
                continue
            cant = it["cant"] if isinstance(it["cant"], (int, float)) else None
            dif = (valor - cant) / cant if cant else None
            filas.append({"item": it["item"], "desc": it["desc"][:70], "und": it["und"], "presupuesto": cant,
                          "plano": round(valor, 2), "dif": dif, "fuente": fuente})
            break
    return filas


# ------------------------------------------------------------------ salidas
def reporte_md(au: Auditoria) -> str:
    s = au.resumen
    L = [f"# Auditoría APU - {au.archivo}", "", f"Fecha: {date.today():%d/%m/%Y} · Formato UNAD F-14-3-5", "",
         "## Resumen", "",
         f"- Ítems en el balance: **{s['items']}**",
         f"- APU que calculan y cuadran con el balance: **{s['apu_ok']}**",
         f"- APU con errores (no calculan): **{s['apu_con_errores']}**",
         f"- Ítems **sin** hoja de APU: **{s['sin_apu']}**",
         f"- de ellos, con materiales de otro proyecto: **{s['insumos_ajenos']}**",
         f"- Hojas sobrantes: **{s['hojas_sobrantes']}**",
         f"- Costo directo: {_pesos(s['costo_directo'])} · Valor total: {_pesos(s['valor_total'])}",
         "- AIU: " + ", ".join(f"{k} {v[0]:.0%}" for k, v in s["aiu"].items() if v and isinstance(v[0], (int, float))), ""]
    for sev in ("ERROR", "ADVERTENCIA", "OBSERVACIÓN"):
        hs = [h for h in au.hallazgos if h.severidad == sev]
        if hs:
            L += [f"## {sev} ({len(hs)})", ""]
            for h in hs:
                L.append(f"- **[{h.tema}]** `{h.lugar}`: {h.detalle}" + (f"\n  - *Qué hacer:* {h.accion}" if h.accion else ""))
            L.append("")
    L += ["## Estado por ítem", "", "| Ítem | Descripción | Und | Cantidad | VU balance | Estado APU |", "|---|---|---|---:|---:|---|"]
    for it in au.items:
        L.append(f"| {it['item']} | {it['desc'][:60]} | {it['und']} | {it['cant']} | {_pesos(it['vu'])} | {it['estado']} |")
    if au.cruce:
        L += ["", "## Cruce presupuesto vs plano DXF (verificar en el plano)", "",
              "| Ítem | Descripción | Und | Presupuesto | Plano | Dif. | Medido en |", "|---|---|---|---:|---:|---:|---|"]
        for c in au.cruce:
            dif = f"{c['dif']:+.0%}" if c["dif"] is not None else "-"
            L.append(f"| {c['item']} | {c['desc'][:45]} | {c['und']} | {c['presupuesto']} | {c['plano']:,.1f} | {dif} | {c['fuente'][:90]} |")
        L += ["", "*El plano puede incluir varias vistas o elementos existentes: una diferencia indica revisar, no un error "
              "confirmado.*"]
    return "\n".join(L)


def a_excel(au: Auditoria, destino: Path) -> Path:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    wb = Workbook()
    ws = wb.active
    ws.title = "HALLAZGOS"
    colores = {"ERROR": "FFC7CE", "ADVERTENCIA": "FFEB9C", "OBSERVACIÓN": "DDEBF7"}
    cab = ["Severidad", "Tema", "Lugar", "Detalle", "Qué hacer", "Estado (llenar)"]
    for i, t in enumerate(cab, 1):
        ws.cell(1, i, t).font = Font(name="Arial", bold=True)
    for r, h in enumerate(au.hallazgos, 2):
        for i, v in enumerate([h.severidad, h.tema, h.lugar, h.detalle, h.accion, ""], 1):
            c = ws.cell(r, i, v)
            c.font = Font(name="Arial", size=9)
            c.alignment = Alignment(wrap_text=True, vertical="top")
        ws.cell(r, 1).fill = PatternFill("solid", fgColor=colores[h.severidad])
    for col, w in zip("ABCDEF", [13, 16, 22, 80, 50, 16]):
        ws.column_dimensions[col].width = w
    ws2 = wb.create_sheet("ITEMS")
    for i, t in enumerate(["Ítem", "Descripción", "Und", "Cantidad", "VU balance", "Valor total", "Estado APU"], 1):
        ws2.cell(1, i, t).font = Font(name="Arial", bold=True)
    for r, it in enumerate(au.items, 2):
        for i, v in enumerate([it["item"], it["desc"], it["und"], it["cant"], it["vu"], it["vt"], it["estado"]], 1):
            ws2.cell(r, i, v).font = Font(name="Arial", size=9)
        ws2.cell(r, 5).number_format = ws2.cell(r, 6).number_format = '"$"#,##0'
    n = len(au.items) + 1
    ws2.cell(n + 1, 5, "TOTAL").font = Font(name="Arial", bold=True)
    ws2.cell(n + 1, 6, f"=SUM(F2:F{n})").number_format = '"$"#,##0'
    for col, w in zip("ABCDEFG", [7, 70, 6, 10, 14, 16, 22]):
        ws2.column_dimensions[col].width = w
    if au.cruce:
        ws3 = wb.create_sheet("CRUCE PLANO")
        for i, t in enumerate(["Ítem", "Descripción", "Und", "Presupuesto", "Plano DXF", "Diferencia", "Medido en"], 1):
            ws3.cell(1, i, t).font = Font(name="Arial", bold=True)
        for r, c in enumerate(au.cruce, 2):
            for i, v in enumerate([c["item"], c["desc"], c["und"], c["presupuesto"], c["plano"], None, c["fuente"]], 1):
                ws3.cell(r, i, v).font = Font(name="Arial", size=9)
            ws3.cell(r, 6, f"=IF(D{r}>0,E{r}/D{r}-1,\"\")").number_format = "0%"
        for col, w in zip("ABCDEFG", [7, 55, 6, 12, 12, 11, 70]):
            ws3.column_dimensions[col].width = w
    wb.save(destino)
    return destino


def main(argv=None):
    ap = argparse.ArgumentParser(description="Auditor formato UNAD F-14-3-5")
    ap.add_argument("archivo")
    ap.add_argument("--dxf")
    ap.add_argument("--salida", default=None)
    a = ap.parse_args(argv)
    au = auditar(a.archivo, a.dxf)
    carpeta = Path(a.salida or Path(a.archivo).parent)
    carpeta.mkdir(parents=True, exist_ok=True)
    base = carpeta / f"AUDITORIA_{Path(a.archivo).stem}_{date.today():%Y-%m-%d}"
    md = reporte_md(au)
    base.with_suffix(".md").write_text(md, encoding="utf-8")
    a_excel(au, base.with_suffix(".xlsx"))
    print(md)
    print(f"\nReporte: {base.with_suffix('.md')}\nExcel:   {base.with_suffix('.xlsx')}")


if __name__ == "__main__":
    main()
