#!/usr/bin/env bash
# Start a local llama.cpp OpenAI-compatible server for AI match summaries.
# Requires a built llama.cpp binary (llama-server) and a GGUF model on disk.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "${SCRIPT_DIR}/lib.sh"

PORT="${LLAMACPP_PORT:-8080}"
HOST="${LLAMACPP_HOST:-127.0.0.1}"
MODEL_PATH="${LLAMACPP_MODEL_PATH:-}"
MODEL_ID="${LLAMACPP_MODEL:-local}"

# Sensible dev defaults for short one-sentence summaries (override via env).
FLASH_ATTN="${LLAMACPP_FLASH_ATTN:-on}"       # on | off | auto
CTX_SIZE="${LLAMACPP_CTX_SIZE:-2048}"         # blurbs need little context
N_GPU_LAYERS="${LLAMACPP_NGL:-99}"            # offload all layers when a GPU backend exists

usage() {
  cat <<EOF
Usage: $(basename "$0") [--help]

Start llama-server for local HeadStart AI summaries (Phase 12 dev helper).

Environment:
  LLAMACPP_MODEL_PATH   Path to a .gguf model file (required to start)
  LLAMACPP_PORT         Listen port (default: 8080)
  LLAMACPP_HOST         Bind address (default: 127.0.0.1)
  LLAMACPP_MODEL        Model id sent in API requests (default: local)
  LLAMACPP_FLASH_ATTN   Flash Attention: on | off | auto (default: on)
  LLAMACPP_CTX_SIZE     Context window in tokens (default: 2048)
  LLAMACPP_NGL          GPU layers to offload; 0 = CPU only (default: 99)

After the server is up, point the app at it:
  SUMMARY_PROVIDER=llamacpp
  LLAMACPP_BASE_URL=http://${HOST}:${PORT}/v1
  LLAMACPP_MODEL=${MODEL_ID}

Install llama.cpp: https://github.com/ggerganov/llama.cpp#build
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

if ! have llama-server; then
  die "llama-server not found on PATH. Build llama.cpp and install llama-server, or add it to PATH."
fi

if [[ -z "${MODEL_PATH}" ]]; then
  cat >&2 <<EOF
ERROR: Set LLAMACPP_MODEL_PATH to a .gguf model file before starting.

Example:
  export LLAMACPP_MODEL_PATH=/path/to/model.gguf
  make llamacpp

Then in another terminal (or your .env):
  SUMMARY_PROVIDER=llamacpp
  LLAMACPP_BASE_URL=http://${HOST}:${PORT}/v1
EOF
  exit 1
fi

if [[ ! -f "${MODEL_PATH}" ]]; then
  die "Model file not found: ${MODEL_PATH}"
fi

case "${FLASH_ATTN}" in
  on|off|auto) ;;
  *)
    die "LLAMACPP_FLASH_ATTN must be on, off, or auto (got: ${FLASH_ATTN})"
    ;;
esac

log "Starting llama-server on http://${HOST}:${PORT}/v1"
log "Model: ${MODEL_PATH} (id=${MODEL_ID})"
log "Flags: flash-attn=${FLASH_ATTN} ctx=${CTX_SIZE} ngl=${N_GPU_LAYERS}"
warn "Keep this terminal open; use Ctrl+C to stop."

exec llama-server \
  --model "${MODEL_PATH}" \
  --host "${HOST}" \
  --port "${PORT}" \
  --flash-attn "${FLASH_ATTN}" \
  --ctx-size "${CTX_SIZE}" \
  --n-gpu-layers "${N_GPU_LAYERS}"
