"""Base de conocimiento local (RAG) con citas de documento y página.

Indexa conocimiento/ y memoria/ en datos/indice.sqlite:
  - Búsqueda por palabras (SQLite FTS5, BM25). Funciona SIEMPRE, sin modelos.
  - Búsqueda semántica (embeddings de Ollama, p. ej. bge-m3) si el modelo está instalado.
  - Ambas se combinan con Reciprocal Rank Fusion.
Cada fragmento guarda su ubicación ("p. 12" en PDF, "sección «...»" en Markdown, "hoja X" en Excel).
Lo que está en conocimiento/confidencial/ o tiene "CONFIDENCIAL" en el nombre queda marcado.

Uso:
  python -m arkcrow.conocimiento indexar
  python -m arkcrow.conocimiento buscar "espesor del mortero de nivelación"
"""
from __future__ import annotations

import re
import sqlite3
import subprocess
import sys
import unicodedata
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
INDICE = RAIZ / "datos" / "indice.sqlite"
FUENTES = [RAIZ / "conocimiento", RAIZ / "memoria"]
EXTENSIONES = {".pdf", ".md", ".txt", ".docx", ".xlsx", ".csv"}
TAM, SOLAPE = 1500, 200

STOP = set("""a al algo como con cual cuales cuando de del desde donde el ella ellas ellos en entre era es esa ese eso esta
este esto estos fue ha hay la las le les lo los mas me mi mis muy no nos o para pero por que quien se segun ser si sin
sobre son su sus tambien te tiene tu un una uno unos y ya cual cuanto cuanta cuantos cuantas debe deben puede usa usar
dejo dejar hace hacer tengo tenemos dime decir explica explicame favor""".split())


def norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()
    return t


# ----------------------------------------------------------------- extracción
def _pdf(ruta: Path):
    try:
        from pypdf import PdfReader
        lector = PdfReader(str(ruta))
        for i, pag in enumerate(lector.pages, start=1):
            yield f"p. {i}", pag.extract_text() or ""
    except Exception:  # noqa: BLE001  (PDF raro: se intenta con pdftotext)
        out = subprocess.run(["pdftotext", "-layout", str(ruta), "-"], capture_output=True, text=True).stdout
        for i, pag in enumerate(out.split("\f"), start=1):
            yield f"p. {i}", pag


def _md(ruta: Path):
    seccion, buf = "inicio", []
    for linea in ruta.read_text(encoding="utf-8", errors="ignore").splitlines():
        m = re.match(r"^#{1,4}\s+(.*)", linea)
        if m:
            if "".join(buf).strip():
                yield f"sección «{seccion}»", "\n".join(buf)
            seccion, buf = m.group(1).strip(), [linea]
        else:
            buf.append(linea)
    if "".join(buf).strip():
        yield f"sección «{seccion}»", "\n".join(buf)


def _docx(ruta: Path):
    with zipfile.ZipFile(ruta) as z:
        xml = z.read("word/document.xml").decode("utf-8", "ignore")
    parrafos = [re.sub(r"<[^>]+>", "", p) for p in re.findall(r"<w:p[ >].*?</w:p>", xml, re.S)]
    parrafos = [p for p in parrafos if p.strip()]
    for i in range(0, len(parrafos), 8):
        yield f"párr. {i + 1}-{min(i + 8, len(parrafos))}", "\n".join(parrafos[i:i + 8])


def _xlsx(ruta: Path):
    from openpyxl import load_workbook
    wb = load_workbook(ruta, data_only=True, read_only=True)
    for ws in wb:
        filas = [" | ".join(str(v) for v in f if v not in (None, "")) for f in ws.iter_rows(values_only=True)]
        yield f"hoja «{ws.title}»", "\n".join(f for f in filas if f)


def extraer(ruta: Path):
    ext = ruta.suffix.lower()
    if ext == ".pdf":
        yield from _pdf(ruta)
    elif ext == ".md":
        yield from _md(ruta)
    elif ext in (".txt", ".csv"):
        yield "texto", ruta.read_text(encoding="utf-8", errors="ignore")
    elif ext == ".docx":
        yield from _docx(ruta)
    elif ext == ".xlsx":
        yield from _xlsx(ruta)


