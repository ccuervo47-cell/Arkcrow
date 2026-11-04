"""Elige el modelo local según el hardware medido (lo usan instalar.ps1 e instalar.sh).

Uso: python herramientas/elegir_modelo.py --ram 16 --vram 0 --disco 120 [--json]

Criterio (modelos Qwen 2.5 cuantizados Q4 en Ollama, buen español y uso de herramientas):
- El modelo debe caber en RAM dejando ~6 GB para Windows, Office y el navegador; con GPU NVIDIA, en la VRAM.
- Se instala además un modelo pequeño de respaldo (equipos sin memoria libre o respuestas rápidas)
  y el modelo de embeddings bge-m3 (multilingüe, bueno en español).
"""
from __future__ import annotations

import argparse
import json

# (nombre ollama, tamaño de descarga GB, RAM mínima total GB)
MODELOS = {
    "qwen2.5:14b": (9.0, 32),
    "qwen2.5:7b": (4.7, 16),
    "qwen2.5:3b": (1.9, 8),
    "qwen2.5:1.5b": (1.0, 0),
}
EMBED = ("bge-m3", 1.2)
WHISPER_GB = 0.5


def elegir(ram_gb: float, vram_gb: float = 0.0, disco_gb: float = 999.0) -> dict:
    if vram_gb >= 12 or ram_gb >= 30:      # "32 GB" se reporta como ~31,7
        principal, respaldo = "qwen2.5:14b", "qwen2.5:7b"
    elif vram_gb >= 6 or ram_gb >= 15:    # "16 GB" se reporta como ~15,7
        principal, respaldo = "qwen2.5:7b", "qwen2.5:3b"
    elif ram_gb >= 7:                      # "8 GB" se reporta como ~7,8
        principal, respaldo = "qwen2.5:3b", "qwen2.5:1.5b"
    else:
        principal, respaldo = "qwen2.5:1.5b", None
    total = MODELOS[principal][0] + (MODELOS[respaldo][0] if respaldo else 0) + EMBED[1] + WHISPER_GB
    avisos = []
    if disco_gb < total + 5:
        avisos.append(f"Espacio libre insuficiente: se necesitan ~{total + 5:.0f} GB (modelos + margen) y hay {disco_gb:.0f} GB.")
        while disco_gb < total + 5 and principal != "qwen2.5:1.5b":
            principal, respaldo = (respaldo, "qwen2.5:1.5b" if respaldo != "qwen2.5:1.5b" else None)
            total = MODELOS[principal][0] + (MODELOS[respaldo][0] if respaldo else 0) + EMBED[1] + WHISPER_GB
        avisos.append(f"Se reduce el modelo a {principal} por espacio en disco.")
    if ram_gb < 8:
        avisos.append("Con menos de 8 GB de RAM el asistente será lento; cierre otros programas al usarlo.")
    razon = (f"RAM {ram_gb:.0f} GB" + (f", GPU NVIDIA {vram_gb:.0f} GB" if vram_gb else ", sin GPU NVIDIA") +
             f" -> {principal}" + (f" (respaldo {respaldo})" if respaldo else ""))
    return {"principal": principal, "respaldo": respaldo or principal, "embed": EMBED[0],
            "descarga_gb": round(total, 1), "razon": razon, "avisos": avisos}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ram", type=float, required=True)
    ap.add_argument("--vram", type=float, default=0)
    ap.add_argument("--disco", type=float, default=999)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    r = elegir(a.ram, a.vram, a.disco)
    print(json.dumps(r, ensure_ascii=False) if a.json else
          f"{r['razon']}\nDescarga total aprox.: {r['descarga_gb']} GB" + "".join(f"\n! {x}" for x in r["avisos"]))
