"""Interfaz de chat en el navegador (100 % local, sin CDN ni recursos externos).

Escucha solo en 127.0.0.1 (no se ve desde la red). Una sola persona usuaria.
Uso: python -m arkcrow.web [--puerto 8765] [--sin-navegador]
"""
from __future__ import annotations

import argparse
import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import cola, conocimiento, enrutador, memoria
from .asistente import Asistente, estado_modo


class NecesitaConfirmacion(Exception):
    def __init__(self, texto):
        super().__init__(texto)
        self.texto = texto


class App:
    def __init__(self):
        self.lock = threading.Lock()
        self.asistente = Asistente()
        self.ultima = ""

    def chat(self, pregunta: str, forzar: str | None, autorizar: bool | None) -> dict:
        def confirmar(texto):
            if autorizar is None:
                raise NecesitaConfirmacion(texto)
            return bool(autorizar)

        with self.lock:
            self.asistente.confirmar = confirmar
            self.ultima = pregunta
            try:
                r = self.asistente.responder(pregunta, forzar=forzar or None)
            except NecesitaConfirmacion as e:
                return {"confirmar": e.texto}
        return {"etiqueta": r.decision.etiqueta(), "modo": r.decision.modo, "aviso_modo": r.aviso_modo,
                "privacidad": r.decision.aviso_privacidad, "texto": r.texto, "segundos": round(r.segundos, 1),
                "sugerir_cola": r.sugerir_cola}

    def subir(self, nombre: str, destino: str, datos_b64: str) -> dict:
        """Guarda un archivo en conocimiento/<destino>/ (nunca sobrescribe) y reindexa."""
        import base64
        import re
        from pathlib import Path
        from .conocimiento import EXTENSIONES, RAIZ
        nombre = Path(nombre).name
        if Path(nombre).suffix.lower() not in EXTENSIONES:
            raise ValueError(f"Formato no soportado: {nombre}. Use PDF, Word (.docx), Excel (.xlsx), .txt, .md o .csv")
        destino = destino.strip().strip("/\\")
        if not re.fullmatch(r"(normas|empresa|precios|confidencial|obras/[a-z0-9][a-z0-9._-]{0,60})", destino):
            raise ValueError("Destino no válido")
        contenido = base64.b64decode(datos_b64.split(",", 1)[-1])
        if len(contenido) > 80 * 1024 * 1024:
            raise ValueError("El archivo supera 80 MB")
        carpeta = RAIZ / "conocimiento" / destino
        carpeta.mkdir(parents=True, exist_ok=True)
        final, n = carpeta / nombre, 2
        while final.exists():
            final = carpeta / f"{Path(nombre).stem}_{n}{Path(nombre).suffix}"
            n += 1
        final.write_bytes(contenido)
        with self.lock:
            r = conocimiento.indexar(self.asistente.con, verbose=False)
        return {"guardado": final.relative_to(RAIZ).as_posix(), "fragmentos": r["fragmentos"],
                "confidencial": destino == "confidencial"}

    def obras(self) -> list[str]:
        from .conocimiento import RAIZ
        nombres = {d.name for base in (RAIZ / "proyectos", RAIZ / "conocimiento" / "obras") if base.is_dir()
                   for d in base.iterdir() if d.is_dir() and not d.name.startswith(("zz-", "_", "."))}
        return sorted(nombres)

    def fijar_obra(self, nombre: str) -> dict:
        import re
        from datetime import date
        from .conocimiento import RAIZ
        slug = re.sub(r"[^a-z0-9._-]+", "-", conocimiento.norm(nombre).strip()).strip("-.")[:60]
        if not slug:
            raise ValueError("Nombre de obra no válido")
        for d in (RAIZ / "proyectos" / slug, RAIZ / "conocimiento" / "obras" / slug):
            d.mkdir(parents=True, exist_ok=True)
        estado = RAIZ / "memoria" / "proyectos" / slug / "estado.md"
        if not estado.exists():   # plantilla vacía de la obra (sin datos personales)
            estado.parent.mkdir(parents=True, exist_ok=True)
            estado.write_text(f"# Obra: {slug}\n\n- Creada: {date.today():%d/%m/%Y}\n- Estado: \n\n## Decisiones\n\n"
                              "## Pendientes\n\n## Contactos\n", encoding="utf-8")
        with self.lock:
            memoria.fijar_obra_activa(slug)
            self.asistente.memoria = memoria.cargar()
        return {"obra": slug}

    def estado(self) -> dict:
        with self.lock:
            n = self.asistente.con.execute("SELECT COUNT(*) FROM docs").fetchone()[0]
        return {"modo": estado_modo(), "online": enrutador.hay_internet(), "obra": memoria.obra_activa() or "(ninguna)",
                "documentos": n, "obras": self.obras(), "cola": [t for t in cola.listar(None) if t["estado"] in ("pendiente", "aprobada", "error")],
                "propuestas_memoria": len(memoria.pendientes())}


