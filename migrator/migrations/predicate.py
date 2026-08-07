"""Migrações de predicates (Snapshot 3 e 4)."""
from __future__ import annotations

from typing import Any

from ..core.scanner import FileType
from ..core.engine import register, MigrationResult


@register("snapshot3", [FileType.PREDICATE, FileType.ADVANCEMENT,
                         FileType.LOOT_TABLE, FileType.ITEM_MODIFIER,
                         FileType.ENCHANTMENT])
def migrate_potion_contents_predicate(data: Any, result: MigrationResult) -> Any:
    """Migrar minecraft:potion_contents de string para objeto (S3-01) — recursivo."""
    if not isinstance(data, dict):
        return data
    if "minecraft:potion_contents" in data:
        value = data["minecraft:potion_contents"]
        if isinstance(value, str):
            data["minecraft:potion_contents"] = {"potions": [value]}
            result.add_change("Convertido minecraft:potion_contents string para objeto {potions: [...]}")
        elif isinstance(value, list):
            data["minecraft:potion_contents"] = {"potions": value}
            result.add_change("Convertido minecraft:potion_contents lista para objeto {potions: [...]}")
    for value in data.values():
        if isinstance(value, dict):
            migrate_potion_contents_predicate(value, result)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    migrate_potion_contents_predicate(item, result)
    return data


@register("snapshot4", [FileType.PREDICATE])
def rename_condition_to_type(data: Any, result: MigrationResult) -> Any:
    """Renomear 'condition' → 'type' em predicates (S4-01)."""
    if not isinstance(data, dict):
        return data
    if "condition" in data and "type" not in data and "function" not in data:
        data["type"] = data.pop("condition")
        result.add_change("Renomeado 'condition' → 'type'")
    return data


def _is_entity_properties(data: dict) -> bool:
    """Verifica se é um entity_properties wrapper válido."""
    t = data.get("type")
    return (
        t == "minecraft:entity_properties"
        or data.get("condition") == "minecraft:entity_properties"
    ) and isinstance(data.get("predicate"), dict)


def _restructure_entity_predicate(ep: dict, result: MigrationResult):
    """Reestrutura entity predicate (S4-08, S4-09, S4-10, S4-11)."""
    if not isinstance(ep, dict):
        return

    # type → minecraft:entity_type (S4-08)
    if "type" in ep and "minecraft:entity_type" not in ep:
        ep["minecraft:entity_type"] = ep.pop("type")
        result.add_change("Renomeado 'type' → 'minecraft:entity_type' em entity predicate")

    # killer → attacker, etc (S4-09)
    renames = {
        "killer": "attacker",
        "direct_killer": "direct_attacker",
        "killer_player": "attacking_player",
    }
    for old, new in renames.items():
        if old in ep:
            ep[new] = ep.pop(old)
            result.add_change(f"Renomeado '{old}' → '{new}' em entity predicate")

    # Sub-predicate renames (S4-10)
    sub_renames = {
        "lightning": "minecraft:type_specific/lightning",
        "fishing_hook": "minecraft:type_specific/fishing_hook",
        "player": "minecraft:type_specific/player",
        "raider": "minecraft:type_specific/raider",
        "sheep": "minecraft:type_specific/sheep",
        "slime": "minecraft:cube_mob",
    }
    for old, new in sub_renames.items():
        if old in ep:
            ep[new] = ep.pop(old)
            result.add_change(f"Renomeado sub-predicate '{old}' → '{new}'")

    # sheep.color removal (S4-11)
    for key in ("sheep", "minecraft:type_specific/sheep"):
        sheep = ep.get(key)
        if isinstance(sheep, dict) and "color" in sheep:
            del sheep["color"]
            result.add_change("Removido campo 'color' de predicate de sheep")

    # Recursão em entity fields aninhados
    for fld in ("attacker", "direct_attacker", "attacking_player",
                "passenger", "vehicle", "targeted_entity", "root_vehicle"):
        if isinstance(ep.get(fld), dict):
            _restructure_entity_predicate(ep[fld], result)


@register("snapshot4", [FileType.PREDICATE, FileType.ADVANCEMENT,
                         FileType.LOOT_TABLE, FileType.ITEM_MODIFIER])
def restructure_entity_predicates(data: Any, result: MigrationResult) -> Any:
    """Reestruturar entity predicates dentro de wrappers (S4-08 a S4-11)."""
    if isinstance(data, dict):
        if _is_entity_properties(data):
            _restructure_entity_predicate(data["predicate"], result)
        for value in data.values():
            restructure_entity_predicates(value, result)
    elif isinstance(data, list):
        for item in data:
            restructure_entity_predicates(item, result)
    return data


