"""Cliente mínimo de Ollama (motor local), sin dependencias externas.

Variables (archivo .env o entorno):
  OLLAMA_HOST          http://127.0.0.1:11434
  ARKCROW_MODELO       modelo principal (lo fija el instalador según la RAM)
  ARKCROW_MODELO_RESP  modelo pequeño de respaldo
  ARKCROW_EMBED        modelo de embeddings (bge-m3 por defecto)
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]


def cargar_env(ruta: Path = RAIZ / ".env") -> None:
    if not ruta.exists():
        return
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if linea and not linea.startswith("#") and "=" in linea:
            k, v = linea.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


cargar_env()
HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
MODELO = os.environ.get("ARKCROW_MODELO", "qwen2.5:7b")
MODELO_RESP = os.environ.get("ARKCROW_MODELO_RESP", "qwen2.5:3b")
EMBED = os.environ.get("ARKCROW_EMBED", "bge-m3")


class OllamaNoDisponible(RuntimeError):
    pass


def _post(ruta: str, datos: dict, timeout: float = 300) -> dict:
    req = urllib.request.Request(f"{HOST}{ruta}", data=json.dumps(datos).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
        raise OllamaNoDisponible(f"Ollama no responde en {HOST}: {e}") from e


def modelos_instalados() -> list[str]:
    try:
        with urllib.request.urlopen(f"{HOST}/api/tags", timeout=3) as r:
            return [m["name"] for m in json.loads(r.read()).get("models", [])]
    except Exception:  # noqa: BLE001
        return []


def _instalado(nombre: str, lista: list[str]) -> bool:
    return any(m == nombre or m.split(":")[0] == nombre or m == f"{nombre}:latest" for m in lista)


def elegir_modelo() -> str | None:
    lista = modelos_instalados()
    for m in (MODELO, MODELO_RESP):
        if _instalado(m, lista):
            return m
    return None


def embed_disponible() -> bool:
    return _instalado(EMBED, modelos_instalados())


def chat(mensajes: list[dict], modelo: str | None = None, temperatura: float = 0.2) -> str:
    modelo = modelo or elegir_modelo()
    if not modelo:
        raise OllamaNoDisponible("No hay modelo local instalado.")
    r = _post("/api/chat", {"model": modelo, "messages": mensajes, "stream": False,
                            "options": {"temperature": temperatura, "num_ctx": 8192}})
    return r["message"]["content"]


def embeber(textos: list[str]) -> list[list[float]]:
    r = _post("/api/embed", {"model": EMBED, "input": textos}, timeout=600)
    return r["embeddings"]
