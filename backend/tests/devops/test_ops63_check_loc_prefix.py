"""Regression: check_loc.sh strips REPO_ROOT without glob patterns (OPS-63)."""

from __future__ import annotations

import subprocess
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _REPO_ROOT / "scripts" / "check_loc.sh"


def test_check_loc_avoids_glob_prefix_strip() -> None:
    """Offender paths must not use ${file#${REPO_ROOT}/} (glob pattern)."""
    text = _SCRIPT.read_text(encoding="utf-8")
    assert "${file#${REPO_ROOT}/}" not in text
    assert "${file:${#prefix}}" in text
    assert "OPS-63" in text


def test_literal_prefix_strip_survives_glob_metachars_in_root(
    tmp_path: Path,
) -> None:
    """Length-based strip keeps relative paths when the root contains [?]."""
    # Mirrors check_loc.sh: [[ == ]] + ${file:${#prefix}} vs ${file#${root}/}.
    probe = tmp_path / "ops63_prefix_strip.sh"
    probe.write_text(
        "\n".join(
            [
                "set -euo pipefail",
                'root="/tmp/HeadStart[dev]"',
                'file="${root}/backend/app/services/apply.py"',
                'prefix="${root}/"',
                'glob_strip="${file#${root}/}"',
                'if [[ "${file}" == "${prefix}"* ]]; then',
                '  literal_strip="${file:${#prefix}}"',
                "else",
                '  literal_strip="${file}"',
                "fi",
                'printf "%s\\n" "${glob_strip}"',
                'printf "%s\\n" "${literal_strip}"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    out = subprocess.check_output(["bash", str(probe)], text=True)
    glob_strip, literal_strip = out.splitlines()
    # Unquoted #pattern treats [dev] as a character class — wrong/empty strip.
    assert glob_strip != "backend/app/services/apply.py"
    assert literal_strip == "backend/app/services/apply.py"
