"""Arma el libro de costos de una obra (memorias + APU + balance enlazados) y lo pasa por el revisor.

Uso (desde la carpeta ArkcrowObra):
    python skills/presupuesto-balance/scripts/armar_balance.py proyectos/<obra>/proyecto.json
Genera en proyectos/<obra>/salidas/:  <nombre>_<fecha>.xlsx  y  <nombre>_<fecha>_REVISION.md
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "nucleo"))
from arkcrow import db, libro_costos, revisor_calidad  # noqa: E402

if len(sys.argv) < 2:
    sys.exit(__doc__)
db.inicializar()
xlsx = libro_costos.generar(sys.argv[1])
ok, md, reporte = revisor_calidad.revisar(xlsx, entregar=True)
print(md)
print(f"\nLibro:   {xlsx}\nReporte: {reporte}\nEstado:  {'APROBADO para entrega' if ok else 'NO APROBADO - corregir errores'}")
sys.exit(0 if ok else 1)
