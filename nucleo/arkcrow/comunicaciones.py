"""Comunicaciones de obra en BORRADOR: correos, oficios y actas de comité.

NUNCA se envía nada: este módulo no tiene código de envío. Los borradores quedan en
proyectos/<obra>/borradores/ para que el usuario los revise, firme y envíe por su cuenta.
Si hay modelo local/nube disponible, `redactar()` propone el cuerpo; si no, se usa la plantilla.

Uso:
  python -m arkcrow.comunicaciones correo <obra> --para "Interventoría" --asunto "..." --puntos "a" "b"
  python -m arkcrow.comunicaciones oficio <obra> --para "Arq. ..." --cargo "..." --asunto "..." --puntos "a" "b"
  python -m arkcrow.comunicaciones acta <obra> archivo_comite.json
"""
from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from email.message import EmailMessage
from pathlib import Path

from . import documentos as D

SALUDO = "Cordial saludo."
CIERRE = "Quedamos atentos a sus comentarios."


def carpeta(obra: str) -> Path:
    d = D.carpeta_obra(obra) / "borradores"
    d.mkdir(exist_ok=True)
    return d


def redactar(instruccion: str, contexto: str = "") -> str | None:
    """Pide al modelo (si existe) un cuerpo en tono profesional colombiano. Devuelve None si no hay modelo."""
    try:
        from . import llm
        if not llm.elegir_modelo():
            return None
        return llm.chat([{"role": "system", "content": "Redactas comunicaciones de obra en español de Colombia, tono "
                          "profesional, cordial y concreto. No inventes datos: deja [COMPLETAR] donde falte información."},
                         {"role": "user", "content": f"{instruccion}\n\nContexto:\n{contexto}"}])
    except Exception:  # noqa: BLE001
        return None


def _cuerpo(puntos: list[str], intro: str) -> str:
    lineas = [SALUDO, "", intro, ""]
    lineas += [f"{i}. {p}" for i, p in enumerate(puntos, start=1)]
    lineas += ["", CIERRE]
    return "\n".join(lineas)


def correo(obra: str, para: str, asunto: str, puntos: list[str], cuerpo: str | None = None) -> Path:
    enc = D.encabezado_obra(obra)
    cuerpo = cuerpo or _cuerpo(puntos, f"En relación con el contrato {enc.get('contrato', '[COMPLETAR]')}, cuyo objeto es "
                                       f"«{enc.get('objeto', '[COMPLETAR]')}», nos permitimos informar/solicitar lo siguiente:")
    firma = f"\n\n{enc.get('elaboro', '')}\nArquitecto residente de obra\n{enc.get('contratista', '')}"
    msg = EmailMessage()
    msg["To"] = para
    msg["Subject"] = f"[BORRADOR] {asunto}"
    msg["X-Unsent"] = "1"          # Outlook lo abre como borrador para editar, no lo envía
    msg.set_content(cuerpo + firma)
    destino = carpeta(obra) / f"{datetime.now():%Y-%m-%d_%H%M}_correo_{_slug(asunto)}.eml"
    destino.write_bytes(bytes(msg))
    destino.with_suffix(".txt").write_text(f"PARA: {para}\nASUNTO: {asunto}\n\n{cuerpo}{firma}\n", encoding="utf-8")
    return destino


def oficio(obra: str, para: str, cargo: str, asunto: str, puntos: list[str], cuerpo: str | None = None,
           consecutivo: str = "[N°]") -> Path:
    enc = D.encabezado_obra(obra)
    doc = D.nuevo_documento(f"Oficio {consecutivo}", obra, borrador=True)
    doc.add_paragraph(f"Bogotá D.C., {D.fecha_co(date.today())}")
    doc.add_paragraph(f"Señor(a)\n{para}\n{cargo}\nCiudad")
    p = doc.add_paragraph()
    p.add_run("Asunto: ").bold = True
    p.add_run(asunto)
    p = doc.add_paragraph()
    p.add_run("Referencia: ").bold = True
    p.add_run(f"Contrato N° {enc.get('contrato', '[COMPLETAR]')} - {enc.get('objeto', '')}")
    doc.add_paragraph("Respetado(a) señor(a):")
    if cuerpo:
        for par in cuerpo.split("\n\n"):
            doc.add_paragraph(par.strip())
    else:
        doc.add_paragraph("De manera atenta, en el marco del contrato de la referencia, nos permitimos manifestar lo siguiente:")
        for pt in puntos:
            doc.add_paragraph(pt, style="List Number")
    doc.add_paragraph(CIERRE)
    doc.add_paragraph("Cordialmente,")
    D.firmas(doc, [(enc.get("elaboro", ""), f"Arquitecto residente - {enc.get('contratista', '')}")])
    destino = carpeta(obra) / f"{datetime.now():%Y-%m-%d_%H%M}_oficio_{_slug(asunto)}.docx"
    doc.save(destino)
    return destino


