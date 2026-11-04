"""Cola de tareas "cuando haya internet" (datos/cola.json).

Tipos de tarea:
  consulta_web       pregunta que necesita internet (normativa reciente, precios de mercado...)
  actualizar_precios investigar precios actuales de insumos -> deja una PROPUESTA (no cambia la base sola)
  descargar_norma    descargar un PDF oficial a conocimiento/normas/ y reindexar
  enviar_borrador    recordatorio: abrir un borrador para que EL USUARIO lo envíe (ARKCROW nunca envía)

Flujo: al detectar internet se muestran las pendientes; solo se ejecutan las que el usuario APRUEBA.
Estados: pendiente -> aprobada -> hecha | error ; o descartada.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
COLA = RAIZ / "datos" / "cola.json"
TIPOS = {"consulta_web", "actualizar_precios", "descargar_norma", "enviar_borrador"}


def _leer() -> list[dict]:
    try:
        return json.loads(COLA.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _guardar(tareas: list[dict]) -> None:
    COLA.parent.mkdir(parents=True, exist_ok=True)
    COLA.write_text(json.dumps(tareas, ensure_ascii=False, indent=2), encoding="utf-8")


def agregar(tipo: str, descripcion: str, datos: dict | None = None, obra: str | None = None) -> dict:
    if tipo not in TIPOS:
        raise ValueError(f"Tipo de tarea desconocido: {tipo}. Opciones: {', '.join(sorted(TIPOS))}")
    t = {"id": uuid.uuid4().hex[:6], "tipo": tipo, "descripcion": descripcion, "datos": datos or {}, "obra": obra,
         "creada": datetime.now().isoformat(timespec="minutes"), "estado": "pendiente", "resultado": None}
    tareas = _leer()
    tareas.append(t)
    _guardar(tareas)
    return t


def listar(estado: str | None = "pendiente") -> list[dict]:
    return [t for t in _leer() if estado is None or t["estado"] == estado]


def _cambiar(id_: str, **cambios) -> dict:
    tareas = _leer()
    t = next((x for x in tareas if x["id"] == id_), None)
    if not t:
        raise KeyError(f"No existe la tarea {id_}")
    t.update(cambios)
    _guardar(tareas)
    return t


def aprobar(id_: str) -> dict:
    return _cambiar(id_, estado="aprobada", aprobada=datetime.now().isoformat(timespec="minutes"))


def descartar(id_: str) -> dict:
    return _cambiar(id_, estado="descartada")


def ejecutar_aprobadas(hay_internet, ejecutores: dict | None = None) -> list[dict]:
    """Ejecuta SOLO las tareas aprobadas. `ejecutores` permite inyectar funciones (pruebas)."""
    if not hay_internet():
        return []
    ejecutores = ejecutores or EJECUTORES
    hechas = []
    for t in listar("aprobada"):
        try:
            res = ejecutores[t["tipo"]](t)
            hechas.append(_cambiar(t["id"], estado="hecha", resultado=res,
                                   terminada=datetime.now().isoformat(timespec="minutes")))
        except Exception as e:  # noqa: BLE001
            hechas.append(_cambiar(t["id"], estado="error", resultado=str(e)))
    return hechas


# ---------------------------------------------------------------- ejecutores reales
def _consulta_web(t):
    from . import nube
    r = nube.preguntar("Eres el asistente técnico de un arquitecto residente en Colombia. Responde en español, "
                       "citando las fuentes web (URL). Si no encuentras fuente oficial, dilo.",
                       [{"role": "user", "content": t["datos"].get("pregunta", t["descripcion"])}], web=True)
    destino = _guardar_resultado(t, r.texto + "\n\nFuentes:\n" + "\n".join(f"- {f['titulo']}: {f['url']}" for f in r.fuentes_web))
    return f"Respuesta guardada en {destino}"


def _actualizar_precios(t):
    from . import db, nube
    ins = db.insumos()
    codigos = t["datos"].get("codigos") or [c for c, r in ins.items() if r["tipo"] == "MAT"]
    lista = "\n".join(f"- {c}: {ins[c]['descripcion']} ({ins[c]['unidad']}), precio actual en base {ins[c]['precio']:,.0f}"
                      for c in codigos if c in ins)
    r = nube.preguntar("Investigas precios de materiales de construcción en Bogotá, Colombia. Para cada insumo da "
                       "precio de mercado actual en COP, unidad, proveedor/fuente con URL y fecha. Si no hay dato "
                       "confiable, escribe 'sin dato'. No inventes.", [{"role": "user", "content": lista}], web=True)
    destino = _guardar_resultado(t, "PROPUESTA DE ACTUALIZACIÓN DE PRECIOS (revisar antes de aplicar a la base)\n\n"
                                    + r.texto + "\n\nFuentes:\n" + "\n".join(f"- {f['url']}" for f in r.fuentes_web))
    return f"Propuesta guardada en {destino} (la base de precios NO se modificó)"


def _descargar_norma(t):
    import urllib.request
    from . import conocimiento
    url, nombre = t["datos"]["url"], t["datos"].get("archivo") or t["datos"]["url"].rsplit("/", 1)[-1]
    destino = RAIZ / "conocimiento" / "normas" / nombre
    if destino.exists():
        raise FileExistsError(f"Ya existe {destino.name}; no se sobrescribe.")
    with urllib.request.urlopen(url, timeout=120) as r:
        datos = r.read()
    if not datos.startswith(b"%PDF"):
        raise ValueError("El archivo descargado no es un PDF.")
    destino.write_bytes(datos)
    conocimiento.indexar(verbose=False)
    return f"Descargada {destino.name} ({len(datos) // 1024} KB) e indexada"


def _enviar_borrador(t):
    return (f"Recordatorio: el borrador {t['datos'].get('archivo', '')} está listo para que USTED lo revise y lo envíe. "
            "ARKCROW no envía comunicaciones.")


def _guardar_resultado(t, texto) -> Path:
    d = RAIZ / "datos" / "resultados_cola"
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"{datetime.now():%Y-%m-%d_%H%M}_{t['tipo']}_{t['id']}.md"
    f.write_text(f"# {t['descripcion']}\n\n{texto}\n", encoding="utf-8")
    return f


EJECUTORES = {"consulta_web": _consulta_web, "actualizar_precios": _actualizar_precios,
              "descargar_norma": _descargar_norma, "enviar_borrador": _enviar_borrador}
