#!/usr/bin/env python3
"""Generate Pydantic models from the NAAS OpenAPI spec.

Cleans spectree's hash-suffixed schema names before running datamodel-codegen.

Usage:
    uv run --package naas-client python packages/naas-client/scripts/generate_models.py
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SPEC_PATH = Path(__file__).resolve().parents[3] / "docs" / "swagger" / "openapi.json"
OUTPUT_PATH = Path(__file__).resolve().parents[1] / "naas_client" / "_generated.py"

# Spectree appends .<hash> to schema names (e.g. "JobResponse.c5eb086")
_HASH_RE = re.compile(r"\.[0-9a-f]{7}$")


def _clean_name(name: str) -> str:
    """Strip spectree hash suffix and flatten nested names."""
    # "ContextsResponse.c5eb086.ContextInfo" → "ContextInfo"
    # "JobResponse.c5eb086" → "JobResponse"
    parts = name.split(".")
    clean = [p for p in parts if not _HASH_RE.match(f".{p}")]
    return clean[-1] if clean else parts[-1]


def clean_spec(spec: dict) -> dict:
    """Remove spectree hash suffixes from all schema names and $ref paths."""
    raw = json.dumps(spec)

    # Build rename map from original → clean
    schemas = spec.get("components", {}).get("schemas", {})
    renames: dict[str, str] = {}
    for name in schemas:
        clean = _clean_name(name)
        renames[name] = clean

    # Replace longest names first to avoid partial prefix matches
    for original, clean in sorted(renames.items(), key=lambda x: len(x[0]), reverse=True):
        raw = raw.replace(
            f"#/components/schemas/{original}",
            f"#/components/schemas/{clean}",
        )

    result = json.loads(raw)

    # Rename the schema keys themselves
    old_schemas = result["components"]["schemas"]
    result["components"]["schemas"] = {renames.get(k, k): v for k, v in old_schemas.items()}

    return result


def main() -> None:
    if not SPEC_PATH.exists():
        print(f"OpenAPI spec not found at {SPEC_PATH}", file=sys.stderr)
        print("Run: cd packages/naas && uv run invoke export-spec", file=sys.stderr)
        sys.exit(1)

    spec = json.loads(SPEC_PATH.read_text())
    cleaned = clean_spec(spec)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(cleaned, f, indent=2)
        tmp_path = f.name

    cmd = [
        sys.executable,
        "-m",
        "datamodel_code_generator",
        "--input",
        tmp_path,
        "--output",
        str(OUTPUT_PATH),
        "--output-model-type",
        "pydantic_v2.BaseModel",
        "--target-python-version",
        "3.11",
        "--use-standard-collections",
        "--use-union-operator",
        "--field-constraints",
        "--snake-case-field",
        "--capitalise-enum-members",
        "--collapse-root-models",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    Path(tmp_path).unlink()

    if result.returncode != 0:
        print(f"datamodel-codegen failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)

    print(f"Generated {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
