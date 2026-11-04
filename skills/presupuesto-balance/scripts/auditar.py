"""Auditor del libro de costos (también sirve para libros hechos a mano con el formato de la empresa).
Uso: python skills/presupuesto-balance/scripts/auditar.py <libro.xlsx>"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "nucleo"))
from arkcrow.auditor import main  # noqa: E402

sys.exit(main())
