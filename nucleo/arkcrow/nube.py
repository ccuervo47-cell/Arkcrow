"""Modelo en la nube (Claude API) para tareas pesadas y búsqueda web. Solo se usa en modo ONLINE.

Configuración en .env:
  ANTHROPIC_API_KEY=...            (la clave la configura el usuario; nunca se guarda en memoria/)
  ARKCROW_MODELO_NUBE=claude-opus-5-5
  ARKCROW_ESFUERZO_NUBE=medium     (low | medium | high | xhigh | max)

Si el modelo declina una solicitud (stop_reason "refusal"), la API la reintenta en el modelo de respaldo que
Anthropic recomienda (fallbacks="default").
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from . import llm  # noqa: F401  (carga .env)

MODELO_NUBE = os.environ.get("ARKCROW_MODELO_NUBE", "claude-opus-5-5")
ESFUERZO = os.environ.get("ARKCROW_ESFUERZO_NUBE", "medium")
UBICACION = {"type": "approximate", "city": "Bogotá", "region": "Bogotá D.C.", "country": "CO",
             "timezone": "America/Bogota"}


class NubeNoDisponible(RuntimeError):
    pass


@dataclass
class RespuestaNube:
    texto: str
    modelo: str
    fuentes_web: list[dict] = field(default_factory=list)
    rechazada: bool = False


def configurada() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def _cliente():
    try:
        import anthropic
    except ImportError as e:
        raise NubeNoDisponible("Falta el paquete 'anthropic' (pip install anthropic).") from e
    if not configurada():
        raise NubeNoDisponible("No hay clave de API: agregue ANTHROPIC_API_KEY en el archivo .env.")
    return anthropic.Anthropic(timeout=180, max_retries=2)


def preguntar(sistema: str, mensajes: list[dict], web: bool = False, esfuerzo: str | None = None,
              cliente=None) -> RespuestaNube:
    import anthropic
    cliente = cliente or _cliente()
    params = dict(model=MODELO_NUBE, max_tokens=16000, system=sistema,
                  output_config={"effort": esfuerzo or ESFUERZO},
                  betas=["server-side-fallback-2026-07-01"], fallbacks="default")
    if web:
        params["tools"] = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 5,
                            "user_location": UBICACION}]
    historial = list(mensajes)
    try:
        r = cliente.beta.messages.create(messages=historial, **params)
        for _ in range(4):                       # búsquedas largas: el servidor pausa y se reanuda
            if r.stop_reason != "pause_turn":
                break
            historial = historial + [{"role": "assistant", "content": r.content}]
            r = cliente.beta.messages.create(messages=historial, **params)
    except anthropic.AuthenticationError as e:
        raise NubeNoDisponible("La clave de API no es válida.") from e
    except anthropic.RateLimitError as e:
        raise NubeNoDisponible("Límite de uso de la API alcanzado; intente más tarde.") from e
    except anthropic.APIStatusError as e:
        raise NubeNoDisponible(f"Error del servicio en la nube ({e.status_code}).") from e
    except anthropic.APIConnectionError as e:
        raise NubeNoDisponible("Sin conexión con el servicio en la nube.") from e
    if r.stop_reason == "refusal":
        return RespuestaNube("El modelo en la nube no atendió esta solicitud. Reformúlela o use el modelo local.",
                             r.model, rechazada=True)
    textos, fuentes = [], {}
    for b in r.content:
        if b.type == "text":
            textos.append(b.text)
            for c in getattr(b, "citations", None) or []:
                url = getattr(c, "url", None)
                if url:
                    fuentes[url] = getattr(c, "title", "") or url
        elif b.type == "web_search_tool_result" and isinstance(b.content, list):
            for res in b.content:
                if getattr(res, "url", None):
                    fuentes.setdefault(res.url, getattr(res, "title", "") or res.url)
    return RespuestaNube("".join(textos).strip(), r.model, [{"url": u, "titulo": t} for u, t in fuentes.items()])
