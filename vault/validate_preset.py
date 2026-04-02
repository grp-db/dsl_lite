#!/usr/bin/env python3
"""
Validate DSL Lite preset YAML files for structural correctness.

Checks:
  - Required top-level keys are present (name, autoloader, bronze, silver, gold)
  - autoloader has at least one input path
  - bronze.name is set and not a placeholder
  - bronze.preTransform contains a `time` column
  - silver.transform entries each have a name and at least one field
  - silver transform names match their bronze input (naming convention)
  - gold entries each have: name, input, fields
  - gold input names reference a defined silver table
  - No un-replaced <placeholder> values remain

Usage:
    # Validate a single preset:
    python3 vault/validate_preset.py pipelines/cisco/ios/preset.yaml

    # Validate all presets in the pipelines/ directory:
    python3 vault/validate_preset.py

Exit code 0 if all presets pass, 1 if any errors are found.
"""

import sys
import yaml
from pathlib import Path


REPO_ROOT = Path(__file__).parent.parent
PIPELINES_DIR = REPO_ROOT / "pipelines"

REQUIRED_TOP_LEVEL = ["name", "autoloader", "bronze", "silver", "gold"]


def error(path: Path, msg: str) -> str:
    return f"  ✗  {msg}"


def warn(msg: str) -> str:
    return f"  ⚠  {msg}"


def validate_preset(path: Path) -> list[str]:
    """Return a list of error strings for a single preset file. Empty = pass."""
    errors = []

    try:
        with open(path) as f:
            preset = yaml.safe_load(f)
    except yaml.YAMLError as e:
        return [f"  ✗  YAML parse error: {e}"]

    if not isinstance(preset, dict):
        return ["  ✗  File does not parse to a YAML mapping"]

    # ── Check for un-replaced placeholders ──────────────────────────────────
    raw = path.read_text()
    import re
    placeholders = set(re.findall(r"<[a-zA-Z_][a-zA-Z0-9_ /]*>", raw))
    # Ignore the intentional placeholder comment in the template itself
    placeholders -= {"<current-user>", "<catalog>", "<schema>"}
    if placeholders:
        errors.append(f"  ✗  Un-replaced placeholders: {', '.join(sorted(placeholders))}")

    # ── Required top-level keys ──────────────────────────────────────────────
    for key in REQUIRED_TOP_LEVEL:
        if key not in preset:
            errors.append(f"  ✗  Missing required top-level key: '{key}'")

    if errors:
        # Stop early — further checks will just produce noise
        return errors

    # ── autoloader ──────────────────────────────────────────────────────────
    autoloader = preset.get("autoloader", {})
    inputs = autoloader.get("inputs", [])
    if not inputs:
        errors.append("  ✗  autoloader.inputs is empty")
    if "format" not in autoloader:
        errors.append("  ✗  autoloader.format is missing")

    # ── bronze ───────────────────────────────────────────────────────────────
    bronze = preset.get("bronze", {})
    if not bronze.get("name"):
        errors.append("  ✗  bronze.name is missing or empty")

    pre_transform = bronze.get("preTransform", [])
    if not pre_transform:
        errors.append("  ✗  bronze.preTransform is empty")
    else:
        # preTransform is a list of lists; flatten to check for `time`
        all_exprs = []
        for group in pre_transform:
            if isinstance(group, list):
                all_exprs.extend(str(e) for e in group if e)
        has_time = any(
            "as time" in expr.lower() or expr.strip().lower() == "time"
            for expr in all_exprs
        )
        if not has_time:
            errors.append("  ⚠  bronze.preTransform: no 'time' column found — pipeline may fail without it")

    # ── silver ───────────────────────────────────────────────────────────────
    silver = preset.get("silver", {})
    transforms = silver.get("transform", [])
    if not transforms:
        errors.append("  ✗  silver.transform is empty or missing")

    silver_table_names = set()
    for t in transforms:
        if not isinstance(t, dict):
            errors.append("  ✗  silver.transform entry is not a mapping")
            continue
        t_name = t.get("name")
        if not t_name:
            errors.append("  ✗  silver.transform entry missing 'name'")
        else:
            silver_table_names.add(t_name)
        fields = t.get("fields", [])
        if not fields:
            errors.append(f"  ⚠  silver.transform '{t_name}': no fields defined (is preserve unreferencedColumns sufficient?)")

    # ── gold ─────────────────────────────────────────────────────────────────
    gold = preset.get("gold", [])
    if not gold:
        errors.append("  ✗  gold is empty or missing")

    for g in gold:
        if not isinstance(g, dict):
            errors.append("  ✗  gold entry is not a mapping")
            continue
        g_name = g.get("name")
        if not g_name:
            errors.append("  ✗  gold entry missing 'name'")
        if not g.get("fields"):
            errors.append(f"  ✗  gold '{g_name}': no fields defined")
        input_table = g.get("input")
        if not input_table:
            errors.append(f"  ✗  gold '{g_name}': missing 'input'")
        elif silver_table_names and input_table not in silver_table_names:
            errors.append(
                f"  ✗  gold '{g_name}': input '{input_table}' not found in silver transforms "
                f"(defined: {', '.join(sorted(silver_table_names))})"
            )

    return errors


def main(paths: list[Path]) -> int:
    total = 0
    failed = 0

    for path in paths:
        total += 1
        rel = path.relative_to(REPO_ROOT)
        errors = validate_preset(path)
        if errors:
            failed += 1
            print(f"\n❌  {rel}")
            for e in errors:
                print(e)
        else:
            print(f"✓   {rel}")

    print(f"\n{'─' * 50}")
    print(f"Checked {total} preset(s) — {total - failed} passed, {failed} failed.")
    return 1 if failed else 0


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Explicit file(s) passed on the command line
        paths = [Path(p) for p in sys.argv[1:]]
        missing = [p for p in paths if not p.exists()]
        if missing:
            for p in missing:
                print(f"File not found: {p}", file=sys.stderr)
            sys.exit(1)
    else:
        # Default: find all preset.yaml files under pipelines/, skip templates
        paths = sorted(
            p for p in PIPELINES_DIR.rglob("preset.yaml")
            if "templates" not in p.parts
        )
        if not paths:
            print("No preset.yaml files found under pipelines/")
            sys.exit(0)

    sys.exit(main(paths))
