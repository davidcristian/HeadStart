"""TST-03: Alembic migrations are applied on real Postgres in CI, not only create_all.

Unit tests still use SQLite ``create_all`` for speed, but CI's ``migrations`` job
runs ``just test-migrations`` (``alembic upgrade head`` on disposable Postgres)
so dialect-specific migration SQL cannot ship unexercised.
"""

from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CI = _REPO_ROOT / ".github" / "workflows" / "ci.yml"
_SCRIPT = _REPO_ROOT / "scripts" / "test-migrations.sh"
_ALEMBIC_INI = _REPO_ROOT / "backend" / "alembic.ini"


def test_ci_runs_test_migrations_job() -> None:
    """Every push/PR must apply the full migration chain on Postgres."""
    text = _CI.read_text(encoding="utf-8")
    assert "migrations:" in text
    assert "name: Migrations (alembic on Postgres)" in text
    assert "just test-migrations" in text
    assert "needs: [backend, frontend, migrations]" in text


def test_test_migrations_script_upgrades_empty_postgres() -> None:
    """Gate must boot disposable Postgres and run alembic upgrade head."""
    text = _SCRIPT.read_text(encoding="utf-8")
    assert "postgres:16-alpine" in text
    assert "alembic upgrade head" in text
    assert "alembic check" in text
    assert "have docker" in text


def test_alembic_revision_chain_is_linear() -> None:
    """Every revision must link into a single base→head chain (no branches)."""
    cfg = Config(str(_ALEMBIC_INI))
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    bases = script.get_bases()
    assert len(heads) == 1, f"expected one head, got {heads}"
    assert len(bases) == 1, f"expected one base, got {bases}"
    revisions = list(script.walk_revisions())
    node = script.get_revision(heads[0])
    walked = 0
    while node is not None:
        walked += 1
        down = node.down_revision
        if down is None:
            break
        assert not isinstance(down, tuple), f"unexpected merge at {node.revision}"
        node = script.get_revision(down)
    assert walked == len(revisions)


def test_pending_reply_send_after_index_declared_on_model() -> None:
    """ORM must keep ix_inbox_pending_reply_send_after (migration 0030 / due queue)."""
    from app.models.inbox_pending_reply import InboxPendingReply

    by_name = {idx.name: idx for idx in InboxPendingReply.__table__.indexes}
    assert "ix_inbox_pending_reply_send_after" in by_name
    assert [col.name for col in by_name["ix_inbox_pending_reply_send_after"].columns] == [
        "send_after"
    ]