def acta_comite(obra: str, datos: dict) -> Path:
    """datos: {numero, fecha, lugar, asistentes:[{nombre,cargo,entidad}], temas:[..], desarrollo:[..],
               compromisos:[{compromiso, responsable, fecha}], proxima: "..."}"""
    enc = D.encabezado_obra(obra)
    doc = D.nuevo_documento(f"Acta de comité de obra N° {datos.get('numero', '[N°]')}", obra, borrador=True)
    D.ficha(doc, [("Contrato N°", enc.get("contrato", "")), ("Objeto", enc.get("objeto", "")),
                  ("Fecha", datos.get("fecha", D.fecha_co(date.today()))), ("Lugar", datos.get("lugar", "Obra"))])
    D.subtitulo(doc, "1. Asistentes")
    D.tabla(doc, ["Nombre", "Cargo", "Entidad", "Firma"],
            [[a.get("nombre"), a.get("cargo"), a.get("entidad"), ""] for a in datos.get("asistentes", [])], [5, 4, 4, 4])
    D.subtitulo(doc, "2. Orden del día")
    for t in datos.get("temas", []):
        doc.add_paragraph(t, style="List Number")
    D.subtitulo(doc, "3. Desarrollo")
    for t in datos.get("desarrollo", []) or ["[COMPLETAR desarrollo de cada tema]"]:
        doc.add_paragraph(t)
    D.subtitulo(doc, "4. Compromisos")
    D.tabla(doc, ["N°", "Compromiso", "Responsable", "Fecha límite"],
            [[i, c.get("compromiso"), c.get("responsable"), c.get("fecha")] for i, c in
             enumerate(datos.get("compromisos", []), start=1)], [1, 9, 4, 3])
    if datos.get("proxima"):
        doc.add_paragraph(f"Próximo comité: {datos['proxima']}")
    doc.add_paragraph("Se firma por los asistentes una vez revisada y aprobada.")
    destino = carpeta(obra) / f"{datetime.now():%Y-%m-%d_%H%M}_acta_comite_{datos.get('numero', 'xx')}.docx"
    doc.save(destino)
    return destino


def _slug(t: str) -> str:
    import re
    import unicodedata
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", t).strip("_")[:40]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Borradores de comunicaciones (nunca se envían)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for nombre in ("correo", "oficio"):
        s = sub.add_parser(nombre)
        s.add_argument("obra")
        s.add_argument("--para", required=True)
        s.add_argument("--cargo", default="")
        s.add_argument("--asunto", required=True)
        s.add_argument("--puntos", nargs="+", default=[])
        s.add_argument("--redactar", help="instrucción para que el modelo redacte el cuerpo")
    s = sub.add_parser("acta")
    s.add_argument("obra")
    s.add_argument("datos")
    a = ap.parse_args(argv)
    if a.cmd == "acta":
        f = acta_comite(a.obra, json.loads(Path(a.datos).read_text(encoding="utf-8")))
    else:
        cuerpo = redactar(a.redactar, "\n".join(a.puntos)) if a.redactar else None
        f = correo(a.obra, a.para, a.asunto, a.puntos, cuerpo) if a.cmd == "correo" else \
            oficio(a.obra, a.para, a.cargo, a.asunto, a.puntos, cuerpo)
    print(f"BORRADOR guardado (no enviado): {f}")


if __name__ == "__main__":
    main()
