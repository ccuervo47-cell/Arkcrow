"""Búsqueda web GRATUITA (sin clave ni costo): DuckDuckGo HTML + Wikipedia en español.

Se usa en modo ONLINE cuando la nube de pago está apagada (por defecto). El modelo LOCAL resume lo encontrado
y cita las URL. Solo sale a internet el TEXTO DE LA BÚSQUEDA; los documentos de la obra nunca se envían.

Uso: python -m arkcrow.web_libre "precio cemento gris Bogotá 2026"
"""
from __future__ import annotations

import html
import json
import re
import sys
import urllib.parse
import urllib.request

AGENTE = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ArkcrowObra/1.0"
MAX_TEXTO = 3500


def _get(url: str, timeout: int = 12) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": AGENTE, "Accept-Language": "es-CO,es;q=0.9"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        tipo = r.headers.get_content_charset() or "utf-8"
        return r.read(1_500_000).decode(tipo, errors="ignore")


def parsear_duckduckgo(pagina: str) -> list[dict]:
    """Extrae resultados del HTML de html.duckduckgo.com/html/."""
    resultados = []
    for m in re.finditer(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>(.*?)(?=<a[^>]+class="result__a"|\Z)',
                         pagina, re.S):
        href, titulo, resto = m.groups()
        q = urllib.parse.urlparse(html.unescape(href))
        url = urllib.parse.parse_qs(q.query).get("uddg", [html.unescape(href)])[0]
        if url.startswith("//"):
            url = "https:" + url
        snip = re.search(r'class="result__snippet"[^>]*>(.*?)</a>', resto, re.S)
        resultados.append({"titulo": _limpio(titulo), "url": url, "resumen": _limpio(snip.group(1)) if snip else ""})
    return [r for r in resultados if r["url"].startswith("http") and "duckduckgo.com/y.js" not in r["url"]]


def buscar(consulta: str, n: int = 5) -> list[dict]:
    res = []
    try:
        res = parsear_duckduckgo(_get("https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": consulta, "kl": "co-es"})))
    except Exception:  # noqa: BLE001
        pass
    if not res:   # respaldo: Wikipedia en español
        try:
            datos = json.loads(_get("https://es.wikipedia.org/w/api.php?" + urllib.parse.urlencode(
                {"action": "query", "list": "search", "srsearch": consulta, "format": "json", "srlimit": n})))
            res = [{"titulo": s["title"], "url": "https://es.wikipedia.org/wiki/" + urllib.parse.quote(s["title"].replace(" ", "_")),
                    "resumen": _limpio(s.get("snippet", ""))} for s in datos["query"]["search"]]
        except Exception:  # noqa: BLE001
            pass
    return res[:n]


def texto_de_pagina(pagina: str) -> str:
    pagina = re.sub(r"(?is)<(script|style|nav|header|footer|noscript)[^>]*>.*?</\1>", " ", pagina)
    return _limpio(pagina)[:MAX_TEXTO]


def leer(url: str) -> str:
    if url.lower().endswith(".pdf"):
        return "(documento PDF: descárguelo con la cola 'descargar_norma' para indexarlo y citarlo por página)"
    try:
        return texto_de_pagina(_get(url))
    except Exception as e:  # noqa: BLE001
        return f"(no se pudo leer: {e})"


def investigar(consulta: str, n_paginas: int = 3) -> list[dict]:
    """Busca y lee las primeras páginas. Devuelve [{titulo, url, resumen, texto}]."""
    res = buscar(consulta)
    for r in res[:n_paginas]:
        r["texto"] = leer(r["url"])
    return res


def _limpio(t: str) -> str:
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", html.unescape(t)).strip()


if __name__ == "__main__":
    for r in investigar(" ".join(sys.argv[1:]) or "NSR-10"):
        print(f"- {r['titulo']}\n  {r['url']}\n  {r.get('texto', r['resumen'])[:300]}\n")
