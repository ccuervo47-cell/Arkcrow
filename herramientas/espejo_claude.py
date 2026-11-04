"""Copia skills/*/SKILL.md a .claude/skills/<nombre>/SKILL.md (espejo para Claude Code).
Las rutas de los SKILL.md son relativas a la raíz ArkcrowObra, que es donde se abre Claude Code.
Ejecutar después de modificar una skill:  python herramientas/espejo_claude.py
"""
import shutil
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
destino = RAIZ / ".claude" / "skills"
n = 0
for skill in sorted((RAIZ / "skills").glob("*/SKILL.md")):
    d = destino / skill.parent.name
    d.mkdir(parents=True, exist_ok=True)
    shutil.copy(skill, d / "SKILL.md")
    n += 1
print(f"{n} skills copiadas a {destino}")
