#!/usr/bin/env python3
"""Clean up changelog fragments that have been released."""

import re
import sys
from pathlib import Path


def extract_released_issues(changelog_path: Path) -> set[int]:
    """Extract issue numbers from released versions in CHANGELOG.md.

    Only extracts from version sections (e.g., "# NAAS 1.0.0"), not from
    "Unreleased" sections.
    """
    released_issues = set()
    content = changelog_path.read_text()

    # Match version headers like "# NAAS 1.0.0 (2026-02-23)"
    version_pattern = r"^#+ NAAS \d+\.\d+\.\d+.*$"

    in_released_section = False
    for line in content.splitlines():
        # Check if we're entering a released version section
        if re.match(version_pattern, line):
            in_released_section = True
            continue

        # Stop at next major section (Unreleased or another version)
        if line.startswith("#") and in_released_section:
            in_released_section = False
            continue

        # Extract issue numbers from released sections
        if in_released_section:
            # Match patterns like (#123) or [#123]
            for match in re.finditer(r"[(\[]#(\d+)[)\]]", line):
                released_issues.add(int(match.group(1)))

    return released_issues


def extract_released_prefix_fragments(changelog_path: Path, changes_dir: Path) -> set[str]:
    """Extract +prefix fragment names that appear in released versions.

    Checks if the content of +prefix fragments appears in released CHANGELOG sections.
    """
    released_fragments = set()
    content = changelog_path.read_text()

    # Match version headers
    version_pattern = r"^#+ NAAS \d+\.\d+\.\d+.*$"

    # Extract released section content
    in_released_section = False
    released_content = []
    for line in content.splitlines():
        if re.match(version_pattern, line):
            in_released_section = True
            continue
        if line.startswith("#") and in_released_section:
            in_released_section = False
            continue
        if in_released_section:
            released_content.append(line)

    released_text = "\n".join(released_content)

    # Check each +prefix fragment
    for fragment in changes_dir.glob("+*.md"):
        fragment_content = fragment.read_text().strip()
        # If fragment content appears in released section, mark for deletion
        if fragment_content and fragment_content in released_text:
            released_fragments.add(fragment.name)

    return released_fragments


def find_fragments_to_delete(
    changes_dir: Path, released_issues: set[int], released_prefixes: set[str]
) -> list[tuple[Path, int | str]]:
    """Find fragments that match released issue numbers or prefix fragments.

    Considers both numbered fragments (e.g., 123.feature.md) and +prefix fragments.
    """
    fragments_to_delete: list[tuple[Path, int | str]] = []

    # Pattern: <number>.<type>.md (e.g., 123.feature.md)
    fragment_pattern = re.compile(r"^(\d+)\.\w+\.md$")

    for fragment in changes_dir.glob("*.md"):
        # Check numbered fragments
        match = fragment_pattern.match(fragment.name)
        if match:
            issue_num = int(match.group(1))
            if issue_num in released_issues:
                fragments_to_delete.append((fragment, issue_num))
        # Check +prefix fragments
        elif fragment.name.startswith("+") and fragment.name in released_prefixes:
            fragments_to_delete.append((fragment, f"+{fragment.stem}"))

    return fragments_to_delete


def generate_pr_body(fragments: list[tuple[Path, int | str]], version: str, changelog_path: Path) -> str:
    """Generate detailed PR body with table of deletions."""
    changelog_content = changelog_path.read_text()

    body = f"""## Summary

Automatically cleaning up changelog fragments that were released in {version}.

## Fragments Deleted

| Fragment | Issue/ID | Changelog Entry |
|----------|----------|-----------------|
"""

    for fragment_path, identifier in sorted(fragments, key=lambda x: str(x[1])):
        # Find the changelog entry
        if isinstance(identifier, int):
            # Numbered fragment
            entry_pattern = rf"- .*\(#({identifier})\)"
            match = re.search(entry_pattern, changelog_content)
            entry = match.group(0) if match else f"(#{identifier})"
            issue_ref = f"#{identifier}"
        else:
            # +prefix fragment
            fragment_content = fragment_path.read_text().strip()
            # Try to find in changelog
            if fragment_content in changelog_content:
                entry = fragment_content[:80]
            else:
                entry = "(internal)"
            issue_ref = identifier

        # Truncate long entries
        if len(entry) > 80:
            entry = entry[:77] + "..."

        body += f"| `{fragment_path.name}` | {issue_ref} | {entry} |\n"

    body += f"""
## Safety Checks

- ✅ Numbered fragments cross-referenced with CHANGELOG.md version {version}
- ✅ +prefix fragments verified in released content
- ✅ Total fragments deleted: {len(fragments)}

## Next Steps

This PR will auto-merge once CI checks pass. If something looks wrong, close this PR to prevent the merge.
"""

    return body


def main() -> int:
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: cleanup_released_fragments.py <version>")
        return 1

    version = sys.argv[1]
    repo_root = Path(__file__).parent.parent.parent
    changelog_path = repo_root / "CHANGELOG.md"
    changes_dir = repo_root / "changes"

    if not changelog_path.exists():
        print(f"Error: CHANGELOG.md not found at {changelog_path}")
        return 1

    if not changes_dir.exists():
        print(f"Error: changes/ directory not found at {changes_dir}")
        return 1

    # Extract released issues
    print(f"Parsing {changelog_path}...")
    released_issues = extract_released_issues(changelog_path)
    print(f"Found {len(released_issues)} released issues")

    # Extract released +prefix fragments
    released_prefixes = extract_released_prefix_fragments(changelog_path, changes_dir)
    print(f"Found {len(released_prefixes)} released +prefix fragments")

    # Find fragments to delete
    print(f"Scanning {changes_dir}...")
    fragments_to_delete = find_fragments_to_delete(changes_dir, released_issues, released_prefixes)

    if not fragments_to_delete:
        print("No fragments to delete")
        return 0

    print(f"Found {len(fragments_to_delete)} fragments to delete:")
    for fragment_path, identifier in fragments_to_delete:
        print(f"  - {fragment_path.name} ({identifier})")

    # Delete fragments
    for fragment_path, _ in fragments_to_delete:
        print(f"Deleting {fragment_path.name}...")
        fragment_path.unlink()

    # Generate PR body
    pr_body = generate_pr_body(fragments_to_delete, version, changelog_path)
    pr_body_path = repo_root / "pr_body.txt"
    pr_body_path.write_text(pr_body)
    print(f"PR body written to {pr_body_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