@register("snapshot4", [FileType.PREDICATE])
def convert_all_of_shorthand(data: Any, result: MigrationResult) -> Any:
    """Converter listas de predicates em minecraft:all_of explícito (S4-06)."""
    if isinstance(data, list) and data and all(isinstance(item, dict) for item in data):
        new_data: dict[str, Any] = {"type": "minecraft:all_of", "terms": []}
        for item in data:
            new_item = rename_condition_to_type(item, result)
            new_data["terms"].append(new_item if new_item is not None else item)
        result.add_change("Convertida lista raiz em minecraft:all_of explícito")
        return new_data
    return data


@register("snapshot4", [FileType.PREDICATE, FileType.ADVANCEMENT,
                         FileType.LOOT_TABLE, FileType.ITEM_MODIFIER])
def convert_block_state_property(data: Any, result: MigrationResult) -> Any:
    """Converter minecraft:block_state_property → minecraft:match_block (S4-07).

    Verifica tanto 'type' quanto 'condition' como discriminador.
    Aplica-se recursivamente a todo o JSON.
    """
    if isinstance(data, dict):
        t = data.get("type") or data.get("condition")
        if t == "minecraft:block_state_property":
            data["type"] = "minecraft:match_block"
            if "condition" in data:
                del data["condition"]
            if "block" in data:
                data["blocks"] = data.pop("block")
                result.add_change("Renomeado 'block' → 'blocks' em match_block")
            if "properties" in data:
                data["state"] = data.pop("properties")
                result.add_change("Renomeado 'properties' → 'state' em match_block")
            result.add_change("Convertido block_state_property → match_block")
        for value in data.values():
            convert_block_state_property(value, result)
    elif isinstance(data, list):
        for item in data:
            convert_block_state_property(item, result)
    return data


@register("snapshot4", [FileType.PREDICATE, FileType.ADVANCEMENT,
                         FileType.LOOT_TABLE, FileType.ITEM_MODIFIER,
                         FileType.ENCHANTMENT])
def rename_condition_to_type_recursive(data: Any, result: MigrationResult) -> Any:
    """Renomear 'condition' → 'type' recursivamente em predicates (S4-01).

    Renomeia apenas quando 'condition' parece ser um discriminador de tipo
    (o objeto tem outros campos de predicate como 'entity', 'predicate',
    'block', 'properties', etc.), NÃO quando é um nome de campo como
    pool.condition ou entry.condition.
    """
    if not isinstance(data, dict):
        return data
    if "condition" in data and "type" not in data and "function" not in data:
        # Verifica se parece um predicate wrapper (tem campos de predicate)
        predicate_indicators = {"entity", "predicate", "block", "blocks",
                                "properties", "state", "terms", "chance",
                                "term"}
        if any(ind in data for ind in predicate_indicators):
            data["type"] = data.pop("condition")
            result.add_change("Renomeado 'condition' → 'type'")
    for value in data.values():
        if isinstance(value, dict):
            rename_condition_to_type_recursive(value, result)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    rename_condition_to_type_recursive(item, result)
    return data


@register("snapshot4", [FileType.PREDICATE, FileType.ITEM_MODIFIER,
                         FileType.ADVANCEMENT, FileType.LOOT_TABLE])
def remove_minecraft_reference_recursive(data: Any, result: MigrationResult) -> Any:
    """Substituir minecraft:reference recursivamente (S4-03, S4-04, S4-05).

    Percorre o JSON e substitui qualquer {type/condition: "minecraft:reference", name: "X"}
    pelo string "X". Verifica tanto 'type' quanto 'condition' como discriminador.
    """
    if not isinstance(data, dict):
        return data
    for key, value in list(data.items()):
        if isinstance(value, dict):
            ref_type = value.get("type") or value.get("condition")
            if ref_type in ("minecraft:reference", "reference") and isinstance(value.get("name"), str):
                ref_name = value["name"]
                data[key] = ref_name
                result.add_change(f"Substituído minecraft:reference por: {ref_name}")
            else:
                remove_minecraft_reference_recursive(value, result)
        elif isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, dict):
                    ref_type = item.get("type") or item.get("condition")
                    if ref_type in ("minecraft:reference", "reference") and isinstance(item.get("name"), str):
                        ref_name = item["name"]
                        value[i] = ref_name
                        result.add_change(f"Substituído minecraft:reference por: {ref_name}")
                    else:
                        remove_minecraft_reference_recursive(item, result)
    return data


def _ensure_entity_properties_default(data: dict, result: MigrationResult):
    """Adicionar type: minecraft:entity_properties quando implícito (S4-02)."""
    if "type" in data or "condition" in data:
        return
    if "entity" in data and "predicate" in data:
        data["type"] = "minecraft:entity_properties"
        result.add_change("Adicionado 'type': minecraft:entity_properties")


@register("snapshot4", [FileType.PREDICATE])
def ensure_default_entity_properties_root(data: Any, result: MigrationResult) -> Any:
    """Adicionar tipo padrão apenas na raiz de predicates (S4-02)."""
    if isinstance(data, dict):
        _ensure_entity_properties_default(data, result)
    return data