def crear_manejador(app: App, puerto: int):
    permitidos = {f"127.0.0.1:{puerto}", f"localhost:{puerto}"}

    class Manejador(BaseHTTPRequestHandler):
        def log_message(self, *a):  # silencioso
            pass

        def _json(self, datos, codigo=200):
            cuerpo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
            self.send_response(codigo)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(cuerpo)

        def _host_ok(self) -> bool:
            return self.headers.get("Host", "") in permitidos

        def do_GET(self):
            if not self._host_ok():
                return self._json({"error": "host no permitido"}, 403)
            if self.path == "/":
                cuerpo = PAGINA.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Security-Policy",
                                 "default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src 'self' data:")
                self.send_header("Content-Length", str(len(cuerpo)))
                self.end_headers()
                self.wfile.write(cuerpo)
            elif self.path == "/api/estado":
                self._json(app.estado())
            else:
                self._json({"error": "no existe"}, 404)

        def do_POST(self):
            origen = self.headers.get("Origin")
            if not self._host_ok() or (origen and origen.split("//")[-1] not in permitidos) or \
                    "application/json" not in self.headers.get("Content-Type", ""):
                return self._json({"error": "solicitud no permitida"}, 403)
            try:
                datos = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0)) or 0) or b"{}")
                if self.path == "/api/chat":
                    return self._json(app.chat(datos.get("pregunta", "").strip(), datos.get("forzar"), datos.get("autorizar")))
                if self.path == "/api/encolar":
                    texto = datos.get("texto") or app.ultima
                    return self._json(cola.agregar("consulta_web", texto, {"pregunta": texto}, memoria.obra_activa()))
                if self.path == "/api/cola/aprobar":
                    return self._json(cola.aprobar(datos["id"]))
                if self.path == "/api/cola/descartar":
                    return self._json(cola.descartar(datos["id"]))
                if self.path == "/api/cola/ejecutar":
                    return self._json({"hechas": cola.ejecutar_aprobadas(lambda: enrutador.hay_internet(forzar=True)),
                                       "online": enrutador.hay_internet()})
                if self.path == "/api/obra":
                    return self._json(app.fijar_obra(datos.get("nombre", "")))
                if self.path == "/api/subir":
                    return self._json(app.subir(datos.get("nombre", ""), datos.get("destino", ""), datos.get("datos", "")))
                if self.path == "/api/indexar":
                    with app.lock:
                        return self._json(conocimiento.indexar(app.asistente.con, verbose=False))
                self._json({"error": "no existe"}, 404)
            except (KeyError, ValueError) as e:
                self._json({"error": str(e)}, 400)
            except Exception as e:  # noqa: BLE001
                self._json({"error": f"{type(e).__name__}: {e}"}, 500)

    return Manejador


def servir(puerto: int = 8765, abrir: bool = True) -> ThreadingHTTPServer:
    app = App()
    for p in range(puerto, puerto + 20):
        try:
            srv = ThreadingHTTPServer(("127.0.0.1", p), crear_manejador(app, p))
            break
        except OSError:
            continue
    else:
        raise RuntimeError("No hay puertos libres entre 8765 y 8784")
    url = f"http://127.0.0.1:{srv.server_address[1]}/"
    print(f"ARKCROW OBRA abierto en {url}  (cierre esta ventana para salir)")
    if abrir:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    return srv


