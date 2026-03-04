#!/usr/bin/env python3
"""Clean up old pre-release entries from CHANGELOG.md while preserving the current version."""

import re
import sys
from pathlib import Path


def cleanup_changelog(version: str, changelog_path: Path) -> None:
    """Remove old pre-release entries for a version, keeping only the current one.

    Args:
        version: Current version (e.g., "1.3.0rc1")
        changelog_path: Path to CHANGELOG.md
    """
    # Extract base version (e.g., "1.3.0" from "1.3.0rc1")
    base_version_match = re.match(r"^(\d+\.\d+\.\d+)", version)
    if not base_version_match:
        print(f"ERROR: Invalid version format: {version}")
        sys.exit(1)

    base_version = base_version_match.group(1)
    print(f"Cleaning up old pre-release entries for version {base_version} (keeping {version})")

    # Read original
    content = changelog_path.read_text()
    lines = content.splitlines(keepends=True)

    # Backup
    backup_path = changelog_path.with_suffix(".md.backup")
    backup_path.write_text(content)

    # Process lines
    output_lines = []
    skip = False
    in_releases = False

    # Regex for release headers
    release_header_pattern = re.compile(r"^# NAAS (\d+\.\d+\.\d+(?:a|b|rc)\d+)")

    for line in lines:
        # Preserve header until first release
        if not in_releases and not release_header_pattern.match(line):
            output_lines.append(line)
            continue

        # Check for any release header
        match = release_header_pattern.match(line)
        if not match:
            # Also check for final releases (no pre-release suffix)
            final_release_match = re.match(r"^# NAAS (\d+\.\d+\.\d+) ", line)
            if final_release_match:
                in_releases = True
                skip = False  # Never skip final releases
                output_lines.append(line)
                continue

        if match:
            in_releases = True
            found_version = match.group(1)

            # Check if this is a pre-release for our base version
            if found_version.startswith(base_version) and re.search(r"(a|b|rc)\d+$", found_version):
                if found_version == version:
                    # Keep current version
                    skip = False
                else:
                    # Skip older pre-releases
                    skip = True
                    continue
            else:
                # Different version, stop skipping
                skip = False

        # Output non-skipped lines
        if in_releases and not skip:
            output_lines.append(line)

    # Write result
    changelog_path.write_text("".join(output_lines))

    # Verify
    result_content = changelog_path.read_text()
    if f"# NAAS {version}" not in result_content:
        print("ERROR: Version entry missing after cleanup!")
        backup_path.rename(changelog_path)
        sys.exit(1)

    if len(result_content.splitlines()) < 5:
        print("ERROR: Changelog too short after cleanup!")
        backup_path.rename(changelog_path)
        sys.exit(1)

    print("✅ Cleanup successful")
    backup_path.unlink()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} VERSION CHANGELOG_PATH")
        sys.exit(1)

    version = sys.argv[1]
    changelog_path = Path(sys.argv[2])

    if not changelog_path.exists():
        print(f"ERROR: {changelog_path} does not exist")
        sys.exit(1)

    cleanup_changelog(version, changelog_path)
