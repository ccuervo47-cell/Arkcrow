"""Revisor de calidad (última etapa de toda entrega). Uso: python skills/revisor-calidad/scripts/revisar.py <archivo> [--entregar]"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "nucleo"))
from arkcrow.revisor_calidad import revisar  # noqa: E402

if len(sys.argv) < 2:
    sys.exit(__doc__)
ok, md, rep = revisar(sys.argv[1], "--entregar" in sys.argv)
print(md)
print(f"\n{'APROBADO' if ok else 'NO APROBADO'} - reporte: {rep}")
sys.exit(0 if ok else 1)
