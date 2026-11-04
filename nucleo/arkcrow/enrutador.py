"""Enrutador ONLINE / OFFLINE y control de privacidad.

- `hay_internet()`: prueba varios destinos con tiempo corto (respeta el proxy corporativo si existe).
  Cualquier respuesta HTTP (incluso 401/403) cuenta como conexión; solo falla si no hay red/DNS.
- `decidir()`: elige el motor para cada pregunta:
    * OFFLINE -> modelo local (Ollama) o, si no hay, solo búsqueda en la base local
    * ONLINE  -> nube (Claude) cuando hay internet + clave, y la tarea lo amerita o no hay modelo local
    * ONLINE GRATIS (por defecto) -> búsqueda web gratuita (DuckDuckGo/Wikipedia) + modelo local
  Preferencia en .env: ARKCROW_PREFERENCIA = auto | local | nube   (auto por defecto)
  Nube de pago: SOLO si ARKCROW_NUBE_DE_PAGO=si y hay clave. Por defecto está APAGADA (costo cero).
- Privacidad: si la pregunta o los fragmentos recuperados son CONFIDENCIALES, NO se envían a la nube sin
  confirmación explícita (callback `confirmar`). Sin confirmación: se quitan los fragmentos confidenciales
  o se responde con el modelo local.
"""
from __future__ import annotations

import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from . import llm, nube

DESTINOS = os.environ.get("ARKCROW_PRUEBA_RED",
                          "https://api.anthropic.com/v1/models,https://pypi.org/simple/,https://www.google.com/generate_204").split(",")
_CACHE = {"t": 0.0, "v": None}
TTL = 20  # segundos

PESADO = re.compile(r"\b(busca|buscar|investiga|internet|web|actualiza|actual(es|izad)|reciente|vigente|compara|"
                    r"redacta|analiza el documento|resume el pdf|norma nueva|cotiza|precio actual)\b", re.I)
MARCA_CONF = re.compile(r"confidencial|contrato firmado|presupuesto interno|margen|oferta econ[oó]mica", re.I)


def hay_internet(forzar: bool = False) -> bool:
    if os.environ.get("ARKCROW_FORZAR_OFFLINE") == "1":
        return False
    if not forzar and _CACHE["v"] is not None and time.time() - _CACHE["t"] < TTL:
        return _CACHE["v"]
    ok = False
    for url in DESTINOS:
        try:
            urllib.request.urlopen(urllib.request.Request(url.strip(), method="HEAD"), timeout=3)
            ok = True
        except urllib.error.HTTPError:
            ok = True            # el servidor respondió: hay internet
        except Exception:  # noqa: BLE001
            continue
        if ok:
            break
    _CACHE.update(t=time.time(), v=ok)
    return ok


@dataclass
class Decision:
    modo: str                 # ONLINE | OFFLINE
    motor: str                # nube | local | busqueda
    modelo: str | None
    motivo: str
    fuentes: list[dict] = field(default_factory=list)
    web: bool = False
    aviso_privacidad: str = ""

    def etiqueta(self) -> str:
        nombres = {"nube": f"nube {self.modelo}", "local": f"modelo local {self.modelo}",
                   "busqueda": "solo búsqueda en la base local",
                   "web": "búsqueda web gratuita + " + (f"modelo local {self.modelo}" if self.modelo else "sin modelo")}
        return f"[{self.modo} · {nombres[self.motor]}{' + web' if self.web and self.motor == 'nube' else ''}]"


def preferencia() -> str:
    return os.environ.get("ARKCROW_PREFERENCIA", "auto").lower()


def nube_de_pago() -> bool:
    return os.environ.get("ARKCROW_NUBE_DE_PAGO", "no").strip().lower() in ("si", "sí", "1", "true", "yes")


def decidir(pregunta: str, fuentes: list[dict], forzar: str | None = None, confirmar=None) -> Decision:
    """forzar: None | 'nube' | 'local' | 'web'. confirmar(texto) -> bool, para datos confidenciales."""
    online = hay_internet()
    local = llm.elegir_modelo()
    nube_ok = online and nube_de_pago() and nube.configurada()
    modo = "ONLINE" if online else "OFFLINE"
    pref = forzar or preferencia()
    necesita_web = bool(PESADO.search(pregunta))
    base_local = Decision(modo, "local" if local else "busqueda", local, "", fuentes)

    if pref == "local" or not online:
        base_local.motivo = "preferencia local" if pref == "local" else "sin internet"
        return base_local

    quiere_nube = nube_ok and (pref == "nube" or (pref == "auto" and (not local or necesita_web)))
    quiere_web = not quiere_nube and (pref == "web" or (pref in ("auto", "nube") and necesita_web))
    if not (quiere_nube or quiere_web):
        base_local.motivo = "tarea local" if local else "sin modelo local"
        return base_local

    # --- privacidad ---
    conf = [f for f in fuentes if f.get("confidencial")]
    pregunta_conf = bool(MARCA_CONF.search(pregunta))
    if quiere_web:   # a la web solo sale el texto de la búsqueda, nunca los documentos
        if pregunta_conf:
            ok = confirmar and confirmar("La búsqueda web enviaría a un buscador un texto que parece CONFIDENCIAL. "
                                         "¿Autoriza la búsqueda? (si/no)")
            if not ok:
                base_local.motivo, base_local.aviso_privacidad = "confidencial: sin búsqueda web", \
                    "No se hizo la búsqueda web (texto confidencial)."
                return base_local
        return Decision(modo, "web", local, "búsqueda web gratuita", fuentes, web=True)

    if conf or pregunta_conf:
        detalle = ", ".join(sorted({f["ruta"] for f in conf})) or "la pregunta menciona información confidencial"
        texto = (f"Esta consulta usaría información CONFIDENCIAL ({detalle}). ¿Autoriza enviarla al servicio en la "
                 "nube? (si/no)")
        if confirmar and confirmar(texto):
            return Decision(modo, "nube", nube.MODELO_NUBE, "autorizado por el usuario", fuentes,
                            web=necesita_web, aviso_privacidad="Envío de información confidencial AUTORIZADO.")
        limpias = [f for f in fuentes if not f.get("confidencial")]
        if pregunta_conf or not limpias:
            base_local.motivo = "confidencial sin autorización: se queda local"
            base_local.aviso_privacidad = "No se envió nada a la nube (información confidencial)."
            return base_local
        return Decision(modo, "nube", nube.MODELO_NUBE, "nube SIN los documentos confidenciales", limpias,
                        web=necesita_web,
                        aviso_privacidad=f"Se excluyeron {len(conf)} fragmento(s) confidencial(es) del envío a la nube.")
    return Decision(modo, "nube", nube.MODELO_NUBE, "tarea pesada o sin modelo local", fuentes, web=necesita_web)
