"""Lectura de planos de AutoCAD (DXF; DWG si está instalado ODA File Converter, gratuito). 100 % offline.

Por capa calcula:
  - longitudes (ml): líneas, polilíneas abiertas, arcos, splines
  - áreas (m²): polilíneas cerradas, círculos, sombreados (hatch, restando huecos)
  - conteo de bloques por nombre (árboles, luminarias, bancas, puertas...)
  - textos y cotas
Las unidades salen del encabezado del plano ($INSUNITS); si el plano no las declara, se deducen del tamaño del
dibujo y se AVISA. Siempre se puede forzar con --unidades.

Uso:
  python -m arkcrow.cad plano.dxf [--unidades mm|cm|m] [--capas "VERDE|ADOQUIN"] [--excel] [--memoria]
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

UNIDADES = {1: ("pulg", 0.0254), 2: ("pies", 0.3048), 4: ("mm", 0.001), 5: ("cm", 0.01), 6: ("m", 1.0)}
FACTOR = {"mm": 0.001, "cm": 0.01, "m": 1.0}
RUTAS_ODA = [r"C:\Program Files\ODA", r"C:\Program Files (x86)\ODA"]


class CadNoLegible(RuntimeError):
    pass


def abrir(ruta: str | Path):
    import ezdxf
    from ezdxf import recover
    ruta = Path(ruta)
    if ruta.suffix.lower() == ".dwg":
        from ezdxf.addons import odafc
        for base in RUTAS_ODA:
            for exe in sorted(Path(base).glob("ODAFileConverter*/ODAFileConverter.exe")) if Path(base).exists() else []:
                ezdxf.options.set("odafc-addon", "win_exec_path", str(exe))
        if not odafc.is_installed():
            raise CadNoLegible("Para leer DWG instale 'ODA File Converter' (gratuito, opendesign.com) o guarde el plano "
                               "como DXF desde AutoCAD (GUARDARCOMO > AutoCAD DXF).")
        return odafc.readfile(str(ruta))
    try:
        return ezdxf.readfile(str(ruta))
    except Exception:  # noqa: BLE001  (archivo con errores menores: modo recuperación)
        doc, auditor = recover.readfile(str(ruta))
        if auditor.has_errors:
            raise CadNoLegible(f"El DXF tiene errores graves: {auditor.errors[:3]}")
        return doc


def _poligono(pts):
    """(perímetro, área) de una lista de puntos 2D."""
    per = sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))
    area = 0.5 * abs(sum(pts[i][0] * pts[i + 1][1] - pts[i + 1][0] * pts[i][1] for i in range(len(pts) - 1)))
    return per, area


def _area_hatch(e) -> float:
    from ezdxf import path as zpath
    total = 0.0
    for bp in e.paths:
        p = zpath.from_hatch_boundary_path(bp, ocs=e.ocs(), elevation=e.dxf.elevation.z)
        pts = [(v.x, v.y) for v in p.flattening(0.01)]
        if len(pts) < 3:
            continue
        if pts[0] != pts[-1]:
            pts.append(pts[0])
        _, a = _poligono(pts)
        externo = bool(bp.path_type_flags & 1) or bool(bp.path_type_flags & 16)
        total += a if externo else -a
    return abs(total)


def _nombre_real(doc, nombre: str, cache: dict) -> str:
    """Los bloques dinámicos aparecen como '*U123'; su nombre real está en el registro del bloque (AcDbBlockRepBTag)."""
    if not nombre.startswith("*U"):
        return nombre
    if nombre not in cache:
        real = nombre
        try:
            br = doc.block_records.get(nombre)
            for t in br.get_xdata("AcDbBlockRepBTag"):
                if t.code == 1005:
                    e = doc.entitydb.get(t.value)
                    if e is not None and getattr(e.dxf, "name", None):
                        real = e.dxf.name
        except Exception:  # noqa: BLE001  (bloque anónimo sin dato del original: se deja el nombre interno)
            pass
        cache[nombre] = real
    return cache[nombre]


def leer(ruta: str | Path, unidades: str | None = None, capas: str | None = None) -> dict:
    from ezdxf import bbox
    from ezdxf import path as zpath
    doc = abrir(ruta)
    msp = doc.modelspace()
    avisos = []
    codigo = doc.header.get("$INSUNITS", 0)
    if unidades:
        nombre_u, f = unidades, FACTOR[unidades]
    elif codigo in UNIDADES:
        nombre_u, f = UNIDADES[codigo]
    else:
        caja = bbox.extents(msp, fast=True)
        tam = max(caja.size.x, caja.size.y) if caja.has_data else 0
        nombre_u, f = ("mm", 0.001) if tam > 2000 else ("m", 1.0)
        avisos.append(f"El plano no declara unidades; por el tamaño del dibujo ({tam:,.0f}) se asume {nombre_u}. "
                      "Verifique o use --unidades.")
    filtro = re.compile(capas, re.I) if capas else None
    por_capa: dict[str, dict] = defaultdict(lambda: {"ml": 0.0, "m2": 0.0, "bloques": defaultdict(int), "textos": [],
                                                     "cotas": [], "abiertas_largas": 0, "n": 0})
    no_soportadas = defaultdict(int)
    nombres: dict = {}
    for e in msp:
        capa = e.dxf.get("layer", "0")
        if filtro and not filtro.search(capa):
            continue
        c = por_capa[capa]
        c["n"] += 1
        t = e.dxftype()
        try:
            if t == "LINE":
                c["ml"] += e.dxf.start.distance(e.dxf.end) * f
            elif t in ("LWPOLYLINE", "POLYLINE", "SPLINE", "ARC", "ELLIPSE"):
                p = zpath.make_path(e)
                pts = [(v.x, v.y) for v in p.flattening(0.01 / f)]
                cerrada = (t in ("LWPOLYLINE", "POLYLINE") and e.is_closed) or \
                          (len(pts) > 2 and math.dist(pts[0], pts[-1]) < 1e-6)
                if cerrada and len(pts) > 2:
                    if pts[0] != pts[-1]:
                        pts.append(pts[0])
                    per, a = _poligono(pts)
                    c["m2"] += a * f * f
                    c.setdefault("perimetro_ml", 0.0)
                    c["perimetro_ml"] += per * f
                else:
                    per, _ = _poligono(pts) if len(pts) > 1 else (0, 0)
                    c["ml"] += per * f
            elif t == "CIRCLE":
                r = e.dxf.radius * f
                c["m2"] += math.pi * r * r
                c.setdefault("perimetro_ml", 0.0)
                c["perimetro_ml"] += 2 * math.pi * r
            elif t == "HATCH":
                c["m2_sombreado"] = c.get("m2_sombreado", 0.0) + _area_hatch(e) * f * f
            elif t == "INSERT":
                c["bloques"][_nombre_real(doc, e.dxf.name, nombres)] += 1
            elif t in ("TEXT", "MTEXT"):
                txt = (e.plain_text() if t == "MTEXT" else e.dxf.text).strip()
                if txt:
                    c["textos"].append(txt)
            elif t == "DIMENSION":
                m = e.get_measurement()
                if isinstance(m, (int, float)):
                    c["cotas"].append(round(m * f, 3))
            else:
                no_soportadas[t] += 1
        except Exception as ex:  # noqa: BLE001
            avisos.append(f"Entidad {t} en capa {capa} no se pudo medir ({ex}).")
    if no_soportadas:
        avisos.append("Entidades no medidas: " + ", ".join(f"{k} ({v})" for k, v in sorted(no_soportadas.items())))
    capas_out = []
    for nombre, c in sorted(por_capa.items()):
        capas_out.append({"capa": nombre, "ml": round(c["ml"], 3), "m2": round(c["m2"], 3),
                          "m2_sombreado": round(c.get("m2_sombreado", 0.0), 3),
                          "perimetro_ml": round(c.get("perimetro_ml", 0.0), 3),
                          "bloques": dict(sorted(c["bloques"].items())), "textos": c["textos"][:200],
                          "cotas": c["cotas"][:200], "entidades": c["n"]})
    bloques_tot = defaultdict(int)
    for c in capas_out:
        for b, n in c["bloques"].items():
            bloques_tot[b] += n
    return {"archivo": Path(ruta).name, "unidades": nombre_u, "version": doc.dxfversion, "capas": capas_out,
            "bloques_total": dict(sorted(bloques_tot.items())), "avisos": avisos}


def a_filas_memoria(r: dict) -> dict:
    """Filas para 'memoria' de proyecto.json, agrupadas por tipo de cantidad."""
    m2, ml, und = [], [], []
    for c in r["capas"]:
        area = c["m2_sombreado"] or c["m2"]
        if area:
            m2.append([f"Capa {c['capa']} ({'sombreado' if c['m2_sombreado'] else 'polilíneas cerradas'}, DXF)",
                       round(area, 3), None, None, 1])
        if c["ml"]:
            ml.append([f"Capa {c['capa']} (DXF)", round(c["ml"], 3), None, None, 1])
        for b, n in c["bloques"].items():
            und.append([f"Bloque {b} en capa {c['capa']} (DXF)", None, None, None, n])
    return {"m2": m2, "ml": ml, "und": und}


def texto_para_indice(r: dict) -> list[tuple[str, str]]:
    """Fragmentos legibles para la base de conocimiento (una ubicación por capa)."""
    out = [("resumen", f"Plano {r['archivo']} (unidades {r['unidades']}). Capas: {', '.join(c['capa'] for c in r['capas'])}. "
                       f"Bloques: {', '.join(f'{b}: {n}' for b, n in r['bloques_total'].items()) or 'ninguno'}.")]
    for c in r["capas"]:
        partes = [f"Capa {c['capa']}:"]
        if c["m2"] or c["m2_sombreado"]:
            partes.append(f"área {max(c['m2'], c['m2_sombreado']):,.2f} m²")
        if c["ml"]:
            partes.append(f"longitud {c['ml']:,.2f} ml")
        if c["bloques"]:
            partes.append("bloques " + ", ".join(f"{b} ({n} und)" for b, n in c["bloques"].items()))
        if c["textos"]:
            partes.append("textos: " + " | ".join(c["textos"][:40]))
        out.append((f"capa «{c['capa']}»", " ".join(partes)))
    return out


def a_excel(r: dict, destino: Path) -> Path:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    wb = Workbook()
    ws = wb.active
    ws.title = "CANTIDADES DXF"
    neg, azul = Font(name="Arial", bold=True), Font(name="Arial", color="0000FF")
    ws["A1"] = f"Cantidades por capa - {r['archivo']} (unidades del plano: {r['unidades']})"
    ws["A1"].font = Font(name="Arial", bold=True, size=12)
    ws["A2"] = "Valores medidos del plano (azul). Verifique capas y polilíneas cerradas antes de usarlos en la memoria."
    cab = ["Capa", "Área polilíneas (m²)", "Área sombreados (m²)", "Perímetro áreas (ml)", "Longitud (ml)", "Bloques",
           "Entidades"]
    for i, t in enumerate(cab, start=1):
        cel = ws.cell(4, i, t)
        cel.font = neg
        cel.fill = PatternFill("solid", fgColor="D9E1F2")
    fila = 5
    for c in r["capas"]:
        vals = [c["capa"], c["m2"], c["m2_sombreado"], c["perimetro_ml"], c["ml"],
                ", ".join(f"{b}: {n}" for b, n in c["bloques"].items()), c["entidades"]]
        for i, v in enumerate(vals, start=1):
            cel = ws.cell(fila, i, v)
            cel.font = azul if i in (2, 3, 4, 5) else Font(name="Arial")
            if i in (2, 3, 4, 5):
                cel.number_format = "#,##0.00"
        fila += 1
    ws.cell(fila, 1, "TOTAL").font = neg
    for col in "BCDE":
        ws[f"{col}{fila}"] = f"=SUM({col}5:{col}{fila - 1})"
        ws[f"{col}{fila}"].font = neg
        ws[f"{col}{fila}"].number_format = "#,##0.00"
    f2 = fila + 2
    ws.cell(f2, 1, "Bloques (total en el plano)").font = neg
    for b, n in r["bloques_total"].items():
        f2 += 1
        ws.cell(f2, 1, b)
        ws.cell(f2, 2, n).font = azul
    for i, w in enumerate([34, 18, 18, 18, 14, 40, 10], start=1):
        ws.column_dimensions[chr(64 + i)].width = w
    if r["avisos"]:
        f2 += 2
        ws.cell(f2, 1, "Avisos").font = neg
        for a in r["avisos"]:
            f2 += 1
            ws.cell(f2, 1, a)
    wb.save(destino)
    return destino


def main(argv=None):
    ap = argparse.ArgumentParser(description="Cantidades por capa de planos DXF/DWG")
    ap.add_argument("archivo")
    ap.add_argument("--unidades", choices=list(FACTOR))
    ap.add_argument("--capas", help="filtro de capas (expresión regular), p. ej. 'VERDE|ADOQUIN'")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--memoria", action="store_true", help="filas para proyecto.json")
    ap.add_argument("--excel", action="store_true", help="genera Excel de cantidades junto al plano")
    a = ap.parse_args(argv)
    try:
        r = leer(a.archivo, a.unidades, a.capas)
    except CadNoLegible as e:
        sys.exit(f"⚠ {e}")
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    elif a.memoria:
        print(json.dumps(a_filas_memoria(r), ensure_ascii=False, indent=2))
    else:
        print(f"{r['archivo']} · DXF {r['version']} · unidades: {r['unidades']}")
        print(f"{'Capa':30s} {'m² (pol.)':>11s} {'m² (somb.)':>11s} {'ml':>10s}  bloques")
        for c in r["capas"]:
            if c["m2"] or c["m2_sombreado"] or c["ml"] or c["bloques"]:
                print(f"{c['capa'][:30]:30s} {c['m2']:11.2f} {c['m2_sombreado']:11.2f} {c['ml']:10.2f}  "
                      + ", ".join(f"{b}:{n}" for b, n in c["bloques"].items()))
        for av in r["avisos"]:
            print("⚠", av)
    if a.excel:
        destino = Path(a.archivo).with_name(f"{Path(a.archivo).stem}_cantidades_{date.today():%Y-%m-%d}.xlsx")
        print(f"Excel: {a_excel(r, destino)}")


if __name__ == "__main__":
    main()
