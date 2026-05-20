"""Unit tests for release-bump helpers in tasks.py.

The task itself does git/file/network side effects so we don't unit-test
the whole task body — those are exercised via `inv release-bump --dry-run`
during real release work. This file covers the pure validators that
catch operator mistakes before any side effects happen.
"""

import sys
from pathlib import Path

import pytest

# tasks.py lives at packages/naas/tasks.py, the same level as the naas/
# package. Add packages/naas/ to sys.path so the import works in any
# pytest collection mode.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tasks import (
    RELEASE_BRANCH_RE,
    RELEASE_VERSION_RE,
    _is_final_release,
    _validate_target_version,
)


class TestReleaseBranchRegex:
    """Branch must match release/X.Y exactly — not finalize-X.Y.Z, not X.Y.Z."""

    @pytest.mark.parametrize(
        "branch",
        [
            "release/1.0",
            "release/1.3",
            "release/2.1",
            "release/10.5",
            "release/100.200",
        ],
    )
    def test_valid_release_branches(self, branch):
        assert RELEASE_BRANCH_RE.match(branch) is not None

    @pytest.mark.parametrize(
        "branch",
        [
            "release/finalize-2.1.0",  # historical leftover branch shape
            "release/1.0.0",  # patch level on the branch name not allowed
            "release/foo",
            "release/v1.3",
            "develop",
            "main",
            "feature/something",
            "hotfix/123",
            "",
        ],
    )
    def test_invalid_branches(self, branch):
        assert RELEASE_BRANCH_RE.match(branch) is None


class TestReleaseVersionRegex:
    """Version must be X.Y.Z, X.Y.ZbN, or X.Y.ZrcN. Alphas rejected."""

    @pytest.mark.parametrize(
        "version",
        [
            "1.3.0",
            "1.3.1",
            "1.3.0b1",
            "1.3.0b10",
            "1.3.0rc1",
            "1.3.0rc99",
            "10.20.30",
            "0.0.0",
        ],
    )
    def test_valid_versions(self, version):
        assert RELEASE_VERSION_RE.match(version) is not None

    @pytest.mark.parametrize(
        "version",
        [
            "1.3.0a1",  # alphas rejected: develop-only
            "1.3",
            "v1.3.0",
            "1.3.0-rc.1",  # SemVer style not supported
            "1.3.0.post1",
            "1.3.0.dev1",
            "garbage",
            "",
            "1.3.0b",  # number required after b
            "1.3.0rc",
        ],
    )
    def test_invalid_versions(self, version):
        assert RELEASE_VERSION_RE.match(version) is None


class TestIsFinalRelease:
    @pytest.mark.parametrize(
        "version, expected",
        [
            ("1.3.0", True),
            ("1.3.1", True),
            ("10.20.30", True),
            ("1.3.0b1", False),
            ("1.3.0rc1", False),
            ("1.3.0rc99", False),
        ],
    )
    def test(self, version, expected):
        assert _is_final_release(version) is expected


class TestValidateTargetVersion:
    """Branch + current + target compatibility checks."""

    @pytest.mark.parametrize(
        "current, target",
        [
            ("1.3.0a1", "1.3.0b1"),
            ("1.3.0b1", "1.3.0rc1"),
            ("1.3.0rc1", "1.3.0rc2"),
            ("1.3.0rc2", "1.3.0"),
            ("1.3.0", "1.3.1"),
            ("1.3.5", "1.3.6"),
            ("1.3.0", "1.3.10"),  # double-digit patch
        ],
    )
    def test_valid_progressions_on_release_1_3(self, current, target):
        # Should not raise
        _validate_target_version(current, target, "release/1.3")

    def test_target_major_minor_must_match_branch(self):
        with pytest.raises(SystemExit, match="does not match branch"):
            _validate_target_version("1.3.0a1", "1.4.0b1", "release/1.3")

    def test_target_must_be_strictly_greater(self):
        with pytest.raises(SystemExit, match="must be strictly greater"):
            _validate_target_version("1.3.0", "1.3.0", "release/1.3")

    def test_target_must_not_be_lower(self):
        # Lower version on a 1.3.x branch would be caught either by
        # major.minor mismatch or strictly-greater.
        with pytest.raises(SystemExit):
            _validate_target_version("1.3.5", "1.3.4", "release/1.3")

    def test_alpha_target_rejected(self):
        with pytest.raises(SystemExit, match="not a valid release version"):
            _validate_target_version("1.3.0", "1.3.0a1", "release/1.3")

    def test_garbage_target_rejected(self):
        with pytest.raises(SystemExit, match="not a valid release version"):
            _validate_target_version("1.3.0", "garbage", "release/1.3")

    def test_non_release_branch_rejected(self):
        with pytest.raises(SystemExit, match="not a release branch"):
            _validate_target_version("1.3.0", "1.3.1", "main")

    def test_finalize_branch_rejected(self):
        with pytest.raises(SystemExit, match="not a release branch"):
            _validate_target_version("1.3.0", "1.3.1", "release/finalize-2.1.0")
