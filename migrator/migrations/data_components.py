"""Migrações de data components (Snapshot 7)."""
from __future__ import annotations

from typing import Any

from ..core.scanner import FileType
from ..core.engine import register, MigrationResult

_ALL_TYPES = [FileType.PREDICATE, FileType.ADVANCEMENT, FileType.LOOT_TABLE,
              FileType.ITEM_MODIFIER, FileType.ENCHANTMENT, FileType.RECIPE]


@register("snapshot7", _ALL_TYPES)
def replace_swing_animation(data: Any, result: MigrationResult) -> Any:
    """Substituir minecraft:swing_animation por attack/interact_animation (S7-02)."""
    if not isinstance(data, dict):
        return data
    if "minecraft:swing_animation" in data:
        old_value = data.pop("minecraft:swing_animation")
        if isinstance(old_value, dict):
            anim_type = old_value.get("type", "whack")
            duration = old_value.get("duration", 6)
            data["minecraft:attack_animation"] = {"type": anim_type, "duration": duration}
            data["minecraft:interact_animation"] = {"type": anim_type, "duration": duration}
        else:
            data["minecraft:attack_animation"] = {"type": "whack", "duration": 6}
            data["minecraft:interact_animation"] = {"type": "whack", "duration": 6}
        result.add_change(
            "Substituído minecraft:swing_animation por "
            "attack_animation + interact_animation (whack)"
        )
    return data


@register("snapshot7", _ALL_TYPES)
def remove_map_color(data: Any, result: MigrationResult) -> Any:
    """Remover minecraft:map_color de data components (S7-03)."""
    if not isinstance(data, dict):
        return data
    if "minecraft:map_color" in data:
        del data["minecraft:map_color"]
        result.add_change("Removido minecraft:map_color (descontinuado)")
    return data
