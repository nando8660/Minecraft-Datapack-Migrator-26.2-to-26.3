"""Migrações de tags (Snapshot 3, 4, 7)."""
from __future__ import annotations

from typing import Any

from ..core.scanner import FileType
from ..core.engine import register, MigrationResult


@register("snapshot3", [FileType.TAG])
def rename_dowses_campfires_tag(data: Any, result: MigrationResult) -> Any:
    """Renomear #dowses_campfires → #douses_campfires (S3-02)."""
    if not isinstance(data, dict):
        return data
    values = data.get("values", [])
    if isinstance(values, list):
        new_values = []
        for v in values:
            if isinstance(v, str) and v == "minecraft:dowses_campfires":
                new_values.append("minecraft:douses_campfires")
                result.add_change("Renomeado #dowses_campfires → #douses_campfires")
            elif isinstance(v, str) and v == "#minecraft:dowses_campfires":
                new_values.append("#minecraft:douses_campfires")
                result.add_change("Renomeado #dowses_campfires → #douses_campfires")
            else:
                new_values.append(v)
        data["values"] = new_values
    return data


@register("snapshot4", [FileType.TAG])
def warn_brewing_fuel_removed(data: Any, result: MigrationResult) -> Any:
    """Avisar sobre remoção da tag #brewing_fuel (S4-26)."""
    if not isinstance(data, dict):
        return data
    values = data.get("values", [])
    if isinstance(values, list):
        for v in values:
            if isinstance(v, str) and "brewing_fuel" in v:
                result.add_warning(
                    "Tag #brewing_fuel foi removida na Snapshot 4. "
                    "Use o componente minecraft:brewing_fuel em vez disso."
                )
    return data


@register("snapshot7", [FileType.TAG])
def remove_map_color_tag(data: Any, result: MigrationResult) -> Any:
    """Remover minecraft:map_color de data components em tags (S7-03)."""
    if not isinstance(data, dict):
        return data
    if "minecraft:map_color" in data:
        del data["minecraft:map_color"]
        result.add_change("Removido minecraft:map_color (descontinuado)")
    return data


@register("snapshot3", [FileType.ADVANCEMENT, FileType.LOOT_TABLE,
                         FileType.ITEM_MODIFIER, FileType.PREDICATE])
def rename_dowses_campfires_references(data: Any, result: MigrationResult) -> Any:
    """Renomear referências a #dowses_campfires em qualquer arquivo (S3-02)."""
    if isinstance(data, str):
        if data in ("minecraft:dowses_campfires", "#minecraft:dowses_campfires"):
            result.add_change("Renomeado #dowses_campfires → #douses_campfires")
            return data.replace("dowses", "douses")
        return data
    if isinstance(data, dict):
        for k, v in list(data.items()):
            new_v = rename_dowses_campfires_references(v, result)
            if new_v is not v:
                data[k] = new_v
    elif isinstance(data, list):
        for i, item in enumerate(data):
            new_item = rename_dowses_campfires_references(item, result)
            if new_item is not item:
                data[i] = new_item
    return data
