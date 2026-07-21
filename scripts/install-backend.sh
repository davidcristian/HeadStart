#!/usr/bin/env bash
# Install backend deps from the hashed lockfile, then the local package
# without resolving further deps. Used by setup and CI.
#
# Usage:
#   ./scripts/install-backend.sh              # runtime lock + editable package
#   ./scripts/install-backend.sh --dev        # dev lock + editable package
#   ./scripts/install-backend.sh --playwright # playwright lock (no editable)
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

extra="runtime"
editable=1
case "${1:-}" in
  --dev)
    extra="dev"
    ;;
  --playwright)
    extra="playwright"
    editable=0
    ;;
  "")
    ;;
  *)
    die "Unknown option '${1}'. Use --dev|--playwright"
    ;;
esac

case "${extra}" in
  runtime)    lock="${BACKEND_DIR}/requirements.txt" ;;
  dev)        lock="${BACKEND_DIR}/requirements-dev.txt" ;;
  playwright) lock="${BACKEND_DIR}/requirements-playwright.txt" ;;
esac

[[ -f "${lock}" ]] || die "Missing lockfile ${lock}. Run 'just lock-backend'."

if [[ -x "${VENV_DIR}/bin/pip" ]]; then
  pip_bin="${VENV_DIR}/bin/pip"
elif have pip; then
  pip_bin="$(command -v pip)"
elif have pip3; then
  pip_bin="$(command -v pip3)"
else
  die "pip not found. Run 'just setup' first."
fi

log "Installing backend dependencies from $(basename "${lock}") (hashed)"
"${pip_bin}" install --upgrade pip >/dev/null
"${pip_bin}" install --require-hashes -r "${lock}"

if [[ "${editable}" -eq 1 ]]; then
  log "Installing local package editable (no dependency resolve)"
  "${pip_bin}" install --no-deps -e "${BACKEND_DIR}"
fi

ok "Backend install complete (${extra})."
