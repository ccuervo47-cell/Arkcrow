"""Crea o actualiza el archivo .env sin borrar lo que el usuario ya configuró.
Uso: python herramientas/configurar_env.py CLAVE=valor [CLAVE=valor ...]
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
env, ejemplo = RAIZ / ".env", RAIZ / ".env.example"
if not env.exists():
    env.write_text(ejemplo.read_text(encoding="utf-8"), encoding="utf-8")
lineas = env.read_text(encoding="utf-8").splitlines()
for par in sys.argv[1:]:
    clave, valor = par.split("=", 1)
    for i, l in enumerate(lineas):
        if l.split("=", 1)[0].strip() == clave:
            lineas[i] = f"{clave}={valor}"
            break
    else:
        lineas.append(f"{clave}={valor}")
env.write_text("\n".join(lineas) + "\n", encoding="utf-8")
print(f".env actualizado: {', '.join(p.split('=')[0] for p in sys.argv[1:])}")
