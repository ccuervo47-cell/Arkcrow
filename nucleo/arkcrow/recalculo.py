"""Recalcula las fórmulas de un .xlsx para poder leer los valores (revisor de calidad / auditor).

openpyxl escribe fórmulas sin valores calculados. Para auditar se necesita un motor de cálculo:
  1. LibreOffice (soffice) en modo invisible  -> Linux, Mac o Windows con LibreOffice instalado
  2. Microsoft Excel por COM (pywin32)        -> Windows con Office
Se trabaja sobre una COPIA; el archivo original no se modifica salvo que se pida `en_sitio=True`.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RUTAS_SOFFICE = [
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
]


class SinMotorDeCalculo(RuntimeError):
    pass


def _soffice() -> str | None:
    for nombre in ("soffice", "libreoffice"):
        ruta = shutil.which(nombre)
        if ruta:
            return ruta
    return next((r for r in RUTAS_SOFFICE if Path(r).exists()), None)


def _con_libreoffice(origen: Path, destino: Path, timeout: int) -> None:
    exe = _soffice()
    if not exe:
        raise SinMotorDeCalculo("LibreOffice no encontrado")
    with tempfile.TemporaryDirectory(prefix="arkcrow-lo-") as tmp:
        perfil = Path(tmp, "perfil").as_uri()
        salida = Path(tmp, "out")
        salida.mkdir()
        cmd = [exe, f"-env:UserInstallation={perfil}", "--headless", "--norestore",
               "--convert-to", "xlsx:Calc MS Excel 2007 XML", "--outdir", str(salida), str(origen)]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        generado = salida / (origen.stem + ".xlsx")
        if not generado.exists():
            raise RuntimeError(f"LibreOffice no generó el archivo recalculado: {res.stderr or res.stdout}")
        shutil.move(str(generado), destino)


def _con_excel(origen: Path, destino: Path) -> None:
    try:
        import win32com.client  # type: ignore
    except ImportError as e:
        raise SinMotorDeCalculo("pywin32 no instalado") from e
    shutil.copy(origen, destino)
    excel = win32com.client.DispatchEx("Excel.Application")
    excel.Visible = False
    excel.DisplayAlerts = False
    try:
        libro = excel.Workbooks.Open(str(destino.resolve()))
        excel.CalculateFull()
        libro.Save()
        libro.Close(False)
    finally:
        excel.Quit()


def recalcular(archivo: str | Path, destino: str | Path | None = None, timeout: int = 120) -> Path:
    """Devuelve la ruta de una copia recalculada (o del mismo archivo si destino == archivo)."""
    archivo = Path(archivo).resolve()
    if destino is None:
        destino = Path(tempfile.mkdtemp(prefix="arkcrow-recalc-")) / archivo.name
    destino = Path(destino)
    errores = []
    motores = [lambda: _con_libreoffice(archivo, destino, timeout)]
    if os.name == "nt":
        motores.insert(0, lambda: _con_excel(archivo, destino))  # en Windows se prefiere Excel si existe
    for motor in motores:
        try:
            motor()
            return destino
        except SinMotorDeCalculo as e:
            errores.append(str(e))
    raise SinMotorDeCalculo("No hay motor de cálculo disponible (" + "; ".join(errores) +
                            "). Instale LibreOffice (portable sirve) o use Excel con pywin32.")


if __name__ == "__main__":
    print(recalcular(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None))
