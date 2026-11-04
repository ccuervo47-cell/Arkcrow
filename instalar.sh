#!/usr/bin/env bash
# ARKCROW OBRA - Instalador para Linux / Mac (nivel de usuario).
# Uso: ./instalar.sh            instala (pide confirmación antes de cada descarga grande)
#      ./instalar.sh --simular  solo muestra el plan, no descarga ni instala nada
set -euo pipefail
RAIZ="$(cd "$(dirname "$0")" && pwd)"
cd "$RAIZ"
SIMULAR=0; [[ "${1:-}" == "--simular" ]] && SIMULAR=1
export PYTHONPATH="$RAIZ/nucleo" PYTHONUTF8=1 OLLAMA_MODELS="$RAIZ/modelos/ollama"
ok(){ echo "  [OK] $*"; }; aviso(){ echo "  [!] $*"; }
confirmar(){ [[ $SIMULAR == 1 ]] && { echo "  (simulación) $1 -> NO"; return 1; }; read -r -p "  $1 (s/n) " r; [[ "$r" =~ ^[sSyY] ]]; }

echo "=== 1. Revisando el equipo ==="
if [[ "$(uname)" == "Darwin" ]]; then RAM=$(( $(sysctl -n hw.memsize) / 1073741824 )); else RAM=$(awk '/MemTotal/{printf "%d", $2/1048576}' /proc/meminfo); fi
VRAM=0; command -v nvidia-smi >/dev/null && VRAM=$(( $(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | head -1) / 1024 )) || true
DISCO=$(df -Pk "$RAIZ" | awk 'NR==2{printf "%d", $4/1048576}')
ok "Sistema: $(uname -sr) · RAM ${RAM} GB · GPU NVIDIA ${VRAM} GB · libre ${DISCO} GB"

echo "=== 2. Python ==="
PY=""; for c in python3.12 python3.11 python3 python; do
  if command -v $c >/dev/null && $c -c 'import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)'; then PY=$c; break; fi; done
[[ -z "$PY" ]] && { echo "  [X] Se necesita Python 3.10+ (instálelo con el gestor de paquetes o desde python.org)."; exit 1; }
ok "Python: $($PY --version)"

echo "=== 3. Modelo según el hardware ==="
PLAN=$($PY herramientas/elegir_modelo.py --ram "$RAM" --vram "$VRAM" --disco "$DISCO" --json)
$PY herramientas/elegir_modelo.py --ram "$RAM" --vram "$VRAM" --disco "$DISCO" | sed 's/^/  /'
campo(){ $PY -c "import json,sys; print(json.loads(sys.argv[1])[sys.argv[2]])" "$PLAN" "$1"; }
PRINCIPAL=$(campo principal); RESPALDO=$(campo respaldo); EMBED=$(campo embed)

echo "=== 4. Librerías (entorno .venv) ==="
if [[ $SIMULAR == 1 ]]; then echo "  (simulación) python -m venv .venv && pip install -r requirements.txt"; VPY=$PY
else
  [[ -x .venv/bin/python ]] || $PY -m venv .venv
  VPY=.venv/bin/python
  $VPY -m pip install --quiet --upgrade pip && $VPY -m pip install --quiet -r requirements.txt
  ok "Librerías instaladas"
  echo "$RAIZ/nucleo" > "$($VPY -c 'import site;print(site.getsitepackages()[0])')/arkcrow.pth"
fi

echo "=== 5. Ollama y modelos ==="
mkdir -p "$OLLAMA_MODELS"
if ! command -v ollama >/dev/null; then
  aviso "Ollama no está instalado. En Linux su instalador oficial requiere sudo:"
  echo "      curl -fsSL https://ollama.com/install.sh | sh      (Mac: descargue la app desde ollama.com)"
  aviso "Sin Ollama, ARKCROW funciona en modo 'solo búsqueda'."
else
  pgrep -x ollama >/dev/null || (nohup ollama serve >/dev/null 2>&1 &); sleep 3
  if confirmar "Descargar $PRINCIPAL, $RESPALDO y $EMBED (≈ $(campo descarga_gb) GB)?"; then
    for m in $(printf "%s\n" "$PRINCIPAL" "$RESPALDO" "$EMBED" | awk '!v[$0]++'); do ollama pull "$m" && ok "$m listo"; done
  fi
fi
if [[ ! -d modelos/whisper-small ]] && confirmar "Descargar el modelo de voz whisper-small (≈ 0,5 GB)?"; then
  $VPY -c "from arkcrow.voz import descargar_modelo; descargar_modelo()" && ok "Voz lista"
fi

echo "=== 6. Configuración, índice y pruebas ==="
if [[ $SIMULAR == 1 ]]; then
  echo "  (simulación) .env -> ARKCROW_MODELO=$PRINCIPAL ARKCROW_MODELO_RESP=$RESPALDO ARKCROW_EMBED=$EMBED"
else
  $VPY herramientas/configurar_env.py "ARKCROW_MODELO=$PRINCIPAL" "ARKCROW_MODELO_RESP=$RESPALDO" "ARKCROW_EMBED=$EMBED" \
       "ARKCROW_WHISPER=$RAIZ/modelos/whisper-small"
  $VPY -m arkcrow.db && $VPY -m arkcrow.conocimiento indexar | tail -1
  $VPY -m unittest discover tests 2>&1 | tail -3
  $VPY -m arkcrow.respaldo hacer
  chmod +x iniciar.sh
fi
echo "=== LISTO === Abra con ./iniciar.sh. Prueba sin internet: desconecte la red y pregunte '¿Qué AIU usa la empresa?'."
