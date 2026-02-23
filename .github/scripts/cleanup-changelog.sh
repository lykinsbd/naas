#!/bin/bash
set -euo pipefail

VERSION="$1"
CHANGELOG="$2"

# Extract major.minor.patch from version (e.g., 1.0.0 from 1.0.0rc1)
BASE_VERSION=$(echo "$VERSION" | grep -oE '^[0-9]+\.[0-9]+\.[0-9]+')

echo "Cleaning up pre-release entries for version $BASE_VERSION"

# Backup original
cp "$CHANGELOG" "${CHANGELOG}.backup"

# Create awk script to remove pre-release entries
awk -v base="$BASE_VERSION" '
BEGIN { skip = 0 }

# Match pre-release headers for this version
$0 ~ "^# NAAS " base "(a|b|rc)[0-9]+ " {
    skip = 1
    next
}

# Stop skipping when we hit any other release header
/^# NAAS [0-9]+\.[0-9]+\.[0-9]+/ {
    skip = 0
}

# Print lines that aren'\''t being skipped
!skip { print }
' "${CHANGELOG}.backup" > "$CHANGELOG"

# Verify the file is not empty and still has the header
if ! grep -q "^# Changelog" "$CHANGELOG"; then
    echo "ERROR: Changelog header missing after cleanup!"
    mv "${CHANGELOG}.backup" "$CHANGELOG"
    exit 1
fi

# Verify we didn't delete everything
if [ $(wc -l < "$CHANGELOG") -lt 5 ]; then
    echo "ERROR: Changelog too short after cleanup!"
    mv "${CHANGELOG}.backup" "$CHANGELOG"
    exit 1
fi

echo "✅ Cleanup successful"
rm "${CHANGELOG}.backup"
