"""Migration metadata integrity tests."""

from __future__ import annotations

from ast import literal_eval
from pathlib import Path
import re

VERSIONS_DIR = Path("migration/versions")
MAX_REVISION_ID_LENGTH = 32


class MigrationParseError(Exception):
    pass


def _extract_assignment(content: str, name: str) -> str:
    pattern = re.compile(rf"^{name}\s*:\s*[^=]+?=\s*(.+)$", re.MULTILINE)
    match = pattern.search(content)
    if match:
        return match.group(1)

    pattern = re.compile(rf"^{name}\s*=\s*(.+)$", re.MULTILINE)
    match = pattern.search(content)
    if match:
        return match.group(1)

    raise MigrationParseError(f"Could not find {name} assignment")


def _parse_migration_metadata(path: Path) -> tuple[str, str | tuple[str, ...] | None]:
    content = path.read_text()

    revision_value = _extract_assignment(content, "revision").strip().splitlines()[0]
    down_revision_raw = _extract_assignment(content, "down_revision").strip()

    if down_revision_raw.startswith("(") and ")" in content:
        down_revision_raw = re.search(
            r"^down_revision\s*:\s*[^=]+?=\s*(\(.*?\))$|^down_revision\s*=\s*(\(.*?\))$",
            content,
            re.MULTILINE | re.DOTALL,
        ).group(1) or re.search(
            r"^down_revision\s*=\s*(\(.*?\))$",
            content,
            re.MULTILINE | re.DOTALL,
        ).group(1)

    revision = literal_eval(revision_value)
    down_revision = literal_eval(down_revision_raw)

    if not isinstance(revision, str):
        raise MigrationParseError(f"Invalid revision type in {path}")

    if down_revision is not None and not isinstance(down_revision, (str, tuple)):
        raise MigrationParseError(f"Invalid down_revision type in {path}")

    return revision, down_revision


def _load_migrations() -> list[tuple[Path, str, str | tuple[str, ...] | None]]:
    migrations: list[tuple[Path, str, str | tuple[str, ...] | None]] = []
    for path in sorted(VERSIONS_DIR.glob("*.py")):
        revision, down_revision = _parse_migration_metadata(path)
        migrations.append((path, revision, down_revision))
    return migrations


def test_all_revision_ids_are_short_enough():
    """All Alembic revision IDs should fit alembic_version.version_num."""
    too_long: list[tuple[str, str]] = []

    for path, revision, _ in _load_migrations():
        if len(revision) > MAX_REVISION_ID_LENGTH:
            too_long.append((path.name, revision))

    assert not too_long, f"Found revision IDs longer than {MAX_REVISION_ID_LENGTH}: {too_long}"


def test_revision_ids_are_unique():
    """Revision IDs must be unique across migration files."""
    revisions = [revision for _, revision, _ in _load_migrations()]
    assert len(revisions) == len(set(revisions)), "Duplicate migration revision IDs found"


def test_down_revisions_reference_existing_revisions():
    """Every down_revision must refer to an existing migration revision."""
    migrations = _load_migrations()
    all_revisions = {revision for _, revision, _ in migrations}

    missing: list[tuple[str, str]] = []

    for path, _, down_revision in migrations:
        if down_revision is None:
            continue
        refs = (down_revision,) if isinstance(down_revision, str) else down_revision
        for ref in refs:
            if ref not in all_revisions:
                missing.append((path.name, ref))

    assert not missing, f"Missing down_revision references: {missing}"


def test_there_is_exactly_one_head_migration():
    """Migration graph should be linearized to one head."""
    migrations = _load_migrations()

    all_revisions = {revision for _, revision, _ in migrations}
    referenced: set[str] = set()
    for _, _, down_revision in migrations:
        if down_revision is None:
            continue
        if isinstance(down_revision, str):
            referenced.add(down_revision)
        else:
            referenced.update(down_revision)

    heads = all_revisions - referenced
    assert len(heads) == 1, f"Expected exactly one head, found: {sorted(heads)}"
