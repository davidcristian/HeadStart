#!/usr/bin/env bash
# Fail when source files exceed the AGENTS.md soft LOC cap (~300 lines).
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

MAX_LOC="${MAX_LOC:-300}"

log "File length check (max ${MAX_LOC} LOC)"

mapfile -t offenders < <(
  find "${REPO_ROOT}" \
    \( -path "*/node_modules/*" -o -path "*/.venv/*" -o -path "*/dist/*" -o -path "*/.git/*" \
       -o -path "*/__pycache__/*" -o -path "*/.pytest_cache/*" \) -prune \
    -o -type f \( -name "*.py" -o -name "*.ts" -o -name "*.tsx" \) -print \
    | while read -r file; do
        case "${file}" in
          */alembic/versions/*) continue ;;
          # The ~300-line cap targets source modules (low-context, one
          # responsibility). Test files map to one module and grow with the
          # number of cases, so they are exempt — but only at known roots
          # (OPS-68): a nested …/tests/ under app/src must stay capped.
          # Frontend vitest helpers live under src/test/ (singular) and are
          # coverage-excluded the same way (OPS-67).
          */backend/tests/*) continue ;;
          */src/test/*) continue ;;
          *.test.ts | *.test.tsx) continue ;;
        esac
        lines=$(wc -l < "${file}")
        if (( lines > MAX_LOC )); then
          # Literal prefix strip (OPS-63): ${var#pattern} treats the pattern as a
          # glob, so a REPO_ROOT with *?[] would mis-strip. Length-based slice
          # after a literal [[ == ]] prefix check does not.
          prefix="${REPO_ROOT}/"
          if [[ "${file}" == "${prefix}"* ]]; then
            rel="${file:${#prefix}}"
          else
            rel="${file}"
          fi
          printf "%s\t%s\n" "${lines}" "${rel}"
        fi
      done \
    | sort -rn
)

if ((${#offenders[@]} > 0)); then
  echo "Files over ${MAX_LOC} lines:" >&2
  for entry in "${offenders[@]}"; do
    lines="${entry%%$'\t'*}"
    path="${entry#*$'\t'}"
    printf "  %4s  %s\n" "${lines}" "${path}" >&2
  done
  die "${#offenders[@]} file(s) exceed the ${MAX_LOC}-line cap. Split or extract helpers."
fi

ok "All source files are at or below ${MAX_LOC} lines."
