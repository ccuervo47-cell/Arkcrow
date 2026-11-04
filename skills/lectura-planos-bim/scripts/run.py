"""Atajo: ejecuta arkcrow.bim con los mismos argumentos. Ver SKILL.md."""
import runpy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "nucleo"))
runpy.run_module("arkcrow.bim", run_name="__main__")
