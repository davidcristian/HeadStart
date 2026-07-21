#!/usr/bin/env bash
# Shared helpers for HeadStart scripts. Source this; do not execute directly.

set -euo pipefail

# Repo root = parent of the scripts/ directory.
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="${REPO_ROOT}/backend"
FRONTEND_DIR="${REPO_ROOT}/frontend"
VENV_DIR="${BACKEND_DIR}/.venv"

# ---- logging ----
if [[ -t 1 ]]; then
  _C_BLUE="\033[34m"; _C_GREEN="\033[32m"; _C_YELLOW="\033[33m"
  _C_RED="\033[31m"; _C_RESET="\033[0m"
else
  _C_BLUE=""; _C_GREEN=""; _C_YELLOW=""; _C_RED=""; _C_RESET=""
fi

log()  { echo -e "${_C_BLUE}==>${_C_RESET} $*"; }
ok()   { echo -e "${_C_GREEN}OK${_C_RESET}  $*"; }
warn() { echo -e "${_C_YELLOW}WARN${_C_RESET} $*" >&2; }
die()  { echo -e "${_C_RED}ERROR${_C_RESET} $*" >&2; exit 1; }

have() { command -v "$1" >/dev/null 2>&1; }

# Path to the python interpreter to use for backend commands.
# Prefers the project venv; falls back to python3 on PATH.
py_bin() {
  if [[ -x "${VENV_DIR}/bin/python" ]]; then
    echo "${VENV_DIR}/bin/python"
  elif have python3; then
    echo "python3"
  else
    die "No python interpreter found. Run 'just setup' first."
  fi
}

# Frontend deps must exist before any frontend gate runs. A skipped gate
# reads as green, so missing node_modules is a hard failure, not a warning.
require_frontend_deps() {
  [[ -d "${FRONTEND_DIR}/node_modules" ]] \
    || die "frontend/node_modules missing. Run 'just setup' first."
}

# Run a python module in the backend dir using the chosen interpreter.
py() {
  ( cd "${BACKEND_DIR}" && "$(py_bin)" "$@" )
}

# Run a console tool from the venv bin (ruff, black, mypy, pytest, alembic...).
venv_tool() {
  local tool="$1"; shift
  if [[ -x "${VENV_DIR}/bin/${tool}" ]]; then
    ( cd "${BACKEND_DIR}" && "${VENV_DIR}/bin/${tool}" "$@" )
  elif have "${tool}"; then
    ( cd "${BACKEND_DIR}" && "${tool}" "$@" )
  else
    die "'${tool}' not found. Run 'just setup' first."
  fi
}

compose() {
  ( cd "${REPO_ROOT}" && docker compose "$@" )
}
