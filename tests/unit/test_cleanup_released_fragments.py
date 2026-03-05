"""Tests for cleanup_released_fragments.py script."""

import sys
from pathlib import Path

import pytest

# Add scripts directory to path
scripts_dir = Path(__file__).parent.parent.parent / ".github" / "scripts"
sys.path.insert(0, str(scripts_dir))

from cleanup_released_fragments import (  # noqa: E402
    extract_released_issues,
    extract_released_prefix_fragments,
    find_fragments_to_delete,
)


@pytest.fixture
def sample_changelog(tmp_path):
    """Create a sample changelog with released versions."""
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(
        """# Changelog

<!-- towncrier release notes start -->

# NAAS 1.2.0 (2026-03-02)

## Features

- Add new feature ([#100](https://github.com/lykinsbd/naas/issues/100))
- Another feature ([#101](https://github.com/lykinsbd/naas/issues/101))

## Bug Fixes

- Fix bug ([#200](https://github.com/lykinsbd/naas/issues/200))

# NAAS 1.1.0 (2026-02-26)

## Features

- Old feature ([#50](https://github.com/lykinsbd/naas/issues/50))
"""
    )
    return changelog


@pytest.fixture
def changes_dir(tmp_path):
    """Create a changes directory with sample fragments."""
    changes = tmp_path / "changes"
    changes.mkdir()

    # Released fragments (should be found)
    (changes / "100.feature.md").write_text("Add new feature")
    (changes / "101.feature.md").write_text("Another feature")
    (changes / "200.bugfix.md").write_text("Fix bug")
    (changes / "50.feature.md").write_text("Old feature")

    # Unreleased fragments (should not be found)
    (changes / "300.feature.md").write_text("Future feature")
    (changes / "400.bugfix.md").write_text("Future fix")

    # Prefix fragments
    (changes / "+custom.feature.md").write_text("Add new feature")  # Matches released
    (changes / "+other.feature.md").write_text("Unreleased work")  # Doesn't match

    return changes


def test_extract_released_issues(sample_changelog):
    """Test extracting issue numbers from released versions."""
    issues = extract_released_issues(sample_changelog)

    assert 100 in issues
    assert 101 in issues
    assert 200 in issues
    assert 50 in issues
    assert len(issues) == 4


def test_find_fragments_to_delete(sample_changelog, changes_dir):
    """Test finding fragments that match released issues."""
    released_issues = extract_released_issues(sample_changelog)
    released_prefixes = extract_released_prefix_fragments(sample_changelog, changes_dir)
    fragments = find_fragments_to_delete(changes_dir, released_issues, released_prefixes)

    # Should find 5 fragments (4 numbered + 1 prefix)
    assert len(fragments) == 5

    fragment_names = {f[0].name for f in fragments}
    assert "100.feature.md" in fragment_names
    assert "101.feature.md" in fragment_names
    assert "200.bugfix.md" in fragment_names
    assert "50.feature.md" in fragment_names
    assert "+custom.feature.md" in fragment_names

    # Should not find unreleased
    assert "300.feature.md" not in fragment_names
    assert "400.bugfix.md" not in fragment_names
    assert "+other.feature.md" not in fragment_names
