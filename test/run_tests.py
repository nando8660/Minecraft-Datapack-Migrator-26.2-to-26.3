"""Regression test runner for migrations."""
import sys
import os
import json
import io
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from migrator.core.scanner import FileType
from migrator.core.engine import apply_migrations, MigrationResult
import migrator.migrations  # triggers @register decorators


TEST_DIR = Path(__file__).parent
CASES_DIR = TEST_DIR / "cases"
EXPECTED_DIR = TEST_DIR / "expected"

# Map file names to file types
FILE_TYPES = {
    "loot_table": FileType.LOOT_TABLE,
    "predicate": FileType.PREDICATE,
    "advancement": FileType.ADVANCEMENT,
    "item_modifier": FileType.ITEM_MODIFIER,
    "enchantment": FileType.ENCHANTMENT,
    "mcfunction": FileType.MCFUNCTION,
}


def get_file_type(filename: str) -> FileType:
    """Determine file type from filename prefix."""
    for prefix, ft in FILE_TYPES.items():
        if filename.startswith(prefix):
            return ft
    return FileType.LOOT_TABLE  # default


def run_test(case_file: Path) -> tuple[bool, str, list[str]]:
    """Run a single test case. Returns (passed, output, changes)."""
    expected_file = EXPECTED_DIR / case_file.name

    if not expected_file.exists():
        return False, f"Expected file not found: {expected_file}", []

    file_type = get_file_type(case_file.name)

    # Read input
    data = json.loads(case_file.read_text(encoding="utf-8"))

    # Run migrations
    output, result = apply_migrations(data, file_type, "snapshot7")

    # Read expected
    expected = json.loads(expected_file.read_text(encoding="utf-8"))

    # Compare
    output_json = json.dumps(output, sort_keys=True, ensure_ascii=False)
    expected_json = json.dumps(expected, sort_keys=True, ensure_ascii=False)

    if output_json == expected_json:
        return True, output_json, result.changes
    else:
        return False, f"MISMATCH:\nGot:      {output_json}\nExpected: {expected_json}", result.changes


def main():
    cases = sorted(CASES_DIR.glob("*.json"))
    if not cases:
        print("No test cases found!")
        return

    passed = 0
    failed = 0

    for case_file in cases:
        ok, output, changes = run_test(case_file)
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {case_file.name}")
        if not ok:
            print(f"  {output}")
            failed += 1
        else:
            if changes:
                for c in changes:
                    print(f"  -> {c}")
            passed += 1

    print(f"\n{'='*40}")
    print(f"Results: {passed} passed, {failed} failed, {passed + failed} total")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
