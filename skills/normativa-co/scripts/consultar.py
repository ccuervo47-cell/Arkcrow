"""Consulta de normativa colombiana SOLO sobre los documentos indexados en conocimiento/normas/.

Uso: python skills/normativa-co/scripts/consultar.py "pregunta" [--k 5]
Si la norma no está indexada, lo dice. Nunca responde de memoria.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "nucleo"))
from arkcrow import asistente, conocimiento  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("pregunta")
ap.add_argument("--k", type=int, default=5)
a = ap.parse_args()
con = conocimiento.conectar()
faltan = asistente.normas_faltantes(a.pregunta, con)
if faltan:
    print(f"⚠ No tengo {', '.join(faltan)} en la base local (conocimiento/normas/). Agregue el PDF oficial y reindexe "
          "con: python -m arkcrow.conocimiento indexar. No se citará esa norma de memoria.\n")
res = [r for r in conocimiento.buscar(a.pregunta, k=40, con=con)
       if r["ruta"].startswith("conocimiento/normas/") and not r["ruta"].lower().endswith("leeme.md")][:a.k]
if not res:
    print("No encontré fragmentos de normas indexadas que respondan la pregunta.")
    sys.exit(2)
for r in res:
    print(f"{r['cita']}\n{r['texto'][:1200]}\n")
