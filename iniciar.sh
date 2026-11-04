#!/usr/bin/env bash
# ARKCROW OBRA - arranque (Linux / Mac). Abre el chat en el navegador.
RAIZ="$(cd "$(dirname "$0")" && pwd)"; cd "$RAIZ"
export PYTHONPATH="$RAIZ/nucleo" PYTHONUTF8=1 OLLAMA_MODELS="$RAIZ/modelos/ollama"
PY=.venv/bin/python; [[ -x $PY ]] || { echo "Primero ejecute ./instalar.sh"; exit 1; }
command -v ollama >/dev/null && { pgrep -x ollama >/dev/null || (nohup ollama serve >/dev/null 2>&1 &); }
$PY -m arkcrow.respaldo si-toca
if [[ "${1:-}" == "--consola" ]]; then exec $PY -m arkcrow.chat; else exec $PY -m arkcrow.web; fi
