#!/bin/bash
set -euo pipefail

VERSION="$1"
CHANGELOG="$2"

# Extract major.minor.patch from version (e.g., 1.0.0 from 1.0.0rc1)
BASE_VERSION=$(echo "$VERSION" | grep -oE '^[0-9]+\.[0-9]+\.[0-9]+')

echo "Cleaning up old pre-release entries for version $BASE_VERSION (keeping $VERSION)"

# Backup original
cp "$CHANGELOG" "${CHANGELOG}.backup"

# Remove all pre-release entries for this version EXCEPT the current one
awk -v base="$BASE_VERSION" -v current="$VERSION" '
BEGIN { skip = 0 }

# Match pre-release headers for this version
$0 ~ "^# NAAS " base "(a|b|rc)[0-9]+ " {
    # Extract the version from the line
    match($0, /NAAS ([0-9]+\.[0-9]+\.[0-9]+(a|b|rc)[0-9]+)/, ver)
    if (ver[1] == current) {
        # Keep the current version
        skip = 0
    } else {
        # Skip older pre-releases
        skip = 1
        next
    }
}

# Stop skipping when we hit any other release header
/^# NAAS [0-9]+\.[0-9]+\.[0-9]+/ {
    skip = 0
}

# Print lines that aren'\''t being skipped
!skip { print }
' "${CHANGELOG}.backup" > "$CHANGELOG"

# Verify the file is not empty and still has the current version
if ! grep -q "^# NAAS $VERSION" "$CHANGELOG"; then
    echo "ERROR: Version entry missing after cleanup!"
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
