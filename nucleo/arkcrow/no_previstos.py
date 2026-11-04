"""Ítems no previstos (NP): APU + memoria + balance de los NP y oficio de solicitud de aprobación (borrador).

Especificación: proyectos/<obra>/np/<archivo>.json
  {"solicitud": "01", "destinatario": "...", "cargo_destinatario": "...",
   "items": [ {codigo: "NP-01", descripcion, unidad, plano, memoria: [...], apu: {...},
               justificacion: "...", causa: "..."} ]}
Usa el mismo formato de ítem de proyecto.json, así reutiliza el generador de libro, el auditor y el revisor.

Uso: python -m arkcrow.no_previstos <obra> proyectos/<obra>/np/<archivo>.json
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

from openpyxl import load_workbook

from . import db
from . import documentos as D
from .libro_costos import LibroCostos
from .revisor_calidad import revisar


def generar(obra: str, ruta_spec: str | Path) -> dict:
    spec = json.loads(Path(ruta_spec).read_text(encoding="utf-8"))
    base = D.cargar_proyecto(obra)
    items = []
    for it in spec["items"]:
        it = dict(it)
        it["tipo_item"] = "Ítem no previsto"
        items.append(it)
    proyecto = {"obra": obra, "encabezado": base["encabezado"], "parametros": base["parametros"],
                "supuestos": spec.get("supuestos", []),
                "capitulos": [{"codigo": "12", "nombre": "ÍTEMS NO PREVISTOS", "items": items}]}
    db.inicializar()
    wb = LibroCostos(proyecto, db.insumos()).construir()
    n = spec.get("solicitud", "01")
    xlsx = D.salidas(obra) / f"NP_solicitud_{n}_APU_Memoria_Balance_{date.today():%Y-%m-%d}.xlsx"
    wb.save(xlsx)
    ok, md, rep = revisar(xlsx, entregar=True)

    # valores calculados para el oficio
    ws = load_workbook(xlsx, data_only=True)["BALANCE"]
    filas, resumen = [], {}
    for f in ws.iter_rows(values_only=True):
        if isinstance(f[0], str) and f[0].startswith("NP-") and f[2]:
            filas.append(f)
        if isinstance(f[0], str) and f[0] in ("TOTAL COSTO DIRECTO", "VALOR TOTAL"):
            resumen[f[0]] = f[5]
    enc = base["encabezado"]
    doc = D.nuevo_documento(f"Solicitud de aprobación de ítems no previstos N° {n}", obra, borrador=True)
    doc.add_paragraph(f"Bogotá D.C., {D.fecha_co(date.today())}")
    doc.add_paragraph(f"Señor(a)\n{spec.get('destinatario', enc.get('supervisor', ''))}\n"
                      f"{spec.get('cargo_destinatario', enc.get('cargo_supervisor', ''))}\nCiudad")
    p = doc.add_paragraph()
    p.add_run("Asunto: ").bold = True
    p.add_run(f"Solicitud de aprobación de ítems no previstos - Contrato N° {enc.get('contrato', '')}. "
              f"Objeto: {enc.get('objeto', '')}.")
    doc.add_paragraph("Respetado(a) señor(a):")
    doc.add_paragraph(
        "Por medio de la presente, y en cumplimiento de lo establecido en el contrato de la referencia, nos permitimos "
        "solicitar la revisión y aprobación de los siguientes ítems no previstos, necesarios para la correcta "
        "ejecución y funcionalidad de la obra, los cuales no se encuentran incluidos en la propuesta económica. "
        "Se adjuntan los análisis de precios unitarios (APU) y las memorias de cantidades correspondientes.")
    D.tabla(doc, ["Ítem", "Descripción", "Und", "Cantidad", "Valor unitario", "Valor total"],
            [[f[0], f[1], f[2], f"{f[3]:.2f}".replace(".", ","), D.pesos(f[4]), D.pesos(f[5])] for f in filas],
            [1.8, 7.5, 1.2, 1.8, 2.5, 2.7])
    doc.add_paragraph(f"Costo directo: {D.pesos(resumen.get('TOTAL COSTO DIRECTO', 0))}. "
                      f"Valor total con AIU (A {base['parametros']['administracion']:.0%}, "
                      f"I {base['parametros']['imprevistos']:.0%}, U {base['parametros']['utilidad']:.0%}, "
                      f"IVA {base['parametros']['iva_utilidad']:.0%} sobre la utilidad): "
                      f"{D.pesos(resumen.get('VALOR TOTAL', 0))}.")
    D.subtitulo(doc, "Justificación técnica")
    for it in spec["items"]:
        p = doc.add_paragraph(style="List Bullet")
        p.add_run(f"{it['codigo']}: ").bold = True
        p.add_run(f"{it.get('justificacion', '[COMPLETAR JUSTIFICACIÓN]')}")
        if it.get("causa"):
            p.add_run(f" Causa: {it['causa']}")
    doc.add_paragraph("Quedamos atentos a sus comentarios y a la aprobación para proceder con la ejecución. "
                      "Los precios se mantendrán vigentes por treinta (30) días calendario.")
    D.subtitulo(doc, "Anexos")
    doc.add_paragraph(f"1. {xlsx.name} (APU, memorias de cantidades y balance de los NP).", style="List Number")
    doc.add_paragraph("Cordialmente,")
    D.firmas(doc, [(enc.get("elaboro", ""), f"Arquitecto residente - {enc.get('contratista', '')}")])
    oficio = D.salidas(obra) / f"Oficio_solicitud_NP_{n}_BORRADOR_{date.today():%Y-%m-%d}.docx"
    doc.save(oficio)
    return {"xlsx": xlsx, "oficio": oficio, "aprobado": ok, "revision": rep, "items": len(filas),
            "costo_directo": resumen.get("TOTAL COSTO DIRECTO"), "valor_total": resumen.get("VALOR TOTAL")}


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    r = generar(sys.argv[1], sys.argv[2])
    for k, v in r.items():
        print(f"{k}: {v}")
