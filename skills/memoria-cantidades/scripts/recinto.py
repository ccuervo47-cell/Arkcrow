"""Calcula las filas de memoria de cantidades de un recinto rectangular (muros, pañetes, pisos, guardaescoba).

Ejemplo (sala de juntas de la prueba):
    python skills/memoria-cantidades/scripts/recinto.py --ext 3.82x3.38 --int 3.54x3.10 --alto 3 \
        --vano "P-101:0.85x2.10:puerta" --vano "V-39:1.50x1.20:ventana"

Imprime una tabla legible y, con --json, las filas listas para pegar en "memoria" de proyecto.json.
Los vanos se restan con cantidad negativa (una cara en mampostería, dos caras en pañete/estuco/pintura).
"""
from __future__ import annotations

import argparse
import json


def dims(t: str) -> tuple[float, float]:
    a, b = t.lower().replace(",", ".").split("x")
    return float(a), float(b)


def calcular(ext, inn, alto, vanos):
    (ex, ey), (ix, iy) = ext, inn
    e = round((ex - ix) / 2, 4)                       # espesor de muro
    cx, cy = ex - e, ey - e                           # longitudes a ejes
    puertas = [v for v in vanos if v["tipo"] == "puerta"]
    rest = lambda caras: [[f"Vano {v['cod']}" + (" (2 caras)" if caras == 2 else ""), v["ancho"], None, v["alto"], -caras]
                          for v in vanos]
    caras = [["Cara interior - muros longitudinales", ix, None, alto, 2],
             ["Cara interior - muros transversales", iy, None, alto, 2],
             ["Cara exterior - muros longitudinales", ex, None, alto, 2],
             ["Cara exterior - muros transversales", ey, None, alto, 2]]
    return {
        "espesor_muro_m": e,
        "placa_huella_exterior": [["Placa sobre huella exterior del recinto", ex, ey, None, 1]],
        "piso_interior": [["Área interior del recinto", ix, iy, None, 1]],
        "mamposteria": [["Muros por ejes longitudinales", round(cx, 4), None, alto, 2],
                        ["Muros por ejes transversales", round(cy, 4), None, alto, 2]] + rest(1),
        "acabados_muro_dos_caras": caras + rest(2),
        "guardaescoba": [["Perímetro interior - muros longitudinales", ix, None, None, 2],
                         ["Perímetro interior - muros transversales", iy, None, None, 2]] +
                        [[f"Vano {v['cod']}", v["ancho"], None, None, -1] for v in puertas],
        "viga_amarre_ml": round(2 * (cx + cy), 4),
    }


def total(filas):
    t = 0.0
    for _, *d in filas:
        p = 1.0
        for x in d:
            if x is not None:
                p *= x
        t += p
    return t


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ext", required=True, help="dimensiones exteriores LARGOxANCHO en m")
    ap.add_argument("--int", dest="inn", required=True, help="dimensiones interiores LARGOxANCHO en m")
    ap.add_argument("--alto", type=float, required=True, help="altura de muros en m")
    ap.add_argument("--vano", action="append", default=[], help='"COD:ANCHOxALTO:puerta|ventana"')
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    vanos = []
    for v in a.vano:
        cod, d, tipo = v.split(":")
        an, al = dims(d)
        vanos.append({"cod": cod, "ancho": an, "alto": al, "tipo": tipo.lower()})
    r = calcular(dims(a.ext), dims(a.inn), a.alto, vanos)
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return
    print(f"Espesor de muro deducido: {r['espesor_muro_m']:.3f} m")
    for clave, und in (("placa_huella_exterior", "m² (x espesor = m³)"), ("piso_interior", "m²"),
                       ("mamposteria", "m²"), ("acabados_muro_dos_caras", "m²"), ("guardaescoba", "ml")):
        print(f"\n{clave}  ->  TOTAL {total(r[clave]):.3f} {und}")
        for f in r[clave]:
            print("   ", f)
    print(f"\nViga de amarre (perímetro a ejes): {r['viga_amarre_ml']:.2f} ml")


if __name__ == "__main__":
    main()
