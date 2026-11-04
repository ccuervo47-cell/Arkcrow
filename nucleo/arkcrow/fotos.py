"""Registro fotográfico: organiza fotos por obra / fecha / ítem leyendo EXIF (fecha y GPS) y genera el anexo.

- Las fotos se COPIAN (nunca se mueven ni se borran los originales) a:
    proyectos/<obra>/fotos/AAAA-MM-DD/<ítem>/AAAAMMDD_HHMMSS_<ítem>_<nombre>.jpg
- El ítem se toma del nombre del archivo (p. ej. "2.03_muro eje A.jpg", "NP-01 cielo.jpg") o de --item.
- Índice en proyectos/<obra>/fotos/indice.json (fecha, GPS, ítem, original).

Uso:
  python -m arkcrow.fotos organizar <obra> <carpeta_origen> [--item 2.03]
  python -m arkcrow.fotos anexo <obra> [--item 2.03] [--desde AAAA-MM-DD] [--hasta AAAA-MM-DD]
  python -m arkcrow.fotos contar <obra>      (actualiza "fotos" de cada ítem en proyecto.json -> semáforo)
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

from PIL import ExifTags, Image, ImageOps

from . import documentos as D

EXT = {".jpg", ".jpeg", ".png", ".heic", ".tif", ".tiff"}
RX_ITEM = re.compile(r"^((?:NP-\d+)|(?:\d+\.\d+(?:\.\d+)?))[\s_-]", re.I)


def _gps_a_decimal(valor, ref) -> float | None:
    try:
        g, m, s = (float(x) for x in valor)
        dec = g + m / 60 + s / 3600
        return round(-dec if ref in ("S", "W") else dec, 6)
    except Exception:  # noqa: BLE001
        return None


def leer_exif(ruta: Path) -> dict:
    out = {"fecha": None, "lat": None, "lon": None}
    try:
        with Image.open(ruta) as im:
            exif = im.getexif()
            ifd = exif.get_ifd(ExifTags.IFD.Exif)
            txt = ifd.get(ExifTags.Base.DateTimeOriginal) or exif.get(ExifTags.Base.DateTime)
            if txt:
                out["fecha"] = datetime.strptime(str(txt).strip("\x00"), "%Y:%m:%d %H:%M:%S")
            gps = exif.get_ifd(ExifTags.IFD.GPSInfo)
            if gps:
                out["lat"] = _gps_a_decimal(gps.get(2), gps.get(1))
                out["lon"] = _gps_a_decimal(gps.get(4), gps.get(3))
    except Exception:  # noqa: BLE001
        pass
    if out["fecha"] is None:   # sin EXIF: fecha de modificación del archivo (se marca)
        out["fecha"] = datetime.fromtimestamp(ruta.stat().st_mtime)
        out["fecha_origen"] = "archivo (sin EXIF)"
    else:
        out["fecha_origen"] = "EXIF"
    return out


def _indice(obra: str) -> Path:
    return D.carpeta_obra(obra) / "fotos" / "indice.json"


def cargar_indice(obra: str) -> list[dict]:
    f = _indice(obra)
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else []


def organizar(obra: str, origen: str | Path, item: str | None = None) -> list[dict]:
    origen = Path(origen)
    indice = cargar_indice(obra)
    ya = {r["original"] for r in indice}
    nuevos = []
    archivos = [origen] if origen.is_file() else sorted(p for p in origen.rglob("*") if p.suffix.lower() in EXT)
    for f in archivos:
        if str(f.resolve()) in ya:
            continue
        meta = leer_exif(f)
        m = RX_ITEM.match(f.name)
        it = (item or (m.group(1).upper() if m else "sin-item"))
        fecha = meta["fecha"]
        nombre = f"{fecha:%Y%m%d_%H%M%S}_{it}_{re.sub(r'[^A-Za-z0-9._-]+', '_', RX_ITEM.sub('', f.name).rsplit('.', 1)[0] or f.stem)}{f.suffix.lower()}"
        destino = D.copiar_seguro(f, D.carpeta_obra(obra) / "fotos" / f"{fecha:%Y-%m-%d}" / it / nombre)
        reg = {"archivo": str(destino.relative_to(D.RAIZ)), "original": str(f.resolve()), "item": it,
               "fecha": fecha.isoformat(timespec="seconds"), "fecha_origen": meta["fecha_origen"],
               "lat": meta["lat"], "lon": meta["lon"]}
        indice.append(reg)
        nuevos.append(reg)
    _indice(obra).parent.mkdir(parents=True, exist_ok=True)
    _indice(obra).write_text(json.dumps(indice, ensure_ascii=False, indent=2), encoding="utf-8")
    return nuevos


def _miniatura(ruta: Path, tmpdir: Path) -> Path:
    with Image.open(ruta) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        im.thumbnail((1200, 1200))
        out = tmpdir / (ruta.stem + "_mini.jpg")
        im.save(out, "JPEG", quality=82)
    return out


def anexo(obra: str, item: str | None = None, desde: str | None = None, hasta: str | None = None) -> tuple[Path, Path | None]:
    import tempfile
    from docx.shared import Cm, Pt
    fotos = [r for r in cargar_indice(obra)
             if (not item or r["item"] == item) and (not desde or r["fecha"][:10] >= desde)
             and (not hasta or r["fecha"][:10] <= hasta)]
    fotos.sort(key=lambda r: (r["item"], r["fecha"]))
    titulo = "Anexo fotográfico" + (f" - ítem {item}" if item else "")
    doc = D.nuevo_documento(titulo, obra)
    enc = D.encabezado_obra(obra)
    D.ficha(doc, [("Obra", obra), ("Objeto", enc.get("objeto", "")), ("Contrato N°", enc.get("contrato", "")),
                  ("Fotografías", str(len(fotos))), ("Periodo", f"{desde or 'inicio'} a {hasta or 'hoy'}")])
    doc.add_paragraph()
    with tempfile.TemporaryDirectory() as tmp:
        t = doc.add_table(rows=0, cols=2)
        t.style = "Table Grid"
        for i in range(0, len(fotos), 2):
            celdas = t.add_row().cells
            for c, r in zip(celdas, fotos[i:i + 2]):
                p = c.paragraphs[0]
                p.add_run().add_picture(str(_miniatura(D.RAIZ / r["archivo"], Path(tmp))), width=Cm(8))
                gps = f"GPS {r['lat']:.5f}, {r['lon']:.5f}" if r.get("lat") is not None else "sin GPS"
                fecha = datetime.fromisoformat(r["fecha"])
                cap = c.add_paragraph(f"Ítem {r['item']} · {fecha:%d/%m/%Y %H:%M}"
                                      f"{' (fecha del archivo)' if r['fecha_origen'] != 'EXIF' else ''} · {gps}\n"
                                      f"{Path(r['archivo']).name}")
                for run in cap.runs:
                    run.font.size = Pt(7)
        sufijo = f"_{item}" if item else ""
        destino = D.salidas(obra) / f"Anexo_fotografico{sufijo}_{datetime.now():%Y-%m-%d}.docx"
        doc.save(destino)
    return destino, D.a_pdf(destino)


def contar(obra: str) -> dict:
    """Pone en proyecto.json el número de fotos por ítem (máx. 3) para el semáforo de memorias."""
    conteo: dict[str, int] = {}
    for r in cargar_indice(obra):
        conteo[r["item"]] = conteo.get(r["item"], 0) + 1
    ruta = D.carpeta_obra(obra) / "proyecto.json"
    p = json.loads(ruta.read_text(encoding="utf-8"))
    for cap in p["capitulos"]:
        for it in cap["items"]:
            it["fotos"] = min(3, conteo.get(it["codigo"], 0))
    ruta.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")
    return conteo


def main(argv=None):
    ap = argparse.ArgumentParser(description="Registro fotográfico")
    sub = ap.add_subparsers(dest="cmd", required=True)
    o = sub.add_parser("organizar")
    o.add_argument("obra")
    o.add_argument("origen")
    o.add_argument("--item")
    a_ = sub.add_parser("anexo")
    a_.add_argument("obra")
    a_.add_argument("--item")
    a_.add_argument("--desde")
    a_.add_argument("--hasta")
    c = sub.add_parser("contar")
    c.add_argument("obra")
    a = ap.parse_args(argv)
    if a.cmd == "organizar":
        n = organizar(a.obra, a.origen, a.item)
        print(f"{len(n)} foto(s) organizadas.")
        for r in n:
            print(f"  {r['archivo']}  [{r['fecha_origen']}{', GPS' if r['lat'] is not None else ''}]")
    elif a.cmd == "anexo":
        d, p = anexo(a.obra, a.item, a.desde, a.hasta)
        print(f"Anexo: {d}\nPDF: {p}")
    else:
        print(contar(a.obra))


if __name__ == "__main__":
    main()
