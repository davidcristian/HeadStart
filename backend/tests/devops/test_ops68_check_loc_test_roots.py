"""Regression: check_loc.sh exempts only known test roots (OPS-68)."""

from __future__ import annotations

import subprocess
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _REPO_ROOT / "scripts" / "check_loc.sh"


def test_check_loc_uses_backend_tests_root_not_any_tests_segment() -> None:
    """Exemption must be */backend/tests/*, not a bare */tests/* glob."""
    text = _SCRIPT.read_text(encoding="utf-8")
    assert "*/backend/tests/*)" in text
    assert "OPS-68" in text
    # A bare */tests/* would exempt nested app/.../tests/ production modules.
    assert "*/tests/*)" not in text


def test_backend_tests_case_exempts_suite_not_nested_app_tests(
    tmp_path: Path,
) -> None:
    """Bash case */backend/tests/* matches the suite; app/.../tests/ stays capped."""
    probe = tmp_path / "ops68_test_roots_case.sh"
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
                'match "/repo/backend/tests/devops/test_ops68.py"',
                'match "/repo/backend/app/foo/tests/generated_client.py"',
                'match "/repo/frontend/src/test/mockApiSamples.ts"',
                'match "/repo/frontend/src/hooks/jobMutations.test.tsx"',
                'match "/repo/frontend/src/components/JobList.tsx"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    out = subprocess.check_output(["bash", str(probe)], text=True)
    assert out.splitlines() == [
        "backend_tests",
        "capped",
        "src_test",
        "test_suffix",
        "capped",
    ]
