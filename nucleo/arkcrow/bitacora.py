"""Bitácora diaria de obra e informe semanal (Word + PDF).

Cada día queda en proyectos/<obra>/bitacora/AAAA-MM-DD.json:
  {fecha, clima: {manana, tarde, lluvia_h}, personal: [{cargo, cantidad, empresa}], equipos: [{equipo, cantidad, horas}],
   actividades: [{item, descripcion, cantidad, unidad, avance}], novedades: [..], visitas: [..], fotos: [rutas], fuente}

Entrada por texto libre (formato simple por secciones) o por dictado de voz (Whisper local, ver voz.py).

Uso:
  python -m arkcrow.bitacora registrar <obra> --texto archivo.txt [--fecha AAAA-MM-DD]
  python -m arkcrow.bitacora informe <obra> --semana AAAA-MM-DD     (cualquier día de la semana)
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

from . import documentos as D

SECCIONES = {
    "clima": r"clima",
    "personal": r"personal|cuadrilla|mano de obra",
    "equipos": r"equipos?|maquinaria",
    "actividades": r"actividades|trabajos|ejecutado",
    "novedades": r"novedades|problemas|incidentes|observaciones",
    "visitas": r"visitas?|interventor[ií]a|supervisi[oó]n",
}


def carpeta(obra: str) -> Path:
    d = D.carpeta_obra(obra) / "bitacora"
    d.mkdir(exist_ok=True)
    return d


def _num(t: str) -> float | None:
    m = re.search(r"(\d+(?:[.,]\d+)?)", t)
    return float(m.group(1).replace(",", ".")) if m else None


def parsear_texto(texto: str) -> dict:
    """Convierte un texto dictado o escrito en una entrada estructurada.

    Formato esperado (flexible): líneas «Sección: ...» o encabezados de sección, y viñetas.
      Clima: mañana soleado, tarde lluvia 2 h
      Personal: 1 oficial, 3 ayudantes, 2 instaladores drywall (Contratista X)
      Equipos: andamio 4 cuerpos 8 h; taladro 1
      Actividades:
      - 2.03 mampostería eje B, 12 m2, 60 %
      Novedades: llegó cemento tarde
    """
    e = {"clima": {}, "personal": [], "equipos": [], "actividades": [], "novedades": [], "visitas": []}
    actual = None
    for bruta in texto.splitlines():
        linea = bruta.strip().lstrip("-•*").strip()
        if not linea:
            continue
        m = re.match(r"^([A-Za-zÁÉÍÓÚáéíóúñÑ ]+):\s*(.*)$", linea)
        if m:
            clave = next((k for k, p in SECCIONES.items() if re.fullmatch(p, m.group(1).strip().lower())), None)
            if clave:
                actual, linea = clave, m.group(2).strip()
                if not linea:
                    continue
        if actual is None:
            e["novedades"].append(linea)
            continue
        partes = [p.strip() for p in re.split(r"[;,](?![^()]*\))", linea) if p.strip()] \
            if actual in ("personal", "equipos", "clima") else [linea]
        for p in partes:
            if actual == "clima":
                bajo = p.lower()
                if "mañana" in bajo or "manana" in bajo:
                    e["clima"]["manana"] = p
                elif "tarde" in bajo:
                    e["clima"]["tarde"] = p
                else:
                    e["clima"].setdefault("general", p)
                if "lluvia" in bajo and _num(p):
                    e["clima"]["lluvia_h"] = _num(p)
            elif actual == "personal":
                emp = re.search(r"\(([^)]*)\)", p)
                n = _num(p) or 1
                cargo = re.sub(r"\(.*?\)|\d+(?:[.,]\d+)?", "", p).strip()
                e["personal"].append({"cargo": cargo, "cantidad": int(n), "empresa": emp.group(1) if emp else ""})
            elif actual == "equipos":
                horas = re.search(r"(\d+(?:[.,]\d+)?)\s*h\b", p)
                cant = re.match(r"\s*(\d+)\s", p)
                e["equipos"].append({"equipo": re.sub(r"^\s*\d+\s+|\d+(?:[.,]\d+)?\s*h\b", "", p).strip(" ,"),
                                     "cantidad": int(cant.group(1)) if cant else 1,
                                     "horas": float(horas.group(1).replace(",", ".")) if horas else None})
            elif actual == "actividades":
                item = re.match(r"^((?:NP-)?\d+(?:\.\d+)+)\s+(.*)", p)
                cant = re.search(r"(\d+(?:[.,]\d+)?)\s*(m2|m²|m3|m³|ml|und|kg|gl)\b", p, re.I)
                av = re.search(r"(\d+(?:[.,]\d+)?)\s*%", p)
                e["actividades"].append({
                    "item": item.group(1) if item else "",
                    "descripcion": re.sub(r",?\s*\d+(?:[.,]\d+)?\s*(m2|m²|m3|m³|ml|und|kg|gl|%)(?=\W|$)", "",
                                          item.group(2) if item else p, flags=re.I).strip(" ,"),
                    "cantidad": float(cant.group(1).replace(",", ".")) if cant else None,
                    "unidad": cant.group(2).replace("m2", "m²").replace("m3", "m³") if cant else "",
                    "avance": float(av.group(1).replace(",", ".")) / 100 if av else None})
            else:
                e[actual].append(p)
    return e


def registrar(obra: str, entrada: dict, fecha: date | None = None, fuente: str = "texto") -> Path:
    fecha = fecha or date.today()
    f = carpeta(obra) / f"{fecha:%Y-%m-%d}.json"
    if f.exists():   # se agrega, nunca se sobrescribe lo del día
        previo = json.loads(f.read_text(encoding="utf-8"))
        for k in ("personal", "equipos", "actividades", "novedades", "visitas", "fotos"):
            previo.setdefault(k, []).extend(entrada.get(k, []))
        previo.setdefault("clima", {}).update(entrada.get("clima", {}))
        entrada = previo
    entrada.update({"fecha": f"{fecha:%Y-%m-%d}", "fuente": fuente, "actualizado": datetime.now().isoformat(timespec="minutes")})
    entrada.setdefault("fotos", [])
    f.write_text(json.dumps(entrada, ensure_ascii=False, indent=2), encoding="utf-8")
    return f


def leer(obra: str, desde: date, hasta: date) -> list[dict]:
    out = []
    d = desde
    while d <= hasta:
        f = carpeta(obra) / f"{d:%Y-%m-%d}.json"
        if f.exists():
            out.append(json.loads(f.read_text(encoding="utf-8")))
        d += timedelta(days=1)
    return out


def informe_semanal(obra: str, dia: date) -> tuple[Path, Path | None]:
    lunes = dia - timedelta(days=dia.weekday())
    domingo = lunes + timedelta(days=6)
    dias = leer(obra, lunes, domingo)
    enc = D.encabezado_obra(obra)
    doc = D.nuevo_documento("Informe semanal de obra", obra)
    D.ficha(doc, [("Obra", obra), ("Objeto", enc.get("objeto", "")), ("Contrato N°", enc.get("contrato", "")),
                  ("Periodo", f"{D.fecha_co(lunes)} a {D.fecha_co(domingo)}"),
                  ("Días con registro", f"{len(dias)} de 7"), ("Elaboró", enc.get("elaboro", ""))])
    if not dias:
        doc.add_paragraph("No hay registros de bitácora en este periodo.")
    else:
        # resumen de personal (hombres-día)
        D.subtitulo(doc, "1. Personal (hombres-día en la semana)")
        hd: dict[str, int] = {}
        for d in dias:
            for p in d.get("personal", []):
                hd[p["cargo"]] = hd.get(p["cargo"], 0) + int(p.get("cantidad") or 0)
        D.tabla(doc, ["Cargo", "Hombres-día"], [[k, v] for k, v in sorted(hd.items())] +
                [["TOTAL", sum(hd.values())]], [10, 4])
        D.subtitulo(doc, "2. Clima")
        lluvia = sum(float(d.get("clima", {}).get("lluvia_h") or 0) for d in dias)
        D.tabla(doc, ["Fecha", "Mañana", "Tarde", "Lluvia (h)"],
                [[d["fecha"], d.get("clima", {}).get("manana") or d.get("clima", {}).get("general", ""),
                  d.get("clima", {}).get("tarde", ""), d.get("clima", {}).get("lluvia_h") or ""] for d in dias] +
                [["Total lluvia", "", "", lluvia]], [3, 6, 6, 2.5])
        D.subtitulo(doc, "3. Actividades ejecutadas")
        filas = []
        for d in dias:
            for a in d.get("actividades", []):
                filas.append([d["fecha"], a.get("item", ""), a.get("descripcion", ""),
                              f"{a['cantidad']:g} {a.get('unidad', '')}".replace(".", ",") if a.get("cantidad") else "",
                              f"{a['avance']:.0%}" if a.get("avance") is not None else ""])
        D.tabla(doc, ["Fecha", "Ítem", "Actividad", "Cantidad", "Avance"], filas, [2.5, 1.5, 8, 2.5, 2])
        D.subtitulo(doc, "4. Equipos")
        D.tabla(doc, ["Fecha", "Equipo", "Cant.", "Horas"],
                [[d["fecha"], e["equipo"], e.get("cantidad", ""), e.get("horas") or ""] for d in dias for e in d.get("equipos", [])],
                [3, 9, 2, 2])
        D.subtitulo(doc, "5. Novedades, visitas y pendientes")
        for d in dias:
            for k, rot in (("novedades", "Novedad"), ("visitas", "Visita")):
                for n in d.get(k, []):
                    doc.add_paragraph(f"{d['fecha']} · {rot}: {n}", style="List Bullet")
        fotos = [f for d in dias for f in d.get("fotos", []) if Path(f).exists()]
        if fotos:
            from docx.shared import Cm
            D.subtitulo(doc, "6. Registro fotográfico")
            for f in fotos[:12]:
                doc.add_picture(f, width=Cm(8))
                doc.add_paragraph(Path(f).name)
    D.firmas(doc, [(enc.get("elaboro", ""), "Arquitecto residente"), (enc.get("supervisor", ""), "Supervisión / Interventoría")])
    destino = D.salidas(obra) / f"Informe_semanal_{lunes:%Y-%m-%d}.docx"
    doc.save(destino)
    return destino, D.a_pdf(destino)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Bitácora de obra")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("registrar")
    r.add_argument("obra")
    r.add_argument("--texto", help="archivo de texto con la bitácora (o '-' para teclado)")
    r.add_argument("--audio", help="audio para dictado offline (Whisper local)")
    r.add_argument("--fecha")
    i = sub.add_parser("informe")
    i.add_argument("obra")
    i.add_argument("--semana", default=None)
    a = ap.parse_args(argv)
    if a.cmd == "registrar":
        if a.audio:
            from .voz import transcribir
            texto, fuente = transcribir(a.audio), "voz"
        else:
            import sys
            texto = sys.stdin.read() if a.texto in (None, "-") else Path(a.texto).read_text(encoding="utf-8")
            fuente = "texto"
        fecha = date.fromisoformat(a.fecha) if a.fecha else None
        f = registrar(a.obra, parsear_texto(texto), fecha, fuente)
        print(f"Bitácora guardada: {f}")
    else:
        dia = date.fromisoformat(a.semana) if a.semana else date.today()
        docx, pdf = informe_semanal(a.obra, dia)
        print(f"Informe: {docx}\nPDF: {pdf or '(sin LibreOffice: abrir el .docx y exportar)'}")


if __name__ == "__main__":
    main()
