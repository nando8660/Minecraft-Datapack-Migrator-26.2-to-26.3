"""Migrações de decorated pot (Snapshot 1)."""
from __future__ import annotations

from typing import Any

from ..core.scanner import FileType
from ..core.engine import register, MigrationResult

_ALL_TYPES = [FileType.PREDICATE, FileType.ADVANCEMENT, FileType.LOOT_TABLE,
              FileType.ITEM_MODIFIER, FileType.ENCHANTMENT, FileType.RECIPE]


def _migrate_sherd_list_to_object(sherds: list) -> dict[str, Any]:
    """Converter lista de sherds para objeto com campos direcionais."""
    result: dict[str, Any] = {}
    positions = ["back", "left", "right", "front"]
    for i, sherd in enumerate(sherds):
        if i >= 4:
            break
        if isinstance(sherd, str):
            result[positions[i]] = {"id": sherd, "count": 1}
        elif isinstance(sherd, dict):
            result[positions[i]] = sherd
    return result


@register("snapshot1", _ALL_TYPES)
def migrate_pot_decorations(data: Any, result: MigrationResult) -> Any:
    """Migrar minecraft:pot_decorations de lista para objeto (S1-01)."""
    if not isinstance(data, dict):
        return data
    for key in ("minecraft:pot_decorations", "pot_decorations"):
        if key in data and isinstance(data[key], list):
            data[key] = _migrate_sherd_list_to_object(data[key])
            result.add_change("Convertido minecraft:pot_decorations de lista para objeto")
    return data


@register("snapshot1", _ALL_TYPES)
def migrate_decorated_pot_sherds(data: Any, result: MigrationResult) -> Any:
    """Migrar campo sherds de decorated_pot (S1-02)."""
    if not isinstance(data, dict):
        return data
    if "sherds" in data and isinstance(data["sherds"], list):
        data["sherds"] = _migrate_sherd_list_to_object(data["sherds"])
        result.add_change("Convertido campo 'sherds' de lista para objeto")
    return data
