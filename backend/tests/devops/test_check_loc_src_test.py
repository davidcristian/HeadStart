"""Regression: check_loc.sh exempts frontend src/test/ infra."""

from __future__ import annotations

import subprocess
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _REPO_ROOT / "scripts" / "check_loc.sh"


def test_check_loc_exempts_frontend_src_test() -> None:
    """Exemption case must include */src/test/* so LOC and coverage agree."""
    text = _SCRIPT.read_text(encoding="utf-8")
    assert "*/src/test/*)" in text


def test_src_test_case_matches_frontend_helpers_not_product_src(
    tmp_path: Path,
) -> None:
    """Bash case */src/test/* matches vitest helpers; product src/ stays capped."""
    probe = tmp_path / "ops67_src_test_case.sh"
    probe.write_text(
        "\n".join(
            [
                "set -euo pipefail",
                "match() {",
                '  case "$1" in',
                "    */backend/tests/*) echo backend_tests ;;",
                "    */src/test/*) echo src_test ;;",
                "    *.test.ts | *.test.tsx) echo test_suffix ;;",
                "    *) echo capped ;;",
                "  esac",
                "}",
                'match "/repo/frontend/src/test/mockApiSamples.ts"',
                'match "/repo/frontend/src/test/nested/helper.ts"',
                'match "/repo/frontend/src/components/JobList.tsx"',
                'match "/repo/backend/tests/devops/test_ops67.py"',
                'match "/repo/frontend/src/hooks/jobMutations.test.tsx"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    out = subprocess.check_output(["bash", str(probe)], text=True)
    assert out.splitlines() == [
        "src_test",
        "src_test",
        "capped",
        "backend_tests",
        "test_suffix",
    ]
