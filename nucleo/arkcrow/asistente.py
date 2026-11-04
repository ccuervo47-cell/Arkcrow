"""Núcleo conversacional: inicio de sesión, recuperación con citas y respuesta.

Modos de respuesta (siempre se informan al usuario):
  OFFLINE · modelo local    -> Ollama + base local (RAG)
  OFFLINE · solo búsqueda   -> sin modelo instalado: devuelve los fragmentos citados (respuesta extractiva)
  ONLINE  · nube            -> (Fase 6) modelo en la nube para tareas pesadas, respetando confidencialidad
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import conocimiento, llm, memoria

RAIZ = Path(__file__).resolve().parents[2]
COLA = RAIZ / "datos" / "cola.json"
MAX_MEMORIA = 12000   # caracteres de memoria que se envían al modelo


def reglas_agente() -> str:
    txt = (RAIZ / "AGENTS.md").read_text(encoding="utf-8")
    m = re.search(r"<!-- REGLAS:INICIO -->(.*?)<!-- REGLAS:FIN -->", txt, re.S)
    return (m.group(1) if m else txt).strip()


def pendientes_cola() -> list[dict]:
    try:
        return [t for t in json.loads(COLA.read_text(encoding="utf-8")) if t.get("estado") == "pendiente"]
    except (FileNotFoundError, json.JSONDecodeError):
        return []


NORMAS = [
    (r"nsr[\s-]*10", "NSR-10"), (r"retilap", "RETILAP"), (r"retie", "RETIE"), (r"\bras\b", "RAS"),
    (r"ntc[\s-]*(\d{3,5})", "NTC {}"), (r"resoluci[oó]n\s*(?:n[°o.]*\s*)?(\d{3,5})", "Resolución {}"),
    (r"decreto\s*(?:n[°o.]*\s*)?(\d{3,5})", "Decreto {}"),
]


def normas_faltantes(pregunta: str, con) -> list[str]:
    """Normas mencionadas en la pregunta que NO tienen ningún documento indexado en conocimiento/."""
    q = conocimiento.norm(pregunta)
    rutas = [conocimiento.norm(r[0]).replace("_", " ").replace("-", " ")
             for r in con.execute("SELECT ruta FROM docs WHERE ruta LIKE 'conocimiento/%' AND n > 0")]
    rutas = [r for r in rutas if not r.endswith("leeme.md")]
    faltan = []
    for patron, nombre in NORMAS:
        for m in re.finditer(patron, q):
            etiqueta = nombre.format(*m.groups()) if m.groups() else nombre
            clave = re.sub(r"[^a-z0-9]", "", conocimiento.norm(etiqueta)).replace("resolucion", "res").replace("decreto", "dec")
            numero = re.sub(r"\D", "", etiqueta)
            hay = any(clave in re.sub(r"[^a-z0-9]", "", r) or (numero and numero in r and len(numero) >= 3) for r in rutas)
            if not hay and etiqueta not in faltan:
                faltan.append(etiqueta)
    return faltan


@dataclass
class Modo:
    nombre: str          # "OFFLINE" | "ONLINE"
    motor: str           # "modelo local qwen2.5:7b" | "solo búsqueda" | ...
    modelo: str | None = None

    def etiqueta(self) -> str:
        return f"[{self.nombre} · {self.motor}]"


def detectar_modo() -> Modo:
    modelo = llm.elegir_modelo()
    if modelo:
        return Modo("OFFLINE", f"modelo local {modelo}", modelo)
    return Modo("OFFLINE", "solo búsqueda en la base local (sin modelo instalado)")


@dataclass
class Respuesta:
    texto: str
    modo: Modo
    fuentes: list[dict] = field(default_factory=list)
    segundos: float = 0.0

    def mostrar(self) -> str:
        return f"{self.modo.etiqueta()}\n{self.texto}\n\n({self.segundos:.1f} s)"


class Asistente:
    def __init__(self):
        self.memoria = memoria.cargar()
        self.historial: list[dict] = []
        self.con = conocimiento.conectar()

    # ------------------------------------------------------------ sesión
    def bienvenida(self) -> str:
        modo = detectar_modo()
        obra = memoria.obra_activa() or "(ninguna; use /obra <nombre>)"
        cola = pendientes_cola()
        props = memoria.pendientes()
        L = [f"ARKCROW OBRA {modo.etiqueta()}", f"Obra activa: {obra}"]
        L.append(f"Cola 'cuando haya internet': {len(cola)} pendiente(s)" +
                 ("".join(f"\n  - {t.get('descripcion', t)}" for t in cola[:5]) if cola else ""))
        if props:
            L.append(f"Propuestas de memoria por confirmar: {len(props)} (use /memoria)")
        n = self.con.execute("SELECT COUNT(*) FROM docs").fetchone()[0]
        L.append(f"Base de conocimiento: {n} documento(s) indexado(s).")
        return "\n".join(L)

    # ------------------------------------------------------------ respuesta
    def _contexto_memoria(self) -> str:
        partes, total = [], 0
        for ruta, txt in self.memoria.items():
            bloque = f"### {ruta}\n{txt.strip()}\n"
            if total + len(bloque) > MAX_MEMORIA:
                break
            partes.append(bloque)
            total += len(bloque)
        return "\n".join(partes)

    def responder(self, pregunta: str, k: int = 6) -> Respuesta:
        t0 = time.time()
        modo = detectar_modo()
        fuentes = conocimiento.buscar(pregunta, k=k, con=self.con)
        faltan = normas_faltantes(pregunta, self.con)
        aviso = (f"⚠ No tengo {', '.join(faltan)} en la base local, así que no puedo citarla. Agregue el PDF oficial a "
                 "conocimiento/normas/ (ver LEEME.md) y reindexe; mientras tanto, cualquier dato sobre esa norma "
                 "sería de memoria y NO verificado.\n\n") if faltan else ""
        if modo.modelo:
            try:
                texto = aviso + self._con_modelo(pregunta, fuentes, modo.modelo, faltan)
            except llm.OllamaNoDisponible:
                modo = Modo("OFFLINE", "solo búsqueda (el modelo local no respondió)")
                texto = aviso + self._extractiva(fuentes)
        else:
            texto = aviso + self._extractiva(fuentes)
        return Respuesta(texto, modo, fuentes, time.time() - t0)

    def _con_modelo(self, pregunta, fuentes, modelo, faltan=()) -> str:
        frag = "\n\n".join(f"{f['cita']}\n{f['texto']}" for f in fuentes) or "(no se encontraron fragmentos)"
        sistema = (f"{reglas_agente()}\n\n# MEMORIA DEL USUARIO\n{self._contexto_memoria()}\n\n"
                   "# INSTRUCCIONES DE RESPUESTA\n"
                   "Responde SOLO con base en la memoria y en los FRAGMENTOS de abajo. Cita cada dato con la "
                   "etiqueta exacta del fragmento, por ejemplo [memoria/empresa.md, sección «...»]. Si los fragmentos "
                   "no contienen la respuesta, di 'No tengo ese dato en la base local' y sugiere qué documento agregar."
                   + (f" NO tienes en la base local: {', '.join(faltan)}. No cites artículos ni valores de esas normas."
                      if faltan else ""))
        mensajes = [{"role": "system", "content": sistema}] + self.historial[-6:] + [
            {"role": "user", "content": f"FRAGMENTOS DE LA BASE LOCAL:\n{frag}\n\nPREGUNTA: {pregunta}"}]
        texto = llm.chat(mensajes, modelo=modelo)
        if fuentes and not re.search(r"\[[^\]]+,\s*[^\]]+\]", texto):
            texto += "\n\nFuentes consultadas: " + "; ".join(dict.fromkeys(f["cita"] for f in fuentes[:3]))
        self.historial += [{"role": "user", "content": pregunta}, {"role": "assistant", "content": texto}]
        return texto

    @staticmethod
    def _extractiva(fuentes) -> str:
        if not fuentes:
            return ("No tengo información sobre eso en la base local. Agregue el documento a conocimiento/ "
                    "y reindexe, o consúltelo cuando haya internet.")
        L = ["No hay modelo de lenguaje disponible; estos son los fragmentos más relevantes de la base local:"]
        for f in fuentes[:3]:
            texto = re.sub(r"\n{2,}", "\n", f["texto"]).strip()
            L.append(f"\n▸ {f['cita']}\n{texto[:900]}{'…' if len(texto) > 900 else ''}")
        return "\n".join(L)
