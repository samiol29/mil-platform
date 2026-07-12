"""
Unit tests for scripts/check_destructive_migrations.py — the FR-DEPLOY-005
migration-safety CI gate (spec 005-enterprise-platform §17, Wave 4).

Imported directly by file path (not a package) since `scripts/` is a
collection of standalone operational scripts, not an installed module.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "check_destructive_migrations.py"


@pytest.fixture(scope="module")
def module():
    spec = importlib.util.spec_from_file_location("check_destructive_migrations", _SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class TestDestructivePatternDetection:
    def test_drop_table_is_flagged(self, module) -> None:
        matches = [
            p.pattern for p in module._DESTRUCTIVE_PATTERNS if p.search("op.drop_table('foo')")
        ]
        assert matches

    def test_drop_column_is_flagged(self, module) -> None:
        matches = [
            p.pattern for p in module._DESTRUCTIVE_PATTERNS if p.search("op.drop_column('t', 'c')")
        ]
        assert matches

    def test_audit_delete_is_flagged(self, module) -> None:
        matches = [
            p.pattern
            for p in module._DESTRUCTIVE_PATTERNS
            if p.search("op.execute('DELETE FROM audit.audit_events')")
        ]
        assert matches

    def test_additive_migration_is_not_flagged(self, module) -> None:
        content = "op.add_column('foo', sa.Column('bar', sa.String()))"
        matches = [p.pattern for p in module._DESTRUCTIVE_PATTERNS if p.search(content)]
        assert matches == []


class TestCheck:
    def test_returns_zero_when_no_changed_files(self, module, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(module, "_changed_migration_files", lambda base: [])
        assert module.check("origin/main") == 0

    def test_returns_one_for_unreviewed_destructive_migration(
        self, module, tmp_path, monkeypatch
    ) -> None:
        migration = tmp_path / "0099_drop_stuff.py"
        migration.write_text("def upgrade():\n    op.drop_table('foo')\n")
        monkeypatch.setattr(module, "_changed_migration_files", lambda base: [migration])
        assert module.check("origin/main") == 1

    def test_returns_zero_when_approval_marker_present(self, module, tmp_path, monkeypatch) -> None:
        migration = tmp_path / "0099_drop_stuff.py"
        migration.write_text(
            "# destructive-migration-approved\ndef upgrade():\n    op.drop_table('foo')\n"
        )
        monkeypatch.setattr(module, "_changed_migration_files", lambda base: [migration])
        assert module.check("origin/main") == 0

    def test_returns_zero_for_additive_only_migration(self, module, tmp_path, monkeypatch) -> None:
        migration = tmp_path / "0099_add_column.py"
        migration.write_text("def upgrade():\n    op.add_column('foo', sa.Column('bar'))\n")
        monkeypatch.setattr(module, "_changed_migration_files", lambda base: [migration])
        assert module.check("origin/main") == 0
