"""Test script for running migrations on specific files."""
import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

import json
import argparse
from pathlib import Path

from migrator.core.scanner import FileType, classify_file
from migrator.core.engine import apply_migrations, MIGRATION_REGISTRY, SNAPSHOT_ORDER


def main():
    parser = argparse.ArgumentParser(description="Run migrations on a specific file")
    parser.add_argument("file", help="Path to the JSON or mcfunction file")
    parser.add_argument("--type", help="Force file type (loot_table, predicate, advancement, item_modifier, mcfunction, enchantment)")
    parser.add_argument("--snap", default="snapshot7", help="Target snapshot (default: snapshot7)")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    parser.add_argument("--list-types", action="store_true", help="List registered migrations per type")
    args = parser.parse_args()

    if args.list_types:
        print_registered_migrations()
        return

    src = Path(args.file)
    if not src.exists():
        print(f"ERROR: File not found: {src}")
        sys.exit(1)

    # Determine file type
    if args.type:
        file_type = FileType(args.type)
    else:
        rel = src.relative_to(src.parent.parent) if len(src.parts) > 2 else src.name
        file_type = classify_file(rel)

    print(f"File: {src}")
    print(f"Type: {file_type.value}")
    print(f"Target: {args.snap}")
    print()

    # Read and parse
    if file_type == FileType.MCFUNCTION:
        content = src.read_text(encoding="utf-8")
        from migrator.core.engine import apply_text_migrations, MigrationResult
        result = MigrationResult()
        output = apply_text_migrations(content, file_type, args.snap, result)
        print("=== OUTPUT ===")
        print(output[:2000] if len(output) > 2000 else output)
        print()
        print(f"=== CHANGES ({len(result.changes)}) ===")
        for c in result.changes:
            print(f"  - {c}")
        if result.warnings:
            print(f"=== WARNINGS ({len(result.warnings)}) ===")
            for w in result.warnings:
                print(f"  ! {w}")
    else:
        data = json.loads(src.read_text(encoding="utf-8"))
        output, result = apply_migrations(data, file_type, args.snap)
        print("=== OUTPUT ===")
        print(json.dumps(output, indent=2, ensure_ascii=False)[:2000])
        print()
        print(f"=== CHANGES ({len(result.changes)}) ===")
        for c in result.changes:
            print(f"  - {c}")
        if result.warnings:
            print(f"=== WARNINGS ({len(result.warnings)}) ===")
            for w in result.warnings:
                print(f"  ! {w}")


def print_registered_migrations():
    """List all registered migrations."""
    print("=== Registered Migrations ===")
    for snap in SNAPSHOT_ORDER:
        entries = [(s, ft, fn) for (s, ft), fns in MIGRATION_REGISTRY.items() for fn in fns if s == snap]
        if entries:
            print(f"\n{snap}:")
            for s, ft, fn in entries:
                print(f"  {ft.value:15s} {fn.__name__}")


if __name__ == "__main__":
    main()
