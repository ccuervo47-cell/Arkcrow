"""Lectura de modelos IFC (offline, ifcopenshell) y de planos PDF.

IFC -> cantidades por categoría:
  - Muros: longitud, altura, espesor, área bruta, vanos y área neta (por cara). Usa Qto_WallBaseQuantities si el
    modelo las trae (Revit: "Export base quantities"); si no, las calcula de la geometría (muros rectos).
  - Puertas y ventanas: marca, ancho y alto.
  - Espacios: área neta de piso y perímetro (Qto_SpaceBaseQuantities o geometría).
  - Losas, cielos y otros: área/volumen si hay Qto.
PDF de planos -> texto con marcas de puertas/ventanas (P-101, V-39), cotas, áreas (m²) y escalas por página.

Uso:
  python -m arkcrow.bim ifc modelo.ifc [--json] [--memoria]
  python -m arkcrow.bim pdf plano.pdf
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def _qto(elem, nombre_qto: str) -> dict:
    import ifcopenshell.util.element as ue
    return ue.get_psets(elem, qtos_only=True).get(nombre_qto, {})


def _bbox_local(elem):
    """Extensiones (dx, dy, dz) de la geometría en coordenadas locales del elemento."""
    import ifcopenshell.geom
    import numpy as np
    s = ifcopenshell.geom.settings()
    s.set("use-world-coords", False)
    s.set("disable-opening-subtractions", True)
    sh = ifcopenshell.geom.create_shape(s, elem)
    v = np.array(sh.geometry.verts).reshape(-1, 3)
    return tuple(float(x) for x in (v.max(axis=0) - v.min(axis=0)))


def _nombre(e):
    return e.Name or e.Tag or e.GlobalId


def leer_ifc(ruta: str | Path) -> dict:
    import ifcopenshell
    m = ifcopenshell.open(str(ruta))
    res = {"archivo": Path(ruta).name, "esquema": m.schema, "muros": [], "puertas": [], "ventanas": [],
           "espacios": [], "otros": [], "avisos": []}
    for w in m.by_type("IfcWall"):
        q = _qto(w, "Qto_WallBaseQuantities")
        try:
            dx, dy, dz = _bbox_local(w)
        except Exception as e:  # noqa: BLE001
            dx = dy = dz = None
            res["avisos"].append(f"Muro {_nombre(w)}: sin geometría legible ({e})")
        largo = q.get("Length") or dx
        alto = q.get("Height") or dz
        espesor = q.get("Width") or dy
        vanos = []
        for rel in getattr(w, "HasOpenings", []) or []:
            op = rel.RelatedOpeningElement
            relleno = next((f.RelatedBuildingElement for f in (op.HasFillings or [])), None)
            ancho = getattr(relleno, "OverallWidth", None) if relleno else None
            altura = getattr(relleno, "OverallHeight", None) if relleno else None
            if not (ancho and altura):
                try:
                    ox, _, oz = _bbox_local(op)
                    ancho, altura = ancho or ox, altura or oz
                except Exception:  # noqa: BLE001
                    pass
            vanos.append({"marca": _nombre(relleno) if relleno else _nombre(op),
                          "tipo": relleno.is_a() if relleno else "IfcOpeningElement",
                          "ancho": round(ancho or 0, 4), "alto": round(altura or 0, 4)})
        bruta = q.get("GrossSideArea") or (largo * alto if largo and alto else None)
        area_vanos = sum(v["ancho"] * v["alto"] for v in vanos)
        neta = q.get("NetSideArea") or (bruta - area_vanos if bruta is not None else None)
        res["muros"].append({"nombre": _nombre(w), "largo": _r(largo), "alto": _r(alto), "espesor": _r(espesor),
                             "area_bruta": _r(bruta), "area_vanos": _r(area_vanos), "area_neta": _r(neta),
                             "vanos": vanos, "fuente": "Qto" if q else "geometría"})
    for clase, clave in (("IfcDoor", "puertas"), ("IfcWindow", "ventanas")):
        for d in m.by_type(clase):
            res[clave].append({"marca": _nombre(d), "ancho": _r(d.OverallWidth), "alto": _r(d.OverallHeight)})
    for sp in m.by_type("IfcSpace"):
        q = _qto(sp, "Qto_SpaceBaseQuantities")
        area, per = q.get("NetFloorArea") or q.get("GrossFloorArea"), q.get("NetPerimeter") or q.get("GrossPerimeter")
        if area is None:
            try:
                dx, dy, _ = _bbox_local(sp)
                area, per = dx * dy, 2 * (dx + dy)
                res["avisos"].append(f"Espacio {_nombre(sp)}: área por caja envolvente (válida solo si es rectangular)")
            except Exception:  # noqa: BLE001
                pass
        res["espacios"].append({"nombre": sp.LongName or _nombre(sp), "area": _r(area), "perimetro": _r(per)})
    for clase, qn in (("IfcSlab", "Qto_SlabBaseQuantities"), ("IfcCovering", "Qto_CoveringBaseQuantities")):
        for e in m.by_type(clase):
            q = _qto(e, qn)
            res["otros"].append({"clase": clase, "nombre": _nombre(e), "area": _r(q.get("NetArea") or q.get("GrossArea")),
                                 "volumen": _r(q.get("NetVolume") or q.get("GrossVolume"))})
    res["resumen"] = {
        "muros_area_bruta_m2": _r(sum(x["area_bruta"] or 0 for x in res["muros"])),
        "muros_area_vanos_m2": _r(sum(x["area_vanos"] or 0 for x in res["muros"])),
        "muros_area_neta_m2_una_cara": _r(sum(x["area_neta"] or 0 for x in res["muros"])),
        "muros_longitud_ml": _r(sum(x["largo"] or 0 for x in res["muros"])),
        "espacios_area_m2": _r(sum(x["area"] or 0 for x in res["espacios"])),
        "puertas": len(res["puertas"]), "ventanas": len(res["ventanas"]),
    }
    return res


def a_filas_memoria(res: dict) -> dict:
    """Filas listas para 'memoria' de proyecto.json (mampostería por muro y vanos en negativo)."""
    mamp = []
    for w in res["muros"]:
        mamp.append([f"Muro {w['nombre']} (IFC)", w["largo"], None, w["alto"], 1])
        for v in w["vanos"]:
            mamp.append([f"Vano {v['marca']} en {w['nombre']} (IFC)", v["ancho"], None, v["alto"], -1])
    piso = [[f"Espacio {s['nombre']} (IFC)", s["area"], None, None, 1] for s in res["espacios"]]
    return {"mamposteria": mamp, "piso": piso}


def leer_pdf_plano(ruta: str | Path) -> list[dict]:
    import pdfplumber
    out = []
    with pdfplumber.open(str(ruta)) as pdf:
        for i, pag in enumerate(pdf.pages, start=1):
            t = pag.extract_text() or ""
            out.append({
                "pagina": i,
                "marcas_puertas": sorted(set(re.findall(r"\bP-\d{1,4}\b", t))),
                "marcas_ventanas": sorted(set(re.findall(r"\bV-\d{1,4}\b", t))),
                "areas_m2": [float(a.replace(",", ".")) for a in re.findall(r"(\d+(?:[.,]\d+)?)\s*m(?:2|²)", t)],
                "escalas": sorted(set(re.findall(r"\b1\s*:\s*\d{2,4}\b", t))),
                "cotas": [float(c.replace(",", ".")) for c in re.findall(r"(?<![\w.,])(\d{1,2}[.,]\d{2})(?![\w.,])", t)][:200],
                "texto": t[:3000],
            })
    return out


def _r(x, n=4):
    return round(float(x), n) if isinstance(x, (int, float)) else None


def main(argv=None):
    ap = argparse.ArgumentParser(description="Lectura de IFC y planos PDF")
    ap.add_argument("tipo", choices=["ifc", "pdf"])
    ap.add_argument("archivo")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--memoria", action="store_true", help="imprime filas para proyecto.json")
    a = ap.parse_args(argv)
    if a.tipo == "pdf":
        for p in leer_pdf_plano(a.archivo):
            p.pop("texto")
            print(json.dumps(p, ensure_ascii=False))
        return
    r = leer_ifc(a.archivo)
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    elif a.memoria:
        print(json.dumps(a_filas_memoria(r), ensure_ascii=False, indent=2))
    else:
        print(f"{r['archivo']} ({r['esquema']})")
        for w in r["muros"]:
            print(f"  Muro {w['nombre']}: L={w['largo']} H={w['alto']} e={w['espesor']} bruta={w['area_bruta']} "
                  f"vanos={w['area_vanos']} neta={w['area_neta']} [{w['fuente']}]")
        for k in ("puertas", "ventanas", "espacios"):
            for x in r[k]:
                print(f"  {k[:-1].capitalize()}: {x}")
        print("Resumen:", r["resumen"])
        for av in r["avisos"]:
            print("  aviso:", av)


if __name__ == "__main__":
    sys.exit(main())
