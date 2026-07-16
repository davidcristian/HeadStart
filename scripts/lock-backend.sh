#!/usr/bin/env bash
# Regenerate hashed backend lockfiles from pyproject.toml (XCT-14).
# Docker, CI, and `just setup` install from these files so builds are
# reproducible; keep pyproject.toml floors as the human-editable contract.
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

log "Regenerating backend lockfiles (pip-tools, hashed)"

if [[ -x "${VENV_DIR}/bin/python" ]]; then
  python_bin="${VENV_DIR}/bin/python"
elif have python3; then
  python_bin="$(command -v python3)"
else
  die "No python interpreter found. Run 'just setup' first."
fi

"${python_bin}" -m pip install -q "pip-tools>=7.4"

compile() {
  local out="$1"
  shift
  (
    cd "${BACKEND_DIR}" || exit
    "${python_bin}" -m piptools compile \
      --generate-hashes \
      --allow-unsafe \
      --strip-extras \
      --quiet \
      --output-file="${out}" \
      "$@" \
      pyproject.toml
  )
}

compile requirements.txt
compile requirements-dev.txt --extra=dev
compile requirements-playwright.txt --extra=playwright

for lock in requirements.txt requirements-dev.txt requirements-playwright.txt; do
  path="${BACKEND_DIR}/${lock}"
  [[ -s "${path}" ]] || die "Expected non-empty lockfile at ${path}"
  grep -q -- '--hash=' "${path}" || die "Lockfile ${path} is missing package hashes"
done

ok "Wrote backend/requirements.txt, requirements-dev.txt, requirements-playwright.txt"
ok "Commit the lockfiles with any pyproject.toml dependency change."
