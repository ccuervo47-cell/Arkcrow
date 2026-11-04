"""Memoria persistente del asistente (carpeta memoria/).

- `cargar()` lee perfil, empresa, lecciones, preferencias y la obra activa, al iniciar cada sesión.
- El asistente NO escribe directo: `proponer()` deja la propuesta pendiente y `aplicar()` la escribe
  solo después de la confirmación del usuario.
- Nunca se guardan contraseñas, números de cuenta ni documentos de identidad (`datos_sensibles()`).
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
MEM = RAIZ / "memoria"
PROPUESTAS = MEM / "_propuestas.json"
BASE = ["perfil.md", "empresa.md", "lecciones.md", "preferencias.md"]

SENSIBLES = [
    (re.compile(r"contrase(ñ|n)a|password|clave\s*[:=]|pin\s*[:=]", re.I), "contraseña o clave"),
    (re.compile(r"\b(c\.?\s?c\.?|c[ée]dula|nit|pasaporte|documento)\b\D{0,15}\d[\d.\s-]{5,}", re.I), "documento de identidad"),
    (re.compile(r"\b(cuenta|cta\.?|ahorros|corriente|iban|tarjeta)\b\D{0,20}\d[\d\s-]{7,}", re.I), "número de cuenta o tarjeta"),
    (re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"), "número de tarjeta"),
    (re.compile(r"(sk|api|key|token)[-_][A-Za-z0-9_-]{16,}", re.I), "clave de API"),
]


def datos_sensibles(texto: str) -> list[str]:
    return sorted({nombre for rx, nombre in SENSIBLES if rx.search(texto)})


def obra_activa() -> str | None:
    f = MEM / "activa.txt"
    return f.read_text(encoding="utf-8").strip() or None if f.exists() else None


def fijar_obra_activa(obra: str) -> None:
    (MEM / "activa.txt").write_text(obra.strip() + "\n", encoding="utf-8")


def cargar() -> dict[str, str]:
    """Devuelve {ruta_relativa: contenido} con la memoria base y la de la obra activa."""
    out = {}
    for nombre in BASE:
        f = MEM / nombre
        if f.exists():
            out[f"memoria/{nombre}"] = f.read_text(encoding="utf-8")
    obra = obra_activa()
    if obra and (MEM / "proyectos" / obra).is_dir():
        for f in sorted((MEM / "proyectos" / obra).glob("*.md")):
            out[f"memoria/proyectos/{obra}/{f.name}"] = f.read_text(encoding="utf-8")
    return out


def _leer_prop() -> list[dict]:
    return json.loads(PROPUESTAS.read_text(encoding="utf-8")) if PROPUESTAS.exists() else []


def _guardar_prop(lista: list[dict]) -> None:
    PROPUESTAS.write_text(json.dumps(lista, ensure_ascii=False, indent=2), encoding="utf-8")


def proponer(archivo: str, texto: str, motivo: str = "") -> dict:
    """Registra una actualización pendiente. Rechaza datos sensibles."""
    destino = (MEM / archivo).resolve()
    if MEM.resolve() not in destino.parents:
        raise ValueError("Solo se puede escribir dentro de memoria/.")
    sens = datos_sensibles(texto)
    if sens:
        raise ValueError(f"No se guarda en memoria: contiene {', '.join(sens)}.")
    p = {"id": uuid.uuid4().hex[:6], "archivo": archivo, "texto": texto.strip(), "motivo": motivo,
         "fecha": datetime.now().isoformat(timespec="minutes")}
    lista = _leer_prop()
    lista.append(p)
    _guardar_prop(lista)
    return p


def pendientes() -> list[dict]:
    return _leer_prop()


def aplicar(id_: str) -> Path:
    """Escribe la propuesta (se llama SOLO después de que el usuario confirma)."""
    lista = _leer_prop()
    p = next((x for x in lista if x["id"] == id_), None)
    if not p:
        raise KeyError(f"No existe la propuesta {id_}")
    destino = MEM / p["archivo"]
    destino.parent.mkdir(parents=True, exist_ok=True)
    previo = destino.read_text(encoding="utf-8") if destino.exists() else ""
    sep = "" if previo.endswith("\n") or not previo else "\n"
    destino.write_text(previo + sep + f"\n<!-- {p['fecha']} -->\n{p['texto']}\n", encoding="utf-8")
    _guardar_prop([x for x in lista if x["id"] != id_])
    return destino


def descartar(id_: str) -> None:
    _guardar_prop([x for x in _leer_prop() if x["id"] != id_])
