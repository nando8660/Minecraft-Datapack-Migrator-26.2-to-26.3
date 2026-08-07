"""Migrações de blocks.json (Snapshot 2)."""
from __future__ import annotations

from typing import Any

from ..core.scanner import FileType
from ..core.engine import register, MigrationResult


@register("snapshot2", [FileType.BLOCKS])
def remove_definition(data: Any, result: MigrationResult) -> Any:
    """Remover campo 'definition' de blocks.json (S2-01)."""
    if not isinstance(data, dict):
        return data
    for ns, ns_data in list(data.items()):
        if isinstance(ns_data, dict) and "definition" in ns_data:
            del ns_data["definition"]
            result.add_change(
                f"Removido campo 'definition' do namespace '{ns}' em blocks.json"
            )
    return data
