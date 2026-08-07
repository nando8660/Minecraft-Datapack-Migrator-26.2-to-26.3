"""Migrações de trim materials (Snapshot 1)."""
from __future__ import annotations

from typing import Any

from ..core.scanner import FileType
from ..core.engine import register, MigrationResult

_ALL_TYPES = [FileType.PREDICATE, FileType.ADVANCEMENT, FileType.LOOT_TABLE,
              FileType.ITEM_MODIFIER, FileType.ENCHANTMENT, FileType.RECIPE]


@register("snapshot1", _ALL_TYPES)
def rename_trim_asset_name(data: Any, result: MigrationResult) -> Any:
    """Renomear asset_name → palette em trim materials (S1-03)."""
    if not isinstance(data, dict):
        return data
    if "asset_name" in data and "palette" not in data:
        data["palette"] = data.pop("asset_name")
        result.add_change("Renomeado 'asset_name' → 'palette' em trim_material")
    return data


@register("snapshot1", _ALL_TYPES)
def remove_override_armor_assets(data: Any, result: MigrationResult) -> Any:
    """Remover override_armor_assets de trim materials (S1-04)."""
    if not isinstance(data, dict):
        return data
    if "override_armor_assets" in data:
        del data["override_armor_assets"]
        result.add_change("Removido 'override_armor_assets' de trim_material")
    return data
