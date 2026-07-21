#!/usr/bin/env bash
# Regenerate hashed backend lockfiles from pyproject.toml.
# Docker, CI, and `just setup` install from these files so builds are
# reproducible; keep pyproject.toml floors as the human-editable contract.
#
# Usage:
#   lock-backend.sh                           # add/drop deps, keep existing pins
#   lock-backend.sh --upgrade-package NAME    # repeatable; bump only NAME
#   lock-backend.sh --upgrade                 # bump every pin to its ceiling
#   lock-backend.sh --dry-run [...]           # print the plan, compile nothing
#
# A bare run deliberately does NOT move existing pins: pip-compile treats the
# current lockfile as constraints, so applying a Dependabot bump needs
# --upgrade-package. Named packages are only passed to a lockfile that already
# pins them, because pip-compile otherwise ADDS an unknown name to that file:
# `--upgrade-package pre-commit` against the runtime lock pulls pre-commit and
# its virtualenv/nodeenv/identify tail into production deps.
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

upgrade_all=0
dry_run=0
declare -a wanted=()

while (( $# )); do
  case "$1" in
    --upgrade) upgrade_all=1 ;;
    --upgrade-package)
      [[ -n "${2:-}" ]] || die "--upgrade-package needs a package name"
      wanted+=("$2")
      shift
      ;;
    --upgrade-package=*) wanted+=("${1#*=}") ;;
    --dry-run) dry_run=1 ;;
    -h|--help) sed -n '6,10p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) die "Unknown option '$1'. Use --upgrade | --upgrade-package NAME | --dry-run" ;;
  esac
  shift
done

if (( upgrade_all )) && (( ${#wanted[@]} )); then
  die "--upgrade and --upgrade-package are mutually exclusive"
fi

# PEP 503 names are case-insensitive and treat . _ - as equivalent.
normalize() { printf '%s' "$1" | tr '[:upper:]' '[:lower:]' | tr '._' '--'; }

# Normalized names already pinned in a lockfile.
lock_packages() {
  sed -n 's/^\([A-Za-z0-9._-]*\)==.*/\1/p' "$1" | tr '[:upper:]' '[:lower:]' | tr '._' '--'
}

lock_has_package() { lock_packages "$1" | grep -qx "$(normalize "$2")"; }

# Reject a typo instead of silently upgrading nothing.
for pkg in ${wanted[@]+"${wanted[@]}"}; do
  found=0
  for lock in requirements.txt requirements-dev.txt requirements-playwright.txt; do
    path="${BACKEND_DIR}/${lock}"
    [[ -f "${path}" ]] || continue
    if lock_has_package "${path}" "${pkg}"; then found=1; break; fi
  done
  (( found )) || die "'${pkg}' is not pinned in any backend lockfile; check the spelling"
done

# Flags for one lockfile: --upgrade passes through, named packages are filtered
# to the ones that file already pins.
upgrade_flags_for() {
  local path="$1" pkg
  if (( upgrade_all )); then
    printf '%s\n' "--upgrade"
    return
  fi
  for pkg in ${wanted[@]+"${wanted[@]}"}; do
    if lock_has_package "${path}" "${pkg}"; then
      printf '%s\n%s\n' "--upgrade-package" "${pkg}"
    fi
  done
}

if (( dry_run )); then
  log "Lock plan (no files written)"
  for spec in "requirements.txt:" "requirements-dev.txt:--extra=dev" \
              "requirements-playwright.txt:--extra=playwright"; do
    lock="${spec%%:*}"
    mapfile -t flags < <(upgrade_flags_for "${BACKEND_DIR}/${lock}")
    if (( ${#flags[@]} )); then
      echo "  ${lock}: ${flags[*]}"
    else
      echo "  ${lock}: keep existing pins"
    fi
  done
  ok "Dry run complete."
  exit 0
fi

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
  mapfile -t flags < <(upgrade_flags_for "${BACKEND_DIR}/${out}")
  (
    cd "${BACKEND_DIR}" || exit
    "${python_bin}" -m piptools compile \
      --generate-hashes \
      --allow-unsafe \
      --strip-extras \
      --quiet \
      --output-file="${out}" \
      ${flags[@]+"${flags[@]}"} \
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
