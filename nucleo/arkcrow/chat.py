"""Chat por consola de ARKCROW OBRA.

Comandos:
  /modo                 ver el modo actual (ONLINE/OFFLINE, modelos)
  /nube <pregunta>      forzar el modelo en la nube (si hay internet y clave)
  /local <pregunta>     forzar el modelo local
  /obra <nombre>        cambiar la obra activa
  /buscar <texto>       ver los fragmentos citados sin pasar por el modelo
  /indexar              reindexar conocimiento/ y memoria/
  /cola                 ver la cola "cuando haya internet"
  /encolar [texto]      dejar una consulta en la cola (por defecto, la última pregunta)
  /aprobar <id>         aprobar una tarea de la cola     ·  /descartar-tarea <id>
  /ejecutar             ejecutar las tareas APROBADAS (solo con internet)
  /memoria              propuestas de memoria pendientes  ·  /aplicar <id>  ·  /descartar <id>
  /respaldo             hacer un respaldo verificado ahora
  /salir
"""
from __future__ import annotations

import sys

from . import cola, conocimiento, enrutador, memoria, respaldo
from .asistente import Asistente, estado_modo


def _confirmar(texto: str) -> bool:
    try:
        return input(f"\n🔒 {texto} ").strip().lower() in ("si", "sí", "s", "yes", "y")
    except EOFError:
        return False


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    a = Asistente(confirmar=_confirmar)
    print(a.bienvenida())
    print("Escriba su pregunta (o /ayuda).\n")
    ultima = ""
    while True:
        try:
            linea = input("Usted> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not linea:
            continue
        cmd, _, arg = linea.partition(" ")
        try:
            if cmd in ("/salir", "/exit"):
                break
            elif cmd == "/ayuda":
                print(__doc__)
            elif cmd == "/modo":
                enrutador.hay_internet(forzar=True)
                print(estado_modo())
            elif cmd in ("/nube", "/local"):
                ultima = arg
                print("\nARKCROW " + a.responder(arg, forzar=cmd[1:]).mostrar() + "\n")
            elif cmd == "/obra":
                memoria.fijar_obra_activa(arg)
                a = Asistente(confirmar=_confirmar)
                print(f"Obra activa: {arg}")
            elif cmd == "/buscar":
                for r in conocimiento.buscar(arg, con=a.con):
                    print(f"\n{r['cita']}\n  {r['texto'][:300]}")
            elif cmd == "/indexar":
                print(conocimiento.indexar(a.con))
            elif cmd == "/cola":
                for t in cola.listar(None):
                    if t["estado"] in ("pendiente", "aprobada", "error"):
                        print(f"[{t['id']}] {t['estado'].upper():9s} {t['tipo']}: {t['descripcion']}")
                print("Apruebe con /aprobar <id> y ejecute con /ejecutar (requiere internet).")
            elif cmd == "/encolar":
                t = cola.agregar("consulta_web", arg or ultima, {"pregunta": arg or ultima}, memoria.obra_activa())
                print(f"En cola [{t['id']}]: {t['descripcion']}")
            elif cmd == "/aprobar":
                print(f"Aprobada: {cola.aprobar(arg)['descripcion']}")
            elif cmd == "/descartar-tarea":
                print(f"Descartada: {cola.descartar(arg)['descripcion']}")
            elif cmd == "/ejecutar":
                if not enrutador.hay_internet(forzar=True):
                    print("Sin internet: las tareas aprobadas se ejecutarán cuando haya conexión.")
                for t in cola.ejecutar_aprobadas(enrutador.hay_internet):
                    print(f"[{t['id']}] {t['estado'].upper()}: {t['resultado']}")
            elif cmd == "/memoria":
                for p in memoria.pendientes():
                    print(f"[{p['id']}] -> {p['archivo']}: {p['texto'][:200]}  ({p['motivo']})")
                print("Use /aplicar <id> para confirmar o /descartar <id>.")
            elif cmd == "/aplicar":
                print(f"Escrito en {memoria.aplicar(arg)}")
            elif cmd == "/descartar":
                memoria.descartar(arg)
                print("Descartada.")
            elif cmd == "/respaldo":
                print(f"Respaldo verificado: {respaldo.hacer()}")
            else:
                ultima = linea
                print("\nARKCROW " + a.responder(linea).mostrar() + "\n")
        except (KeyError, ValueError, RuntimeError) as e:
            print(f"⚠ {e}")


if __name__ == "__main__":
    main()
