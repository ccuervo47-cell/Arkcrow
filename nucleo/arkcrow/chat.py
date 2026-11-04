"""Chat por consola de ARKCROW OBRA.

Comandos:
  /obra <nombre>      cambiar la obra activa
  /buscar <texto>     ver los fragmentos citados sin pasar por el modelo
  /indexar            reindexar conocimiento/ y memoria/
  /memoria            ver las propuestas de memoria pendientes
  /aplicar <id>       confirmar y escribir una propuesta de memoria
  /descartar <id>     descartar una propuesta
  /salir
"""
from __future__ import annotations

import sys

from . import conocimiento, memoria
from .asistente import Asistente


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    a = Asistente()
    print(a.bienvenida())
    print("Escriba su pregunta (o /ayuda).\n")
    while True:
        try:
            linea = input("Usted> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not linea:
            continue
        cmd, _, arg = linea.partition(" ")
        if cmd in ("/salir", "/exit"):
            break
        elif cmd == "/ayuda":
            print(__doc__)
        elif cmd == "/obra":
            memoria.fijar_obra_activa(arg)
            a = Asistente()
            print(f"Obra activa: {arg}")
        elif cmd == "/buscar":
            for r in conocimiento.buscar(arg, con=a.con):
                print(f"\n{r['cita']}\n  {r['texto'][:300]}")
        elif cmd == "/indexar":
            print(conocimiento.indexar(a.con))
        elif cmd == "/memoria":
            for p in memoria.pendientes():
                print(f"[{p['id']}] -> {p['archivo']}: {p['texto'][:200]}  ({p['motivo']})")
            print("Use /aplicar <id> para confirmar o /descartar <id>.")
        elif cmd == "/aplicar":
            print(f"Escrito en {memoria.aplicar(arg)}")
        elif cmd == "/descartar":
            memoria.descartar(arg)
            print("Descartada.")
        else:
            print("\nARKCROW " + a.responder(linea).mostrar() + "\n")


if __name__ == "__main__":
    main()