PAGINA = r"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ARKCROW OBRA</title>
<style>
:root{--fondo:#f4f5f7;--panel:#fff;--texto:#1d2330;--suave:#5b6475;--borde:#dde1e8;--azul:#1f3864;--azul2:#2f5597;
--verde:#1e7b45;--rojo:#b42318;--amarillo:#fff4ce}
@media (prefers-color-scheme:dark){:root{--fondo:#14171d;--panel:#1d2129;--texto:#e7eaf0;--suave:#9aa3b2;--borde:#323846;
--azul:#8fb0ff;--azul2:#5b7fd1;--verde:#5ccb8a;--rojo:#ff7b72;--amarillo:#3a3420}}
*{box-sizing:border-box}body{margin:0;font:15px/1.5 "Segoe UI",Arial,sans-serif;background:var(--fondo);color:var(--texto)}
header{display:flex;gap:12px;align-items:center;justify-content:space-between;padding:10px 16px;background:var(--panel);
border-bottom:1px solid var(--borde);flex-wrap:wrap}
h1{font-size:17px;margin:0;color:var(--azul);letter-spacing:.5px}
.chip{display:inline-block;padding:3px 10px;border-radius:999px;font-size:12px;font-weight:600;border:1px solid var(--borde)}
.on{color:var(--verde)}.off{color:var(--rojo)}
main{display:grid;grid-template-columns:1fr 300px;gap:12px;padding:12px;height:calc(100vh - 58px)}
@media (max-width:820px){main{grid-template-columns:1fr;height:auto}aside{order:2}}
#chat{background:var(--panel);border:1px solid var(--borde);border-radius:10px;display:flex;flex-direction:column;min-height:70vh}
#msgs{flex:1;overflow:auto;padding:14px}
.m{max-width:88%;margin:8px 0;padding:10px 12px;border-radius:10px;white-space:pre-wrap;word-wrap:break-word}
.u{margin-left:auto;background:var(--azul2);color:#fff}.a{background:var(--fondo);border:1px solid var(--borde)}
.et{font-size:12px;color:var(--suave);margin-bottom:4px;font-weight:600}.av{background:var(--amarillo);padding:4px 8px;border-radius:6px;margin-bottom:6px;font-size:13px}
form{display:flex;gap:8px;padding:10px;border-top:1px solid var(--borde)}
textarea{flex:1;resize:none;height:54px;padding:8px;border-radius:8px;border:1px solid var(--borde);background:var(--panel);color:var(--texto);font:inherit}
button{border:0;border-radius:8px;padding:8px 12px;background:var(--azul2);color:#fff;font-weight:600;cursor:pointer}
button.sec{background:transparent;color:var(--azul);border:1px solid var(--borde)}
select{border-radius:8px;border:1px solid var(--borde);background:var(--panel);color:var(--texto)}
aside{background:var(--panel);border:1px solid var(--borde);border-radius:10px;padding:12px;overflow:auto}
aside h2{font-size:14px;margin:4px 0 8px;color:var(--azul)}.t{border:1px solid var(--borde);border-radius:8px;padding:8px;margin:6px 0;font-size:13px}
.t b{font-size:11px}.small{font-size:12px;color:var(--suave)}a{color:var(--azul)}
</style></head><body>
<header><h1>ARKCROW OBRA</h1><span id="modo" class="chip">…</span><span class="small">Obra activa: <select id="obrasel" title="Cambiar obra activa"></select></span></header>
<main>
<section id="chat"><div id="msgs"></div>
<form id="f"><textarea id="q" placeholder="Escriba su pregunta (Enter para enviar, Shift+Enter nueva línea)"></textarea>
<select id="motor" title="Motor"><option value="">Automático</option><option value="local">Solo local</option>
<option value="web">Web gratuita</option></select><button>Enviar</button></form></section>
<aside><h2>Cola "cuando haya internet"</h2><div id="cola" class="small">—</div>
<button class="sec" id="encolar" type="button">+ Encolar última pregunta</button>
<button class="sec" id="ejecutar" type="button">Ejecutar aprobadas</button>
<h2 style="margin-top:16px">Subir documentos</h2>
<select id="destino" style="width:100%;padding:6px;margin-bottom:6px">
<option value="obras">Documento de la obra activa</option><option value="normas">Norma</option>
<option value="confidencial">Confidencial (nunca sale del equipo)</option><option value="empresa">Formato de la empresa</option>
<option value="precios">Precios</option></select>
<input type="file" id="archivo" multiple accept=".pdf,.docx,.xlsx,.txt,.md,.csv" style="width:100%;font-size:12px">
<div id="subiendo" class="small"></div>
<h2 style="margin-top:16px">Base de conocimiento</h2><div id="docs" class="small"></div>
<button class="sec" id="indexar" type="button">Reindexar documentos</button>
<p class="small">Todo corre en este equipo. Costo cero: sin servicios de pago.</p></aside>
</main>
<script>
const $=s=>document.querySelector(s);
const esc=t=>t.replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const enl=t=>esc(t).replace(/(https?:\/\/[^\s)\]]+)/g,'<a href="$1" target="_blank" rel="noopener">$1</a>')
 .replace(/\*\*([^*\n]+)\*\*/g,'<b>$1</b>').replace(/^#{1,4} (.*)$/gm,'<b>$1</b>').replace(/`([^`\n]+)`/g,'<code>$1</code>');
async function api(ruta,datos){const r=await fetch(ruta,datos===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(datos)});return r.json()}
function msg(cls,html){const d=document.createElement('div');d.className='m '+cls;d.innerHTML=html;$('#msgs').appendChild(d);$('#msgs').scrollTop=1e9;return d}
async function estado(){const e=await api('/api/estado');$('#modo').textContent=e.modo;$('#modo').className='chip '+(e.online?'on':'off');
const sel=$('#obrasel');if(document.activeElement!==sel){sel.innerHTML=e.obras.map(o=>`<option${o===e.obra?' selected':''}>${esc(o)}</option>`).join('')+'<option value="__nueva">+ Nueva obra…</option>';}obraActiva=e.obra.startsWith('(')?'':e.obra;$('#docs').textContent=e.documentos+' documento(s) indexado(s)';
$('#cola').innerHTML=e.cola.length?e.cola.map(t=>`<div class="t"><b>${esc(t.estado.toUpperCase())}</b> ${esc(t.descripcion)}<br>
${t.estado==='pendiente'?`<button class="sec" onclick="accion('aprobar','${t.id}')">Aprobar</button> <button class="sec" onclick="accion('descartar','${t.id}')">Descartar</button>`:esc(String(t.resultado||''))}</div>`).join(''):'Sin tareas pendientes.'}
async function accion(a,id){await api('/api/cola/'+a,{id});estado()}
async function enviar(q,autorizar){const espera=msg('a','<span class="small">Pensando…</span>');
const r=await api('/api/chat',{pregunta:q,forzar:$('#motor').value,autorizar});espera.remove();
if(r.confirmar){const ok=confirm('🔒 '+r.confirmar);return enviar(q,ok)}
if(r.error){msg('a','⚠ '+esc(r.error));return}
let h='';if(r.aviso_modo)h+=`<div class="av">${esc(r.aviso_modo)}</div>`;if(r.privacidad)h+=`<div class="av">🔒 ${esc(r.privacidad)}</div>`;
msg('a',h+`<div class="et">${esc(r.etiqueta)} · ${r.segundos} s</div>`+enl(r.texto));estado()}
$('#f').onsubmit=e=>{e.preventDefault();const q=$('#q').value.trim();if(!q)return;msg('u',esc(q));$('#q').value='';enviar(q,null)};
$('#q').onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();$('#f').requestSubmit()}};
$('#encolar').onclick=async()=>{await api('/api/encolar',{});estado()};
$('#ejecutar').onclick=async()=>{const r=await api('/api/cola/ejecutar',{});msg('a',r.online?`Ejecutadas: ${r.hechas.length}`:'Sin internet: se ejecutarán cuando haya conexión.');estado()};
$('#indexar').onclick=async()=>{const r=await api('/api/indexar',{});msg('a','Índice actualizado: '+r.fragmentos+' fragmentos.');estado()};
let obraActiva='';
$('#obrasel').onchange=async e=>{let n=e.target.value;if(n==='__nueva'){n=prompt('Nombre de la nueva obra (ej.: corozal)');if(!n){estado();return}}
const r=await api('/api/obra',{nombre:n});msg('a',r.error?'⚠ '+esc(r.error):`🏗 Obra activa: <b>${esc(r.obra)}</b>. Los documentos que suba como "obra activa" quedan en <code>conocimiento/obras/${esc(r.obra)}/</code>.`);estado()};
$('#archivo').onchange=async e=>{const files=[...e.target.files];let d=$('#destino').value;
if(d==='obras')d='obras/'+(obraActiva||'general').toLowerCase().replace(/[^a-z0-9._-]+/g,'-');
for(const f of files){$('#subiendo').textContent='Subiendo '+f.name+'…';
const b64=await new Promise(ok=>{const r=new FileReader();r.onload=()=>ok(r.result);r.readAsDataURL(f)});
const r=await api('/api/subir',{nombre:f.name,destino:d,datos:b64});
msg('a',r.error?'⚠ '+esc(r.error):`📄 Guardado en <code>${esc(r.guardado)}</code>${r.confidencial?' (CONFIDENCIAL)':''} y indexado (${r.fragmentos} fragmentos en total). Ya puede preguntarme sobre él.`)}
$('#subiendo').textContent='';e.target.value='';estado()};
estado();setInterval(estado,30000);
msg('a','Hola, Cristian. Pregúnteme por APU, cantidades, normas de la base local o la obra activa.');
</script></body></html>"""


def main():
    ap = argparse.ArgumentParser(description="ARKCROW OBRA en el navegador")
    ap.add_argument("--puerto", type=int, default=8765)
    ap.add_argument("--sin-navegador", action="store_true")
    a = ap.parse_args()
    srv = servir(a.puerto, not a.sin_navegador)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
