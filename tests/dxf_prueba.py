"""Plano DXF sintético de paisajismo (en milímetros) con cantidades conocidas, para probar la lectura de CAD.

Cantidades esperadas (en metros):
  ZONA VERDE  : polilínea cerrada 10 x 5 = 50 m² ; círculo r = 1 m -> 3,1416 m²   (total 53,1416 m²)
  ADOQUIN     : sombreado 4 x 3 con hueco 1 x 1 = 11 m²
  BORDILLO    : polilínea abierta 12 m + arco 90° r = 2 m (3,1416 m) = 15,1416 ml
  ARBOLES     : 7 bloques ARBOL ; LUMINARIAS: 3 bloques LUMINARIA
  TEXTOS      : "ZONA VERDE 1", "ADOQUIN PEATONAL"
"""
from pathlib import Path


def crear(destino: Path, unidades_mm: bool = True) -> Path:
    import ezdxf
    k = 1000.0 if unidades_mm else 1.0
    doc = ezdxf.new("R2018", setup=True)
    doc.header["$INSUNITS"] = 4 if unidades_mm else 6
    msp = doc.modelspace()
    for capa in ("ZONA VERDE", "ADOQUIN", "BORDILLO", "ARBOLES", "LUMINARIAS", "TEXTOS"):
        doc.layers.add(capa)
    msp.add_lwpolyline([(0, 0), (10 * k, 0), (10 * k, 5 * k), (0, 5 * k)], close=True, dxfattribs={"layer": "ZONA VERDE"})
    msp.add_circle((20 * k, 20 * k), 1 * k, dxfattribs={"layer": "ZONA VERDE"})
    h = msp.add_hatch(dxfattribs={"layer": "ADOQUIN"})
    h.paths.add_polyline_path([(30 * k, 0), (34 * k, 0), (34 * k, 3 * k), (30 * k, 3 * k)], is_closed=True, flags=1)
    h.paths.add_polyline_path([(31 * k, 1 * k), (32 * k, 1 * k), (32 * k, 2 * k), (31 * k, 2 * k)], is_closed=True, flags=0)
    msp.add_lwpolyline([(0, 10 * k), (12 * k, 10 * k)], dxfattribs={"layer": "BORDILLO"})
    msp.add_arc((50 * k, 50 * k), 2 * k, 0, 90, dxfattribs={"layer": "BORDILLO"})
    arbol = doc.blocks.new("ARBOL")
    arbol.add_circle((0, 0), 0.5 * k)
    lum = doc.blocks.new("LUMINARIA")
    lum.add_line((0, 0), (0, 0.3 * k))
    for i in range(7):
        msp.add_blockref("ARBOL", (i * 2 * k, 20 * k), dxfattribs={"layer": "ARBOLES"})
    for i in range(3):
        msp.add_blockref("LUMINARIA", (i * 5 * k, 30 * k), dxfattribs={"layer": "LUMINARIAS"})
    msp.add_text("ZONA VERDE 1", dxfattribs={"layer": "TEXTOS"}).set_placement((1 * k, 1 * k))
    msp.add_mtext("ADOQUIN PEATONAL", dxfattribs={"layer": "TEXTOS"}).set_location((31 * k, 4 * k))
    destino.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(destino)
    return destino
