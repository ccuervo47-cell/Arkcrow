"""Respaldos automáticos diarios de memoria/, proyectos/ y las bases de datos.

Destino configurable en .env:  ARKCROW_RESPALDOS=E:\\RespaldosArkcrow   (USB, OneDrive de la empresa, etc.)
Por defecto: ArkcrowObra/respaldos/. Se conservan los últimos ARKCROW_RESPALDOS_MAX (30) archivos.
Las bases SQLite se copian con la API de respaldo de SQLite (copia consistente aunque estén abiertas).
Cada respaldo se VERIFICA (zip íntegro + integrity_check de las bases) antes de darlo por bueno.

Uso:
  python -m arkcrow.respaldo hacer            (siempre)
  python -m arkcrow.respaldo si-toca          (solo si el último tiene más de 24 h; lo llama iniciar)
  python -m arkcrow.respaldo listar
  python -m arkcrow.respaldo verificar <zip>
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import closing
import sys
import tempfile
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

from . import llm  # noqa: F401  (carga .env)

RAIZ = Path(__file__).resolve().parents[2]
CARPETAS = ["memoria", "proyectos"]
BASES = ["datos/arkcrow.sqlite", "datos/indice.sqlite"]
EXTRAS = ["datos/cola.json"]
EXCLUIR = ("__pycache__", ".tmp", "~$")


def destino() -> Path:
    d = Path(os.environ.get("ARKCROW_RESPALDOS") or RAIZ / "respaldos")
    d.mkdir(parents=True, exist_ok=True)
    return d


def listar() -> list[Path]:
    return sorted(destino().glob("arkcrow_respaldo_*.zip"))


def hacer() -> Path:
    marca = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    final = destino() / f"arkcrow_respaldo_{marca}.zip"
    tmp_zip = final.with_suffix(".zip.tmp")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp, \
            zipfile.ZipFile(tmp_zip, "w", zipfile.ZIP_DEFLATED) as z:
        for carpeta in CARPETAS:
            for f in sorted((RAIZ / carpeta).rglob("*")):
                if f.is_file() and not any(x in str(f) for x in EXCLUIR):
                    z.write(f, f.relative_to(RAIZ).as_posix())
        for rel in BASES:
            origen = RAIZ / rel
            if origen.exists():
                copia = Path(tmp) / origen.name
                # cerrar SIEMPRE las conexiones: en Windows un archivo abierto no se puede borrar
                with closing(sqlite3.connect(origen)) as src, closing(sqlite3.connect(copia)) as dst:
                    src.backup(dst)
                z.write(copia, rel)
        for rel in EXTRAS:
            if (RAIZ / rel).exists():
                z.write(RAIZ / rel, rel)
    problemas = verificar(tmp_zip)
    if problemas:
        tmp_zip.unlink(missing_ok=True)
        raise RuntimeError("El respaldo no pasó la verificación: " + "; ".join(problemas))
    tmp_zip.rename(final)
    _rotar()
    return final


def verificar(zip_path: Path) -> list[str]:
    problemas = []
    with zipfile.ZipFile(zip_path) as z:
        malo = z.testzip()
        if malo:
            problemas.append(f"archivo dañado en el zip: {malo}")
        nombres = set(z.namelist())
        if not any(n.startswith("memoria/") for n in nombres):
            problemas.append("no contiene memoria/")
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            for rel in BASES:
                if rel in nombres:
                    p = Path(z.extract(rel, tmp))
                    with closing(sqlite3.connect(p)) as c:
                        if c.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                            problemas.append(f"base dañada: {rel}")
    return problemas


def _rotar():
    maximo = int(os.environ.get("ARKCROW_RESPALDOS_MAX", "30"))
    viejos = listar()[:-maximo] if maximo > 0 else []
    for f in viejos:       # solo borra respaldos propios antiguos (nombre arkcrow_respaldo_*.zip)
        f.unlink()


def ultimo() -> datetime | None:
    l = listar()
    return datetime.fromtimestamp(l[-1].stat().st_mtime) if l else None


def si_toca(horas: int = 24) -> Path | None:
    u = ultimo()
    if u is None or datetime.now() - u > timedelta(hours=horas):
        return hacer()
    return None


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "si-toca"
    if cmd == "hacer":
        print(f"Respaldo verificado: {hacer()}")
    elif cmd == "si-toca":
        try:
            r = si_toca()
        except Exception as e:  # noqa: BLE001  (un respaldo fallido no debe impedir abrir el programa)
            print(f"⚠ No se pudo hacer el respaldo diario: {e}")
            sys.exit(0)
        print(f"Respaldo verificado: {r}" if r else f"Respaldo al día (último: {ultimo():%d/%m/%Y %H:%M}).")
    elif cmd == "listar":
        for f in listar():
            print(f"{f.name}  {f.stat().st_size // 1024} KB")
    elif cmd == "verificar":
        p = verificar(Path(sys.argv[2]))
        print("OK" if not p else "\n".join(p))
    else:
        sys.exit(__doc__)
