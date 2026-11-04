"""Proceso de cotización a partir de los APU: necesidades, solicitudes a proveedores y cuadro comparativo.

1. necesidades(): cantidad total de cada insumo en la obra = cantidad en el APU × cantidad del ítem (equipos: días).
2. libro(): Excel con NECESIDADES, COMPARATIVO (3 proveedores por insumo, fórmulas que eligen el menor precio),
   RESUMEN por categoría y PROVEEDORES (directorio para llenar).
3. solicitudes(): una solicitud de cotización en BORRADOR (Word + texto para correo/WhatsApp) por categoría.
4. desde_comparativo(): lee el comparativo diligenciado y devuelve las cotizaciones elegidas en el formato que usa
   apu_unad (spec["cotizaciones"]) para regenerar los APU con precios reales.

Uso:
  python -m arkcrow.cotizaciones OFICIAL.xlsx especificacion.json carpeta_salida [--obra "nombre"] [--lugar "Corozal, Sucre"]
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Font, PatternFill

from .libro_costos import F_NEGRITA, F_NORMAL, F_TITULO, MONEDA, RELLENO_CAP, RELLENO_TITULO, RELLENO_TOTAL, _c

AMARILLO = PatternFill("solid", fgColor="FFF2CC")
CATEGORIAS = [
    ("Concretos y acero", ["concreto premezclado", "acero de refuerzo", "alambre negro", "malla electrosoldada",
                           "tabla formaleta", "formaleta curva"]),
    ("Pavimentos, agregados y geosintéticos", ["adoquín", "arena", "gravilla", "geotextil", "grapa de anclaje",
                                               "endurecedor", "desmoldante", "sellador acrílico"]),
    ("Madera y deck", ["deck", "listón", "tornillo inoxidable", "sellante protector", "tutor"]),
    ("Hidráulica, riego y bombeo", ["pvc presión", "accesorio pvc", "limpiador pvc", "pegante pvc", "tanque",
                                    "kit de conexión", "válvula", "flotador", "aspersor", "manómetro", "motobomba",
                                    "arrancador", "accesorios hidráulicos"]),
    ("Eléctricos e iluminación", ["tablero", "cooperweld", "cable", "conector y soldadura", "caja", "conduit",
                                  "tomacorriente", "prensaestopa", "tapa para caja", "luminaria", "breaker",
                                  "interruptor", "emt", "grapa doble", "chazo", "tornillo acero", "alambre cobre"]),
    ("Vivero y jardinería", ["árbol", "planta", "tierra negra", "abono", "hidrogel", "enraizante"]),
    ("Mobiliario urbano", ["banca", "anclaje epóxico", "parasol"]),
    ("Metalmecánica y cubiertas", ["puerta metálica", "cerradura", "perfil tubular", "teja", "tubo galvanizado",
                                   "platina", "anticorrosivo", "pintura tipo esmalte"]),
    ("Servicios y consumibles", ["disposición final", "insumos de aseo", "papelería"]),
]


def categoria(desc: str, tipo: str) -> str:
    if tipo == "EQ":
        return "Alquiler de equipos"
    d = desc.lower()
    for nombre, claves in CATEGORIAS:
        if any(k in d for k in claves):
            return nombre
    return "Otros"


def necesidades(oficial: str | Path, spec: dict) -> list[dict]:
    from .apu_unad import leer_oficial
    items, precios = leer_oficial(Path(oficial))
    ref = {}
    for k, filas in precios.items():
        for d, u, p, _ in filas:
            ref[(k, d.strip().lower())] = (u, p, "PRECIOS oficial")
    for d, u, p, _ in spec["precios_nuevos"]["MAT"]:
        ref[("MAT", d.lower())] = (u, p, "SUPUESTO")
    for d, t, p in spec["precios_nuevos"].get("EQ", []):
        ref[("EQ", d.lower())] = ("día", p, "SUPUESTO")
    tot: dict = {}
    for a in spec["apus"]:
        q = items[a["item"]]["cant"]
        for d, c in a.get("mat", []):
            e = tot.setdefault(("MAT", d), {"cant": 0.0, "items": set()})
            e["cant"] += c * q
            e["items"].add(a["item"])
        for d, rend in a.get("eq", []):
            e = tot.setdefault(("EQ", d), {"cant": 0.0, "items": set()})
            e["cant"] += q / rend
            e["items"].add(a["item"])
    filas = []
    for (tipo, d), e in tot.items():
        u, p, fuente = ref.get((tipo, d.strip().lower()), (None, None, "sin precio"))
        if tipo == "EQ":
            u = "día"
        filas.append({"tipo": tipo, "insumo": d, "und": u, "cantidad": round(e["cant"], 2), "precio_ref": p,
                      "fuente_ref": fuente, "categoria": categoria(d, tipo),
                      "items": ", ".join(sorted(e["items"], key=lambda x: [int(n) for n in x.split(".")]))})
    orden = [c for c, _ in CATEGORIAS] + ["Alquiler de equipos", "Otros"]
    filas.sort(key=lambda f: (orden.index(f["categoria"]), -(f["precio_ref"] or 0) * f["cantidad"]))
    return filas


def libro(filas: list[dict], salida: str | Path, obra: str, referencias: dict | None = None) -> Path:
    referencias = referencias or {}
    wb = Workbook()
    ws = wb.active
    ws.title = "COMPARATIVO"
    _c(ws, "A1", f"CUADRO COMPARATIVO DE COTIZACIONES - {obra}", F_TITULO, relleno=RELLENO_TITULO)
    ws.merge_cells("A1:R1")
    _c(ws, "A2", "Llene las celdas amarillas con lo que respondan los proveedores (precio unitario ANTES de IVA, puesto en "
                 "obra). La columna «Mejor precio» elige el menor; si no hay cotizaciones se usa la referencia.",
       Font(name="Arial", size=9, italic=True), borde=False)
    ws.merge_cells("A2:R2")
    cab = ["Categoría", "Insumo", "Und", "Cantidad obra", "Precio referencia", "Fuente referencia",
           "Proveedor 1", "Precio 1", "Proveedor 2", "Precio 2", "Proveedor 3", "Precio 3",
           "Mejor precio", "Proveedor elegido", "Valor total", "Base del valor", "Ítems APU", "Observaciones"]
    for i, t in enumerate(cab, 1):
        c = ws.cell(4, i, t)
        c.font = Font(name="Arial", size=9, bold=True, color="FFFFFF")
        c.fill = RELLENO_TITULO
        c.alignment = Alignment(wrap_text=True, horizontal="center", vertical="center")
    ws.row_dimensions[4].height = 30
    r = 5
    for f in filas:
        rf = referencias.get(f["insumo"])
        p_ref, fuente = (rf["precio"], f"WEB: {rf['fuente']}") if rf else (f["precio_ref"], f["fuente_ref"])
        vals = [f["categoria"], f["insumo"], f["und"], f["cantidad"], p_ref, fuente]
        for i, v in enumerate(vals, 1):
            c = ws.cell(r, i, v)
            c.font = F_NORMAL
        ws.cell(r, 4).number_format = "#,##0.00"
        ws.cell(r, 5).number_format = MONEDA
        for col in range(7, 13):
            c = ws.cell(r, col)
            c.fill = AMARILLO
            c.font = Font(name="Arial", size=9, color="0000FF")
            if col % 2 == 0:
                c.number_format = MONEDA
        ws.cell(r, 13, f'=IF(COUNT(H{r},J{r},L{r})=0,"",MIN(H{r},J{r},L{r}))').number_format = MONEDA
        ws.cell(r, 14, f'=IF(M{r}="","",IF(H{r}=M{r},G{r},IF(J{r}=M{r},I{r},K{r})))')
        ws.cell(r, 15, f'=ROUND(D{r}*IF(M{r}="",E{r},M{r}),0)').number_format = MONEDA
        ws.cell(r, 16, f'=IF(M{r}="","Referencia","Cotización")')
        ws.cell(r, 17, f["items"]).font = Font(name="Arial", size=8)
        for col in (13, 14, 15, 16):
            ws.cell(r, col).font = F_NORMAL
        r += 1
    fin = r - 1
    _c(ws, f"N{r}", "TOTAL COMPRAS", F_NEGRITA, relleno=RELLENO_TOTAL)
    _c(ws, f"O{r}", f"=SUM(O5:O{fin})", F_NEGRITA, MONEDA, RELLENO_TOTAL)
    ws.conditional_formatting.add(f"P5:P{fin}", CellIsRule(operator="equal", formula=['"Cotización"'],
                                                            fill=PatternFill("solid", fgColor="C6EFCE")))
    for col, w in zip("ABCDEFGHIJKLMNOPQR", [24, 48, 7, 11, 13, 26, 16, 12, 16, 12, 16, 12, 12, 18, 15, 12, 18, 26]):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "C5"
    ws.auto_filter.ref = f"A4:R{fin}"

    res = wb.create_sheet("RESUMEN", 0)
    _c(res, "B2", f"RESUMEN DE COMPRAS POR CATEGORÍA - {obra}", F_TITULO, relleno=RELLENO_TITULO)
    res.merge_cells("B2:F2")
    for i, t in enumerate(["Categoría", "Insumos", "Valor estimado", "Cotizados", "% del total"], 2):
        _c(res, f"{chr(64 + i)}4", t, F_NEGRITA, relleno=RELLENO_CAP)
    cats = list(dict.fromkeys(f["categoria"] for f in filas))
    for k, cat in enumerate(cats, 5):
        _c(res, f"B{k}", cat, F_NORMAL)
        _c(res, f"C{k}", f'=COUNTIF(COMPARATIVO!$A$5:$A${fin},B{k})', F_NORMAL)
        _c(res, f"D{k}", f'=SUMIF(COMPARATIVO!$A$5:$A${fin},B{k},COMPARATIVO!$O$5:$O${fin})', F_NORMAL, MONEDA)
        _c(res, f"E{k}", f'=COUNTIFS(COMPARATIVO!$A$5:$A${fin},B{k},COMPARATIVO!$P$5:$P${fin},"Cotización")', F_NORMAL)
        _c(res, f"F{k}", f"=IF($D${5 + len(cats)}>0,D{k}/$D${5 + len(cats)},0)", F_NORMAL, "0.0%")
    t = 5 + len(cats)
    _c(res, f"B{t}", "TOTAL", F_NEGRITA, relleno=RELLENO_TOTAL)
    for col in "CDE":
        _c(res, f"{col}{t}", f"=SUM({col}5:{col}{t - 1})", F_NEGRITA, MONEDA if col == "D" else None, RELLENO_TOTAL)
    for col, w in zip("BCDEF", [40, 10, 18, 11, 11]):
        res.column_dimensions[col].width = w

    prov = wb.create_sheet("PROVEEDORES")
    for i, t in enumerate(["Categoría", "Proveedor", "Ciudad", "Contacto", "Teléfono / WhatsApp", "Correo",
                           "Fecha de envío", "Fecha de respuesta", "Estado"], 1):
        c = prov.cell(1, i, t)
        c.font = Font(name="Arial", size=9, bold=True, color="FFFFFF")
        c.fill = RELLENO_TITULO
    rr = 2
    for cat in cats:
        for _ in range(3):
            prov.cell(rr, 1, cat).font = F_NORMAL
            for col in range(2, 10):
                prov.cell(rr, col).fill = AMARILLO
            rr += 1
    for col, w in zip("ABCDEFGHI", [34, 30, 14, 22, 18, 28, 13, 13, 14]):
        prov.column_dimensions[col].width = w
    wb.calculation.fullCalcOnLoad = True
    wb.save(salida)
    return Path(salida)


def solicitudes(filas: list[dict], carpeta: str | Path, obra: str, lugar: str, contacto: dict) -> list[Path]:
    from docx.shared import Pt

    from . import documentos as D
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    salidas = []
    for cat in dict.fromkeys(f["categoria"] for f in filas):
        sel = [f for f in filas if f["categoria"] == cat]
        alquiler = cat == "Alquiler de equipos"
        doc = D.nuevo_documento(f"Solicitud de cotización - {cat}", None, borrador=True)
        doc.add_paragraph(f"{lugar.split(',')[0]}, {D.fecha_co(date.today())}")
        doc.add_paragraph("Señores\n[NOMBRE DEL PROVEEDOR]\nCiudad")
        p = doc.add_paragraph()
        p.add_run("Asunto: ").bold = True
        p.add_run(f"Solicitud de cotización - {cat.lower()} - obra «{obra}».")
        doc.add_paragraph("Cordial saludo.")
        doc.add_paragraph(
            f"R&C Redes y Construcciones S.A.S. se encuentra preparando la ejecución de la obra «{obra}», en {lugar}. "
            f"Agradecemos nos coticen {'el alquiler de los siguientes equipos' if alquiler else 'los siguientes elementos'}, "
            "en las cantidades aproximadas indicadas:")
        D.tabla(doc, ["N°", "Descripción / especificación", "Und", "Cantidad aprox."],
                [[i, f["insumo"], f["und"] or "", f"{f['cantidad']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")]
                 for i, f in enumerate(sel, 1)], [1.0, 11.0, 1.5, 3.0])
        D.subtitulo(doc, "Condiciones de la cotización")
        condiciones = [
            "Precios en pesos colombianos, con el IVA discriminado.",
            f"Precio puesto en obra ({lugar}); si el transporte se cobra aparte, indicarlo por separado.",
            "Validez de la oferta: mínimo 30 días calendario.",
            "Tiempo de entrega o disponibilidad, y forma de pago.",
            "Ficha técnica, garantía y certificaciones del producto cuando apliquen.",
            "Si no maneja alguno de los elementos, por favor cotice los demás e indíquelo.",
        ]
        if alquiler:
            condiciones[1] = f"Tarifa por día de alquiler, incluyendo transporte de ida y regreso a {lugar}."
        for c in condiciones:
            doc.add_paragraph(c, style="List Bullet")
        doc.add_paragraph("Las cantidades son aproximadas y pueden variar según el replanteo de obra. "
                          "Agradecemos su respuesta antes del [COMPLETAR FECHA].")
        doc.add_paragraph("Cordialmente,")
        D.firmas(doc, [(contacto.get("nombre", ""), f"{contacto.get('cargo', '')}\nR&C Redes y Construcciones S.A.S.\n"
                                                  f"{contacto.get('telefono', '[TELÉFONO]')} · {contacto.get('correo', '[CORREO]')}")])
        for par in doc.paragraphs:
            for run in par.runs:
                if run.font.size is None:
                    run.font.size = Pt(10)
        nombre = re.sub(r"[^A-Za-z0-9]+", "_", _ascii(cat)).strip("_")
        ruta = carpeta / f"Solicitud_cotizacion_{nombre}_BORRADOR.docx"
        doc.save(ruta)
        txt = [f"Asunto: Solicitud de cotización - {cat.lower()} - {obra}", "", "Cordial saludo.", "",
               f"Desde R&C Redes y Construcciones S.A.S. les solicitamos cotización para la obra «{obra}» ({lugar}):", ""]
        txt += [f"{i}. {f['insumo']} - {f['cantidad']:,.2f} {f['und'] or ''}".replace(",", "X").replace(".", ",").replace("X", ".")
                for i, f in enumerate(sel, 1)]
        txt += ["", "Por favor indicar: precio unitario sin IVA, IVA, valor puesto en obra o flete aparte, validez, tiempo de "
                    "entrega y forma de pago.", "", "Cordialmente,", contacto.get("nombre", ""), contacto.get("cargo", ""),
                "R&C Redes y Construcciones S.A.S."]
        ruta.with_suffix(".txt").write_text("\n".join(txt), encoding="utf-8")
        salidas.append(ruta)
    return salidas


def desde_comparativo(ruta: str | Path) -> dict:
    """Cotizaciones elegidas en el comparativo -> {insumo: {precio, proveedor, fecha}} para spec['cotizaciones']."""
    ws = load_workbook(ruta, data_only=True)["COMPARATIVO"]
    out = {}
    for r in range(5, ws.max_row + 1):
        insumo, mejor, prov = ws.cell(r, 2).value, ws.cell(r, 13).value, ws.cell(r, 14).value
        if insumo and isinstance(mejor, (int, float)) and mejor > 0:
            out[str(insumo).strip()] = {"precio": mejor, "proveedor": str(prov or ""), "fecha": f"{date.today():%d/%m/%Y}"}
    return out


def _ascii(t: str) -> str:
    import unicodedata
    return unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()


def main(argv=None):
    ap = argparse.ArgumentParser(description="Proceso de cotización desde los APU")
    ap.add_argument("oficial")
    ap.add_argument("especificacion")
    ap.add_argument("salida")
    ap.add_argument("--obra", default="Paisajismo UNAD CEAD Corozal")
    ap.add_argument("--lugar", default="Corozal, Sucre")
    ap.add_argument("--referencias", help="JSON {insumo: {precio, fuente}} con precios de referencia web")
    a = ap.parse_args(argv)
    spec = json.loads(Path(a.especificacion).read_text(encoding="utf-8"))
    filas = necesidades(a.oficial, spec)
    refs = json.loads(Path(a.referencias).read_text(encoding="utf-8")) if a.referencias else {}
    carpeta = Path(a.salida)
    carpeta.mkdir(parents=True, exist_ok=True)
    x = libro(filas, carpeta / f"Cuadro_comparativo_cotizaciones_{date.today():%Y-%m-%d}.xlsx", a.obra, refs)
    contacto = {"nombre": "Arq. Cristian Mauricio Cuervo Ramírez", "cargo": "Arquitecto residente de obra"}
    docs = solicitudes(filas, carpeta / "solicitudes", a.obra, a.lugar, contacto)
    print(f"{len(filas)} insumos · cuadro: {x}\n{len(docs)} solicitudes en {carpeta / 'solicitudes'}")


if __name__ == "__main__":
    main()
