#!/usr/bin/env bash
# Regenerate the third-party attribution manifest.
# Inventories packages conveyed by the backend/frontend container images:
#   - backend runtime lock (requirements.txt) + worker Playwright lock
#   - frontend npm production dependencies
# Writes the same file to the repo root and into each Docker build context.
# shellcheck source=lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

OUT_NAME="THIRD_PARTY_LICENSES.md"
ROOT_OUT="${REPO_ROOT}/${OUT_NAME}"
BACKEND_OUT="${BACKEND_DIR}/${OUT_NAME}"
FRONTEND_OUT="${FRONTEND_DIR}/public/${OUT_NAME}"

have python3 || die "python3 is required to generate ${OUT_NAME}"
have npm || die "npm is required to generate ${OUT_NAME}"
[[ -f "${BACKEND_DIR}/requirements.txt" ]] \
  || die "Missing ${BACKEND_DIR}/requirements.txt. Run 'just lock-backend'"
[[ -f "${BACKEND_DIR}/requirements-playwright.txt" ]] \
  || die "Missing ${BACKEND_DIR}/requirements-playwright.txt. Run 'just lock-backend'"
[[ -d "${FRONTEND_DIR}/node_modules" ]] \
  || die "frontend/node_modules missing. Run 'just setup' first."

tmpdir="$(mktemp -d "${TMPDIR:-/tmp}/headstart-licenses.XXXXXX")"
cleanup() { rm -rf "${tmpdir}"; }
trap cleanup EXIT

log "Creating isolated venv for runtime lock inventory"
# Prefer stdlib venv; fall back to the virtualenv package (common on slim images).
if ! python3 -m venv "${tmpdir}/venv" >/dev/null 2>&1; then
  rm -rf "${tmpdir}/venv"
  if have virtualenv; then
    virtualenv "${tmpdir}/venv" >/dev/null
  elif python3 -m virtualenv "${tmpdir}/venv" >/dev/null 2>&1; then
    :
  else
    die "Need python3-venv or virtualenv to build an isolated license inventory"
  fi
fi
# shellcheck disable=SC1091
source "${tmpdir}/venv/bin/activate"
python -m pip install --upgrade pip >/dev/null
python -m pip install --quiet 'pip-licenses>=5.0'
python -m pip install --quiet --require-hashes -r "${BACKEND_DIR}/requirements.txt"

backend_md="${tmpdir}/backend.md"
pip-licenses \
  --format=markdown \
  --with-urls \
  --order=name \
  --ignore-packages pip pip-licenses setuptools wheel \
  --output-file "${backend_md}"

log "Adding Playwright worker lock packages"
python -m pip install --quiet --require-hashes -r "${BACKEND_DIR}/requirements-playwright.txt"
# Diff: packages present after playwright lock that were not in the runtime table.
playwright_md="${tmpdir}/playwright.md"
pip-licenses \
  --format=markdown \
  --with-urls \
  --order=name \
  --ignore-packages pip pip-licenses setuptools wheel \
  --output-file "${tmpdir}/all-backend.md"
# Keep only playwright (+ its unique deps) by name: lines in all not in runtime.
# Header rows are shared; filter by package name column for readability.
awk 'NR<=2 {next} {print}' "${backend_md}" | sort > "${tmpdir}/runtime-rows.txt"
awk 'NR<=2 {next} {print}' "${tmpdir}/all-backend.md" | sort > "${tmpdir}/all-rows.txt"
comm -13 "${tmpdir}/runtime-rows.txt" "${tmpdir}/all-rows.txt" > "${tmpdir}/playwright-rows.txt"
{
  echo "| Name | Version | License | URL |"
  echo "|------|---------|---------|-----|"
  if [[ -s "${tmpdir}/playwright-rows.txt" ]]; then
    cat "${tmpdir}/playwright-rows.txt"
  else
    echo "| _(no additional packages)_ | | | |"
  fi
} > "${playwright_md}"

deactivate

log "Inventorying frontend production npm dependencies"
frontend_raw="${tmpdir}/frontend.txt"
(
  cd "${FRONTEND_DIR}" || exit 1
  npx --yes license-checker \
    --production \
    --excludePrivatePackages \
    --relativeLicensePath \
    --out "${frontend_raw}"
)
# Drop absolute checkout paths so the committed file is machine-stable.
sed -i "s|${FRONTEND_DIR}/||g" "${frontend_raw}"
sed -i "s|${FRONTEND_DIR}|frontend|g" "${frontend_raw}"

generated_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
{
  cat <<EOF
# Third-party licenses

HeadStart itself is licensed under [\`LICENSE\`](LICENSE) (SSPL 1.0).
This file lists **third-party** packages bundled into the conveyed backend and
frontend container images so upstream MIT / BSD / Apache / LGPL (and similar)
attribution terms are preserved for self-host and distribution.

Regenerate after dependency bumps:

\`\`\`bash
just generate-third-party-licenses
\`\`\`

Generated at \`${generated_at}\` (UTC).

## Backend runtime (\`backend/requirements.txt\`)

Packages installed into the API / beat image (and the shared base of the worker
image) from the hashed runtime lockfile.

EOF
  cat "${backend_md}"
  cat <<EOF

## Backend worker extras (\`backend/requirements-playwright.txt\`)

Additional packages installed only on the Playwright worker image (beyond the
runtime lock above).

EOF
  cat "${playwright_md}"
  cat <<EOF

## Frontend production (\`frontend/package.json\` dependencies)

npm production dependencies and their transitive packages, as resolved in
\`frontend/node_modules\` for the SPA build.

\`\`\`
EOF
  cat "${frontend_raw}"
  echo '```'
  cat <<'EOF'

## LGPL-3.0 notice (`psycopg` / `psycopg-binary`)

The backend images include **psycopg** and **psycopg-binary** under
**LGPL-3.0-only** (see the runtime table above). HeadStart does **not** vendor
or modify these packages: they are installed unmodified from PyPI via the
hashed lockfile (`psycopg[binary]` in `backend/pyproject.toml`).

LGPL-3.0 §4 expects recipients of a conveyed Combined Work to be able to obtain
the LGPL library's corresponding source and to relink with a modified version.
Because psycopg remains a normal pip dependency (not statically vendored into
HeadStart), that obligation is met for self-hosters by:

1. **Corresponding source.** Download the same versions from PyPI
   (`pip download psycopg==<version> psycopg-binary==<version>`) or from the
   upstream project at https://psycopg.org / the repository URL listed in the
   table above.
2. **Relink.** Replace the installed wheels in your image or venv with a
   rebuilt `psycopg` / `psycopg-binary` of your choice and restart the process;
   no HeadStart rebuild of a vendored copy is required.

Operators who redistribute modified HeadStart images that still bundle these
wheels should keep this notice (and the inventory above) with their conveyance.

---

This file is copied into backend and frontend container images at
`/app/THIRD_PARTY_LICENSES.md` (backend) and served as
`/THIRD_PARTY_LICENSES.md` from the SPA (frontend `public/`).
EOF
} > "${tmpdir}/combined.md"

install -m 0644 "${tmpdir}/combined.md" "${ROOT_OUT}"
install -m 0644 "${tmpdir}/combined.md" "${BACKEND_OUT}"
mkdir -p "$(dirname "${FRONTEND_OUT}")"
install -m 0644 "${tmpdir}/combined.md" "${FRONTEND_OUT}"

ok "Wrote ${OUT_NAME} (root + backend/ + frontend/public/)."
