"""Genera fotos de prueba (sintéticas) con EXIF de fecha y GPS para probar el registro fotográfico."""
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw


def _rac(x):
    g = int(x); m = int((x - g) * 60); s = round(((x - g) * 60 - m) * 60, 2)
    return (float(g), float(m), float(s))


def crear(carpeta: Path, nombre: str, fecha: datetime, lat=None, lon=None, color=(150, 120, 90)):
    carpeta.mkdir(parents=True, exist_ok=True)
    im = Image.new("RGB", (800, 600), color)
    d = ImageDraw.Draw(im)
    d.rectangle([100, 100, 700, 500], outline=(255, 255, 255), width=6)
    d.text((120, 120), f"FOTO DE PRUEBA {nombre}", fill=(255, 255, 255))
    exif = im.getexif()
    exif[0x0132] = fecha.strftime("%Y:%m:%d %H:%M:%S")
    exif.get_ifd(0x8769)[0x9003] = fecha.strftime("%Y:%m:%d %H:%M:%S")
    if lat is not None:
        gps = exif.get_ifd(0x8825)
        gps[1] = "N" if lat >= 0 else "S"; gps[2] = _rac(abs(lat))
        gps[3] = "E" if lon >= 0 else "W"; gps[4] = _rac(abs(lon))
    ruta = carpeta / nombre
    im.save(ruta, "JPEG", exif=exif)
    return ruta
