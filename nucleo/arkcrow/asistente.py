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

from . import cola as cola_mod
from . import conocimiento, enrutador, llm, memoria, nube

RAIZ = Path(__file__).resolve().parents[2]
COLA = RAIZ / "datos" / "cola.json"
MAX_MEMORIA = 3500    # caracteres de memoria que se envían al modelo local (más = más lento en CPU)
MAX_FRAGMENTO = 1000  # caracteres por fragmento citado
K_MODELO = 4          # fragmentos que se envían al modelo


def reglas_agente() -> str:
    txt = (RAIZ / "AGENTS.md").read_text(encoding="utf-8")
    m = re.search(r"<!-- REGLAS:INICIO -->(.*?)<!-- REGLAS:FIN -->", txt, re.S)
    return (m.group(1) if m else txt).strip()


def pendientes_cola() -> list[dict]:
    return cola_mod.listar("pendiente")


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
class Respuesta:
    texto: str
    decision: "enrutador.Decision"
    fuentes: list[dict] = field(default_factory=list)
    segundos: float = 0.0
    sugerir_cola: bool = False
    aviso_modo: str = ""

    def mostrar(self) -> str:
        cab = (self.aviso_modo + "\n" if self.aviso_modo else "") + self.decision.etiqueta()
        if self.decision.aviso_privacidad:
            cab += f"\n🔒 {self.decision.aviso_privacidad}"
        return f"{cab}\n{self.texto}\n\n({self.segundos:.1f} s)"


def estado_modo() -> str:
    online = enrutador.hay_internet()
    local = llm.elegir_modelo()
    partes = ["ONLINE" if online else "OFFLINE"]
    partes.append(f"modelo local {local}" if local else "sin modelo local (solo búsqueda)")
    if online:
        partes.append(f"nube de pago {nube.MODELO_NUBE}" if enrutador.nube_de_pago() and nube.configurada()
                      else "búsqueda web gratuita")
    return "[" + " · ".join(partes) + "]"


