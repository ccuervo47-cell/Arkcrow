"""Dictado de voz OFFLINE con Whisper local (faster-whisper, CPU).

El modelo se descarga UNA vez con internet (el instalador lo deja en modelos/whisper-small) y luego
funciona sin conexión. Variable ARKCROW_WHISPER = ruta o nombre del modelo (por defecto modelos/whisper-small).
"""
from __future__ import annotations

import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]


class VozNoDisponible(RuntimeError):
    pass


def ruta_modelo() -> str:
    return os.environ.get("ARKCROW_WHISPER", str(RAIZ / "modelos" / "whisper-small"))


def transcribir(audio: str | Path, idioma: str = "es") -> str:
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        raise VozNoDisponible("Falta faster-whisper (pip install faster-whisper).") from e
    modelo = ruta_modelo()
    if not Path(modelo).exists():
        raise VozNoDisponible(
            f"No está el modelo de voz en {modelo}. Con internet ejecute el instalador (descarga whisper 'small', "
            "≈ 480 MB) o escriba la bitácora como texto.")
    m = WhisperModel(modelo, device="cpu", compute_type="int8")
    segmentos, _ = m.transcribe(str(audio), language=idioma, vad_filter=True,
                                initial_prompt="Bitácora de obra. Clima: Personal: Equipos: Actividades: Novedades:")
    return "\n".join(s.text.strip() for s in segmentos)


def descargar_modelo(destino: str | Path | None = None, tamano: str = "small") -> Path:
    """Se usa desde el instalador, con internet."""
    from faster_whisper.utils import download_model
    destino = Path(destino or ruta_modelo())
    destino.mkdir(parents=True, exist_ok=True)
    download_model(tamano, output_dir=str(destino))
    return destino
