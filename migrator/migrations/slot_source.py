"""Migrações de slot sources e item modifiers (Snapshot 4)."""
from __future__ import annotations

from typing import Any

from ..core.scanner import FileType
from ..core.engine import register, MigrationResult

_ALL_TYPES = [FileType.PREDICATE, FileType.ADVANCEMENT, FileType.LOOT_TABLE,
              FileType.ITEM_MODIFIER, FileType.ENCHANTMENT, FileType.RECIPE]


@register("snapshot4", _ALL_TYPES)
def remove_minecraft_reference_slot_source(data: Any, result: MigrationResult) -> Any:
    """Remover minecraft:reference de slot sources e outros (S4-05)."""
    if not isinstance(data, dict):
        return data
    if data.get("type") == "minecraft:reference" and isinstance(data.get("name"), str):
        result.add_change(f"Substituído minecraft:reference por: {data['name']}")
        return data["name"]
    return data


@register("snapshot4", [FileType.ITEM_MODIFIER])
def migrate_item_modifier(data: Any, result: MigrationResult) -> Any:
    """Migrar item modifiers: conditions→condition, function→type, functions→modifier."""
    if not isinstance(data, list):
        data = [data]
    for modifier in data:
        if not isinstance(modifier, dict):
            continue
        # function → type
        if "function" in modifier and "type" not in modifier:
            modifier["type"] = modifier.pop("function")
            result.add_change("Renomeado 'function' → 'type' em item modifier")
        # conditions → condition
        if "conditions" in modifier:
            old = modifier.pop("conditions")
            if isinstance(old, list) and len(old) > 1:
                modifier["condition"] = {"type": "minecraft:all_of", "terms": old}
                result.add_change("Convertida lista de condições em all_of")
            elif isinstance(old, list) and len(old) == 1:
                modifier["condition"] = old[0]
                result.add_change("Renomeado 'conditions' → 'condition'")
            elif old:
                modifier["condition"] = old
        # functions → modifier
        if "functions" in modifier:
            old = modifier.pop("functions")
            if isinstance(old, list) and len(old) > 1:
                modifier["modifier"] = {"type": "minecraft:sequence", "functions": old}
                result.add_change("Convertida lista de funções em sequence")
            elif isinstance(old, list) and len(old) == 1:
                modifier["modifier"] = old[0]
                result.add_change("Renomeado 'functions' → 'modifier'")
            elif old:
                modifier["modifier"] = old
    return data