class Asistente:
    def __init__(self, confirmar=None):
        self.memoria = memoria.cargar()
        self.historial: list[dict] = []
        self.con = conocimiento.conectar()
        self.confirmar = confirmar           # función(texto) -> bool para autorizar envíos confidenciales
        self.ultimo_online = enrutador.hay_internet()

    # ------------------------------------------------------------ sesión
    def bienvenida(self) -> str:
        obra = memoria.obra_activa() or "(ninguna; use /obra <nombre>)"
        cola = pendientes_cola()
        props = memoria.pendientes()
        L = [f"ARKCROW OBRA {estado_modo()}", f"Obra activa: {obra}"]
        L.append(f"Cola 'cuando haya internet': {len(cola)} pendiente(s)" +
                 ("".join(f"\n  - [{t['id']}] {t.get('descripcion', t)}" for t in cola[:5]) if cola else ""))
        if cola and self.ultimo_online:
            L.append("  Hay internet: revise con /cola y apruebe lo que quiera ejecutar (/aprobar <id>, /ejecutar).")
        if props:
            L.append(f"Propuestas de memoria por confirmar: {len(props)} (use /memoria)")
        n = self.con.execute("SELECT COUNT(*) FROM docs").fetchone()[0]
        L.append(f"Base de conocimiento: {n} documento(s) indexado(s).")
        return "\n".join(L)

    def cambio_de_modo(self) -> str:
        """Devuelve un aviso si la conectividad cambió desde la última consulta."""
        ahora = enrutador.hay_internet()
        if ahora == self.ultimo_online:
            return ""
        self.ultimo_online = ahora
        if ahora:
            n = len(pendientes_cola())
            return ("🔄 CAMBIO DE MODO: ahora ONLINE." +
                    (f" Hay {n} tarea(s) en la cola 'cuando haya internet' (vea /cola)." if n else ""))
        return "🔄 CAMBIO DE MODO: ahora OFFLINE (sin internet). Respondo con el modelo local y la base local."

    # ------------------------------------------------------------ respuesta
    def _contexto_memoria(self) -> str:
        partes, total = [], 0
        orden = sorted(self.memoria.items(), key=lambda kv: (0 if "/proyectos/" in kv[0] else
                                                             1 if "empresa" in kv[0] else 2 if "lecciones" in kv[0] else 3))
        for ruta, txt in orden:
            bloque = f"### {ruta}\n{txt.strip()}\n"
            if total + len(bloque) > MAX_MEMORIA:
                break
            partes.append(bloque)
            total += len(bloque)
        return "\n".join(partes)

    def _sistema(self, faltan) -> str:
        return (f"{reglas_agente()}\n\n# MEMORIA DEL USUARIO\n{self._contexto_memoria()}\n\n"
                "# INSTRUCCIONES DE RESPUESTA\n"
                "Responde con base en la memoria y en los FRAGMENTOS de la base local. Cita cada dato con la "
                "etiqueta exacta del fragmento, por ejemplo [memoria/empresa.md, sección «...»]. Si los fragmentos "
                "no contienen la respuesta, di 'No tengo ese dato en la base local' y sugiere qué documento agregar. "
                "Si usas búsqueda web, cita la URL y distingue claramente lo que viene de la web."
                + (f" NO tienes en la base local: {', '.join(faltan)}. No cites artículos ni valores de esas normas "
                   "de memoria." if faltan else ""))

    def responder(self, pregunta: str, k: int = 6, forzar: str | None = None) -> Respuesta:
        t0 = time.time()
        aviso_modo = self.cambio_de_modo()
        fuentes = conocimiento.buscar(pregunta, k=k, con=self.con)
        faltan = normas_faltantes(pregunta, self.con)
        d = enrutador.decidir(pregunta, fuentes, forzar=forzar, confirmar=self.confirmar)
        aviso = (f"⚠ No tengo {', '.join(faltan)} en la base local, así que no puedo citarla. Agregue el PDF oficial a "
                 "conocimiento/normas/ (ver LEEME.md) y reindexe; mientras tanto, cualquier dato sobre esa norma "
                 "sería de memoria y NO verificado.\n\n") if faltan else ""
        sugerir = d.modo == "OFFLINE" and bool(enrutador.PESADO.search(pregunta))
        texto = None
        if d.motor == "nube":
            try:
                texto = aviso + self._con_nube(pregunta, d, faltan)
            except nube.NubeNoDisponible as e:
                d = enrutador.Decision(d.modo, "local" if llm.elegir_modelo() else "busqueda", llm.elegir_modelo(),
                                       f"la nube falló: {e}", fuentes)
                aviso = f"(La nube no respondió: {e} Uso el modo local.)\n\n" + aviso
        if d.motor == "web":
            if faltan:
                aviso = (f"⚠ {', '.join(faltan)} no está en la base local. Lo que sigue viene de INTERNET: verifíquelo "
                         "en el documento oficial y, si sirve, descárguelo a conocimiento/normas/ para citarlo por "
                         "página.\n\n")
            texto = aviso + self._con_web(pregunta, d, faltan)
        if texto is None and d.motor == "local":
            try:
                texto = aviso + self._con_modelo(pregunta, fuentes, d.modelo, faltan)
            except llm.OllamaNoDisponible as e:
                d = enrutador.Decision(d.modo, "busqueda", None, "el modelo local no respondió", fuentes)
                demora = "tardó demasiado" if "timed out" in str(e).lower() or "timeout" in str(e).lower() else "no respondió"
                aviso += (f"⏱ El modelo local {demora}. Haga una pregunta más concreta (un tema o un ítem a la vez) "
                          "o cambie a un modelo más pequeño en .env. Mientras tanto, estos son los fragmentos:\n\n")
        if texto is None:
            texto = aviso + self._extractiva(fuentes)
        if sugerir:
            texto += ("\n\n💡 Esta consulta parece necesitar internet. Puedo dejarla en la cola 'cuando haya "
                      "internet' (/encolar).")
        return Respuesta(texto, d, fuentes, time.time() - t0, sugerir, aviso_modo)

    def _mensajes(self, pregunta, fuentes) -> list[dict]:
        frag = "\n\n".join(f"{f['cita']}\n{f['texto'][:MAX_FRAGMENTO]}" for f in fuentes[:K_MODELO]) \
            or "(no se encontraron fragmentos)"
        return self.historial[-6:] + [
            {"role": "user", "content": f"FRAGMENTOS DE LA BASE LOCAL:\n{frag}\n\nPREGUNTA: {pregunta}"}]

    def _con_nube(self, pregunta, d, faltan) -> str:
        r = nube.preguntar(self._sistema(faltan), self._mensajes(pregunta, d.fuentes), web=d.web)
        texto = r.texto
        if r.fuentes_web:
            texto += "\n\nFuentes web:\n" + "\n".join(f"- {f['titulo']}: {f['url']}" for f in r.fuentes_web[:8])
        if r.modelo and r.modelo != d.modelo:
            d.modelo = r.modelo
        self.historial += [{"role": "user", "content": pregunta}, {"role": "assistant", "content": texto}]
        return texto

    def _con_web(self, pregunta, d, faltan) -> str:
        from . import web_libre
        try:
            paginas = web_libre.investigar(pregunta)
        except Exception as e:  # noqa: BLE001
            paginas, d.motivo = [], f"falló la búsqueda web: {e}"
        if not paginas:
            d.motor = "local" if d.modelo else "busqueda"
            d.web = False
            texto = "(La búsqueda web no devolvió resultados.)\n\n"
            return texto + (self._con_modelo(pregunta, d.fuentes, d.modelo, faltan) if d.modelo
                            else self._extractiva(d.fuentes))
        web = "\n\n".join(f"[WEB {i}] {p['titulo']} - {p['url']}\n{p.get('texto') or p['resumen']}"
                           for i, p in enumerate(paginas, start=1))
        lista = "\n".join(f"[WEB {i}] {p['titulo']}: {p['url']}" for i, p in enumerate(paginas, start=1))
        if not d.modelo:
            return ("Resultados de la búsqueda web gratuita (sin modelo local para resumirlos):\n" +
                    "\n".join(f"\n▸ {p['titulo']}\n  {p['url']}\n  {(p.get('texto') or p['resumen'])[:400]}"
                              for p in paginas))
        mensajes = [{"role": "system", "content": self._sistema(faltan) + " Los resultados WEB vienen de internet: "
                     "cítalos como [WEB n] con su URL y advierte si no son fuente oficial."}] + \
            self._mensajes(pregunta, d.fuentes)
        mensajes[-1]["content"] = f"RESULTADOS WEB:\n{web}\n\n" + mensajes[-1]["content"]
        try:
            texto = llm.chat(mensajes, modelo=d.modelo)
        except llm.OllamaNoDisponible:
            return "El modelo local no respondió. Resultados web:\n" + lista
        self.historial += [{"role": "user", "content": pregunta}, {"role": "assistant", "content": texto}]
        return texto + "\n\nFuentes web:\n" + lista

    def _con_modelo(self, pregunta, fuentes, modelo, faltan=()) -> str:
        mensajes = [{"role": "system", "content": self._sistema(faltan)}] + self._mensajes(pregunta, fuentes)
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
        L = ["Fragmentos más relevantes de la base local:"]
        for f in fuentes[:3]:
            texto = re.sub(r"\n{2,}", "\n", f["texto"]).strip()
            L.append(f"\n▸ {f['cita']}\n{texto[:900]}{'…' if len(texto) > 900 else ''}")
        return "\n".join(L)
