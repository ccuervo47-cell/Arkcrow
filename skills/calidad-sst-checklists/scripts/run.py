"""Atajo: ejecuta arkcrow.checklists con los mismos argumentos. Ver SKILL.md."""
import runpy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "nucleo"))
runpy.run_module("arkcrow.checklists", run_name="__main__")
