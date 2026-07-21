"""Regression: aws-deploy-env.sh quotes exports for safe eval."""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _REPO_ROOT / "scripts" / "aws-deploy-env.sh"


def test_aws_deploy_env_emits_printf_q_not_single_quoted_heredoc() -> None:
    """Exports must use printf %q; the old export X='…' heredoc is the bug."""
    text = _SCRIPT.read_text(encoding="utf-8")
    assert "printf" in text
    assert "%q" in text
    assert "cat <<EOF" not in text
    assert "export AWS_REGION='" not in text
    assert "export ECS_CLUSTER='" not in text
    assert "export APP_URL='" not in text


def test_aws_deploy_env_eval_survives_single_quote_in_outputs(
    tmp_path: Path,
) -> None:
    """A terraform/aws value containing ' must still round-trip through eval."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()

    # Stub terraform: echo values that include a single quote / metachars.
    terraform = bin_dir / "terraform"
    terraform.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "# Ignore -chdir / output flags; last arg is the output name.\n"
        'name="${@: -1}"\n'
        'case "$name" in\n'
        '  region) echo "us-east-2" ;;\n'
        '  ecs_cluster_name) echo "headstart-O\'Brien-cluster" ;;\n'
        '  app_url) echo "https://app.example.com/O\'Brien" ;;\n'
        '  alb_dns_name) echo "alb.example.com" ;;\n'
        '  *) echo "unexpected output: $name" >&2; exit 1 ;;\n'
        "esac\n",
        encoding="utf-8",
    )
    terraform.chmod(terraform.stat().st_mode | stat.S_IEXEC)

    aws = bin_dir / "aws"
    aws.write_text(
        "#!/usr/bin/env bash\n" "set -euo pipefail\n" 'echo "123456789012"\n',
        encoding="utf-8",
    )
    aws.chmod(aws.stat().st_mode | stat.S_IEXEC)

    env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}
    emitted = subprocess.check_output(
        ["bash", str(_SCRIPT), "beta"],
        cwd=_REPO_ROOT,
        env=env,
        text=True,
    )

    # Must not look like the broken single-quote wrap.
    assert "export ECS_CLUSTER='headstart-O'Brien-cluster'" not in emitted
    assert "printf" not in emitted  # emitted lines are assignments only

    # Round-trip through eval the same way operators / aws-first-deploy do.
    probe = subprocess.check_output(
        [
            "bash",
            "-c",
            'eval "$1"; printf "%s\\n" "$ECS_CLUSTER"; printf "%s\\n" "$APP_URL"; '
            'printf "%s\\n" "$ECR_REGISTRY"; printf "%s\\n" "$ENVIRONMENT"',
            "_",
            emitted,
        ],
        text=True,
    )
    lines = probe.splitlines()
    assert lines[0] == "headstart-O'Brien-cluster"
    assert lines[1] == "https://app.example.com/O'Brien"
    assert lines[2] == "123456789012.dkr.ecr.us-east-2.amazonaws.com"
    assert lines[3] == "beta"