def trocear(texto: str) -> list[str]:
    texto = re.sub(r"[ \t]+", " ", texto).strip()
    if len(texto) <= TAM:
        return [texto] if texto else []
    partes, i = [], 0
    while i < len(texto):
        fin = min(i + TAM, len(texto))
        if fin < len(texto):
            corte = max(texto.rfind("\n", i + TAM // 2, fin), texto.rfind(". ", i + TAM // 2, fin))
            fin = corte + 1 if corte > 0 else fin
        partes.append(texto[i:fin].strip())
        if fin >= len(texto):
            break
        i = max(fin - SOLAPE, i + 1)
    return [p for p in partes if p]


def es_confidencial(ruta: Path) -> bool:
    rel = ruta.relative_to(RAIZ).as_posix().lower()
    return "confidencial" in rel


# --------------------------------------------------------------------- índice
def conectar(ruta: Path = INDICE) -> sqlite3.Connection:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(ruta)
    con.executescript("""
        CREATE TABLE IF NOT EXISTS meta (clave TEXT PRIMARY KEY, valor TEXT);
        CREATE TABLE IF NOT EXISTS docs (ruta TEXT PRIMARY KEY, mtime REAL, tam INTEGER, n INTEGER, confidencial INTEGER);
        CREATE TABLE IF NOT EXISTS chunks (id INTEGER PRIMARY KEY, ruta TEXT, ubicacion TEXT, texto TEXT,
                                           confidencial INTEGER, vec BLOB);
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(texto, tokenize='unicode61 remove_diacritics 2');
    """)
    return con


def _archivos():
    for base in FUENTES:
        for f in sorted(base.rglob("*")):
            if f.is_file() and f.suffix.lower() in EXTENSIONES and not f.name.startswith(("_", "~$", ".")) and f.name != "activa.txt":
                yield f


def exportar_precios() -> Path:
    """Copia la base de precios a Markdown para que el asistente la pueda consultar y citar."""
    from . import db
    db.inicializar()
    dest = RAIZ / "conocimiento" / "precios" / "precios_base.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    nombres = {"MO": "Mano de obra (jornal)", "EQ": "Equipos (tarifa de alquiler)", "MAT": "Materiales",
               "TR": "Transporte"}
    L = ["# Base de precios ARKCROW (exportada de datos/arkcrow.sqlite)", "",
         "Estado: precios de la prueba técnica, oct-2026, POR ACTUALIZAR. Los marcados SUPUESTO son estimados.", ""]
    ins = db.insumos()
    for tipo, titulo in nombres.items():
        L += [f"## {titulo}", "", "| Código | Descripción | Unidad | Precio | Fuente |", "|---|---|---|---:|---|"]
        for c, r in ins.items():
            if r["tipo"] == tipo:
                precio = f"{r['precio']:,.0f}".replace(",", ".")
                L.append(f"| {c} | {r['descripcion']} | {r['unidad']} | {precio} | {r['fuente']} |")
        L.append("")
    nuevo = "\n".join(L)
    if not dest.exists() or dest.read_text(encoding="utf-8") != nuevo:
        dest.write_text(nuevo, encoding="utf-8")
    return dest


def indexar(con: sqlite3.Connection | None = None, embeddings: bool = True, verbose: bool = True) -> dict:
    from . import llm
    con = con or conectar()
    exportar_precios()
    vistos, nuevos, borrados = set(), 0, 0
    for f in _archivos():
        rel = f.relative_to(RAIZ).as_posix()
        vistos.add(rel)
        st = f.stat()
        fila = con.execute("SELECT mtime, tam FROM docs WHERE ruta=?", (rel,)).fetchone()
        if fila and fila[0] == st.st_mtime and fila[1] == st.st_size:
            continue
        _borrar(con, rel)
        conf = int(es_confidencial(f))
        n = 0
        try:
            for ubic, texto in extraer(f):
                for trozo in trocear(texto):
                    cur = con.execute("INSERT INTO chunks (ruta, ubicacion, texto, confidencial) VALUES (?,?,?,?)",
                                      (rel, ubic, trozo, conf))
                    con.execute("INSERT INTO chunks_fts (rowid, texto) VALUES (?,?)", (cur.lastrowid, f"{rel} {ubic}\n{trozo}"))
                    n += 1
        except Exception as e:  # noqa: BLE001
            if verbose:
                print(f"  ! No se pudo leer {rel}: {e}")
        con.execute("INSERT OR REPLACE INTO docs VALUES (?,?,?,?,?)", (rel, st.st_mtime, st.st_size, n, conf))
        nuevos += 1
        if verbose:
            print(f"  + {rel}: {n} fragmentos{' (CONFIDENCIAL)' if conf else ''}")
    for (rel,) in con.execute("SELECT ruta FROM docs").fetchall():
        if rel not in vistos:
            _borrar(con, rel)
            con.execute("DELETE FROM docs WHERE ruta=?", (rel,))
            borrados += 1
    con.commit()
    n_vec = _embeber_pendientes(con, llm, verbose) if embeddings else 0
    total = con.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    return {"documentos_actualizados": nuevos, "documentos_borrados": borrados, "fragmentos": total,
            "vectores_nuevos": n_vec}


def _borrar(con, rel):
    ids = [r[0] for r in con.execute("SELECT id FROM chunks WHERE ruta=?", (rel,))]
    con.executemany("DELETE FROM chunks_fts WHERE rowid=?", [(i,) for i in ids])
    con.execute("DELETE FROM chunks WHERE ruta=?", (rel,))


def _embeber_pendientes(con, llm, verbose) -> int:
    import numpy as np
    if not llm.embed_disponible():
        if verbose:
            print(f"  (Modelo de embeddings '{llm.EMBED}' no disponible: solo búsqueda por palabras.)")
        return 0
    previo = con.execute("SELECT valor FROM meta WHERE clave='embed'").fetchone()
    if previo and previo[0] != llm.EMBED:
        con.execute("UPDATE chunks SET vec=NULL")
    con.execute("INSERT OR REPLACE INTO meta VALUES ('embed', ?)", (llm.EMBED,))
    pend = con.execute("SELECT id, ruta, ubicacion, texto FROM chunks WHERE vec IS NULL").fetchall()
    for i in range(0, len(pend), 16):
        lote = pend[i:i + 16]
        vecs = llm.embeber([f"{r[1]} {r[2]}\n{r[3]}" for r in lote])
        for (cid, *_), v in zip(lote, vecs):
            a = np.asarray(v, dtype=np.float32)
            a /= (np.linalg.norm(a) or 1.0)
            con.execute("UPDATE chunks SET vec=? WHERE id=?", (a.tobytes(), cid))
        con.commit()
        if verbose:
            print(f"  embeddings {min(i + 16, len(pend))}/{len(pend)}")
    return len(pend)


# --------------------------------------------------------------------- búsqueda
def _consulta_fts(pregunta: str) -> str:
    toks = [t for t in re.findall(r"[a-z0-9]+", norm(pregunta)) if t not in STOP and len(t) > 1]
    terminos = []
    for t in dict.fromkeys(toks):
        raiz = re.sub(r"(ciones|cion|es|s)$", "", t) if len(t) > 5 else t
        terminos.append(f"{raiz}*" if len(raiz) >= 4 else f'"{t}"')
    return " OR ".join(terminos)


def buscar(pregunta: str, k: int = 6, con: sqlite3.Connection | None = None,
           incluir_confidencial: bool = True) -> list[dict]:
    from . import llm
    con = con or conectar()
    rangos: dict[int, float] = {}
    q = _consulta_fts(pregunta)
    if q:
        filas = con.execute("SELECT rowid FROM chunks_fts WHERE chunks_fts MATCH ? ORDER BY bm25(chunks_fts) LIMIT 30",
                            (q,)).fetchall()
        for pos, (cid,) in enumerate(filas):
            rangos[cid] = rangos.get(cid, 0) + 1 / (60 + pos)
    hay_vec = con.execute("SELECT 1 FROM chunks WHERE vec IS NOT NULL LIMIT 1").fetchone()
    if hay_vec and llm.embed_disponible():
        import numpy as np
        qv = np.asarray(llm.embeber([pregunta])[0], dtype=np.float32)
        qv /= (np.linalg.norm(qv) or 1.0)
        ids, mats = [], []
        for cid, blob in con.execute("SELECT id, vec FROM chunks WHERE vec IS NOT NULL"):
            ids.append(cid)
            mats.append(np.frombuffer(blob, dtype=np.float32))
        sims = np.vstack(mats) @ qv
        for pos, j in enumerate(np.argsort(-sims)[:30]):
            rangos[ids[j]] = rangos.get(ids[j], 0) + 1 / (60 + pos)
    # refuerzo: coincidencia de la pregunta con el nombre del archivo o el título de la sección
    raices = [t.rstrip("*").strip('"') for t in q.split(" OR ")] if q else []
    for cid in list(rangos):
        ruta, ubic = con.execute("SELECT ruta, ubicacion FROM chunks WHERE id=?", (cid,)).fetchone()
        titulo = norm(f"{Path(ruta).stem} {ubic}")
        aciertos = sum(1 for r in raices if r and r in titulo)
        rangos[cid] += aciertos * 0.004
    mejores = sorted(rangos.items(), key=lambda x: -x[1])
    out = []
    for cid, puntaje in mejores:
        r = con.execute("SELECT ruta, ubicacion, texto, confidencial FROM chunks WHERE id=?", (cid,)).fetchone()
        if r[3] and not incluir_confidencial:
            continue
        out.append({"id": cid, "ruta": r[0], "ubicacion": r[1], "texto": r[2], "confidencial": bool(r[3]),
                    "puntaje": round(puntaje, 4), "cita": f"[{r[0]}, {r[1]}]"})
        if len(out) >= k:
            break
    return out


def main(argv=None):
    argv = argv or sys.argv[1:]
    if not argv or argv[0] not in ("indexar", "buscar"):
        sys.exit(__doc__)
    if argv[0] == "indexar":
        print(indexar())
    else:
        for r in buscar(" ".join(argv[1:])):
            print(f"\n{r['cita']}  (puntaje {r['puntaje']}{', CONFIDENCIAL' if r['confidencial'] else ''})")
            print("   " + r["texto"][:300].replace("\n", " ") + ("..." if len(r["texto"]) > 300 else ""))


if __name__ == "__main__":
    main()
