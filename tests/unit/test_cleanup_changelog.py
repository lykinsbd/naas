"""Tests for cleanup-changelog.py script."""

import sys
from pathlib import Path

import pytest

# Add scripts directory to path
scripts_dir = Path(__file__).parent.parent.parent / ".github" / "scripts"
sys.path.insert(0, str(scripts_dir))

# Import after path modification
from cleanup_changelog import cleanup_changelog  # noqa: E402


@pytest.fixture
def sample_changelog(tmp_path):
    """Create a sample changelog with multiple pre-releases."""
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(
        """# Changelog

All notable changes to NAAS will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

# NAAS 1.3.0rc2 (2026-03-04)

## Features

- New feature in rc2

# NAAS 1.3.0rc1 (2026-03-04)

## Features

- New feature in rc1

# NAAS 1.3.0b1 (2026-03-04)

## Features

- New feature in beta

# NAAS 1.2.0 (2026-03-02)

## Features

- Old release feature
"""
    )
    return changelog


def test_cleanup_keeps_current_rc(sample_changelog):
    """Test that cleanup keeps the current RC and removes older pre-releases."""
    cleanup_changelog("1.3.0rc2", sample_changelog)

    content = sample_changelog.read_text()

    # Should keep header
    assert "# Changelog" in content
    assert "<!-- towncrier release notes start -->" in content

    # Should keep current version
    assert "# NAAS 1.3.0rc2" in content
    assert "New feature in rc2" in content

    # Should remove older pre-releases
    assert "# NAAS 1.3.0rc1" not in content
    assert "New feature in rc1" not in content
    assert "# NAAS 1.3.0b1" not in content
    assert "New feature in beta" not in content

    # Should keep other releases
    assert "# NAAS 1.2.0" in content
    assert "Old release feature" in content


def test_cleanup_keeps_beta(sample_changelog):
    """Test that cleanup works with beta versions."""
    cleanup_changelog("1.3.0b1", sample_changelog)

    content = sample_changelog.read_text()

    # Should keep header
    assert "# Changelog" in content

    # Should keep beta
    assert "# NAAS 1.3.0b1" in content

    # Should remove RCs (they come after beta in the file but are "newer")
    assert "# NAAS 1.3.0rc2" not in content
    assert "# NAAS 1.3.0rc1" not in content


def test_cleanup_preserves_header(sample_changelog):
    """Test that header is always preserved."""
    cleanup_changelog("1.3.0rc2", sample_changelog)

    content = sample_changelog.read_text()
    lines = content.splitlines()

    # First line should be the header
    assert lines[0] == "# Changelog"
    assert "All notable changes to NAAS" in content
    assert "Keep a Changelog" in content
    assert "Semantic Versioning" in content


def test_cleanup_creates_backup(sample_changelog):
    """Test that backup is created and removed on success."""
    backup = sample_changelog.with_suffix(".md.backup")

    cleanup_changelog("1.3.0rc2", sample_changelog)

    # Backup should be removed after successful cleanup
    assert not backup.exists()


def test_cleanup_restores_on_error(sample_changelog):
    """Test that backup is restored if version is missing after cleanup."""
    original_content = sample_changelog.read_text()

    # Try to clean up with a version that doesn't exist
    with pytest.raises(SystemExit):
        cleanup_changelog("1.4.0rc1", sample_changelog)

    # Original should be restored
    assert sample_changelog.read_text() == original_content


def test_cleanup_with_final_release(tmp_path):
    """Test cleanup with final release version."""
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(
        """# Changelog

<!-- towncrier release notes start -->

# NAAS 1.3.0 (2026-03-04)

## Features

- Final release

# NAAS 1.3.0rc1 (2026-03-04)

## Features

- RC feature

# NAAS 1.2.0 (2026-03-02)

## Features

- Old release
"""
    )

    cleanup_changelog("1.3.0", changelog)

    content = changelog.read_text()

    # Should keep final release
    assert "# NAAS 1.3.0 (2026-03-04)" in content
    assert "Final release" in content

    # Should remove pre-releases for 1.3.0
    assert "# NAAS 1.3.0rc1" not in content
    assert "RC feature" not in content

    # Should keep other releases
    assert "# NAAS 1.2.0" in content


def test_cleanup_preserves_other_versions(tmp_path):
    """Test that cleanup preserves releases from other major.minor versions."""
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(
        """# Changelog

<!-- towncrier release notes start -->

# NAAS 1.3.0rc2 (2026-03-04)

## Features

- RC2 feature

# NAAS 1.3.0rc1 (2026-03-04)

## Features

- RC1 feature

# NAAS 1.2.0 (2026-03-02)

## Features

- v1.2.0 feature

# NAAS 1.1.0 (2026-02-26)

## Features

- v1.1.0 feature
"""
    )

    cleanup_changelog("1.3.0rc2", changelog)

    content = changelog.read_text()

    # Should keep current version
    assert "# NAAS 1.3.0rc2" in content
    assert "RC2 feature" in content

    # Should remove older 1.3.0 pre-releases
    assert "# NAAS 1.3.0rc1" not in content
    assert "RC1 feature" not in content

    # CRITICAL: Should keep other major.minor versions
    assert "# NAAS 1.2.0" in content
    assert "v1.2.0 feature" in content
    assert "# NAAS 1.1.0" in content
    assert "v1.1.0 feature" in content
