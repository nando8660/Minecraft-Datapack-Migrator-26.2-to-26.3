"""Migrações de loot tables (Snapshot 4 + Snapshot 7)."""
from __future__ import annotations

from typing import Any

from ..core.scanner import FileType
from ..core.engine import register, MigrationResult

# Known standalone conditions (condition-only objects)
_STANDALONE_CONDITIONS = {
    "killed_by_player", "survives_explosion", "random_chance",
    "random_chance_with_looting", "entity_properties",
    "damage_source_properties", "location_check",
    "match_tool", "inverted", "all_of", "any_of",
    "time_check", "weather_check", "reference",
}


def _migrate_condition(cond: Any, result: MigrationResult) -> Any:
    """Migrar uma condição individual: condition → type."""
    if not isinstance(cond, dict):
        return cond
    if "condition" in cond and "type" not in cond and "function" not in cond:
        cond["type"] = cond.pop("condition")
        result.add_change("Renomeado 'condition' → 'type' em condição")
    return cond


def _migrate_conditions_field(obj: dict, field: str, result: MigrationResult, where: str):
    """Migrar campo conditions → condition em um objeto."""
    if field not in obj:
        return
    old = obj[field]
    if isinstance(old, list):
        migrated = [_migrate_condition(c, result) for c in old]
        if len(migrated) > 1:
            obj["condition"] = {"type": "minecraft:all_of", "terms": migrated}
            result.add_change(f"Convertida lista de condições em all_of ({where})")
        elif len(migrated) == 1:
            obj["condition"] = migrated[0]
            result.add_change(f"Renomeado '{field}' → 'condition' ({where})")
        else:
            result.add_change(f"Removido campo '{field}' vazio ({where})")
    elif isinstance(old, dict):
        obj["condition"] = _migrate_condition(old, result)
        result.add_change(f"Renomeado '{field}' → 'condition' ({where})")
    else:
        obj["condition"] = old
    del obj[field]


def _migrate_functions_field(obj: dict, result: MigrationResult, where: str):
    """Migrar campo functions → modifier em um objeto."""
    if "functions" not in obj:
        return
    old = obj["functions"]
    if isinstance(old, list) and len(old) > 1:
        obj["modifier"] = {"type": "minecraft:sequence", "functions": old}
        result.add_change(f"Convertida lista de funções em sequence ({where})")
    elif isinstance(old, list) and len(old) == 1:
        obj["modifier"] = old[0]
        result.add_change(f"Renomeado 'functions' → 'modifier' ({where})")
    elif old:
        obj["modifier"] = old
        result.add_change(f"Renomeado 'functions' → 'modifier' ({where})")
    else:
        result.add_change(f"Removido campo 'functions' vazio ({where})")
    del obj["functions"]


def _migrate_function(func: Any, result: MigrationResult) -> Any:
    """Migrar uma loot function individual."""
    if not isinstance(func, dict):
        return func
    if "function" in func and "type" not in func:
        func["type"] = func.pop("function")
        result.add_change("Renomeado 'function' → 'type' em loot function")
    _migrate_conditions_field(func, "conditions", result, "loot function")
    return func


def _migrate_entry(entry: Any, result: MigrationResult):
    """Migrar uma loot pool entry."""
    if not isinstance(entry, dict):
        return
    _migrate_conditions_field(entry, "conditions", result, "entry")
    _migrate_functions_field(entry, result, "entry")
    modifier = entry.get("modifier")
    if isinstance(modifier, dict) and "functions" in modifier:
        for fn in modifier["functions"]:
            _migrate_function(fn, result)
    for sub in ("children", "entries"):
        if isinstance(entry.get(sub), list):
            for child in entry[sub]:
                _migrate_entry(child, result)


@register("snapshot4", [FileType.LOOT_TABLE])
def migrate_loot_pools(data: Any, result: MigrationResult) -> Any:
    """Migrar loot pools: conditions→condition, functions→modifier (S4-12, S4-13)."""
    if not isinstance(data, dict):
        return data
    pools = data.get("pools", [])
    if not isinstance(pools, list):
        return data
    for pool in pools:
        if not isinstance(pool, dict):
            continue
        _migrate_conditions_field(pool, "conditions", result, "pool")
        _migrate_functions_field(pool, result, "pool")
        modifier = pool.get("modifier")
        if isinstance(modifier, dict) and "functions" in modifier:
            for fn in modifier["functions"]:
                _migrate_function(fn, result)
        for entry in pool.get("entries", []):
            _migrate_entry(entry, result)
    return data


@register("snapshot4", [FileType.LOOT_TABLE])
def migrate_loot_function_type(data: Any, result: MigrationResult) -> Any:
    """Migrar function → type em loot functions (S4-16)."""
    if not isinstance(data, dict):
        return data
    pools = data.get("pools", [])
    for pool in pools:
        if not isinstance(pool, dict):
            continue
        modifier = pool.get("modifier")
        if isinstance(modifier, dict):
            _migrate_function(modifier, result)
            if "functions" in modifier:
                for fn in modifier["functions"]:
                    _migrate_function(fn, result)
        for entry in pool.get("entries", []):
            entry_mod = entry.get("modifier")
            if isinstance(entry_mod, dict):
                _migrate_function(entry_mod, result)
                if "functions" in entry_mod:
                    for fn in entry_mod["functions"]:
                        _migrate_function(fn, result)
    return data


@register("snapshot4", [FileType.LOOT_TABLE])
def migrate_loot_tag_entry(data: Any, result: MigrationResult) -> Any:
    """Migrar name → items em loot pool entries do tipo tag (S4-14)."""
    if not isinstance(data, dict):
        return data
    pools = data.get("pools", [])
    for pool in pools:
        if not isinstance(pool, dict):
            continue
        for entry in pool.get("entries", []):
            if not isinstance(entry, dict):
                continue
            if entry.get("type") == "minecraft:tag" and "name" in entry:
                old_name = entry["name"]
                if not old_name.startswith("#"):
                    entry["items"] = f"#{old_name}"
                else:
                    entry["items"] = old_name
                del entry["name"]
                result.add_change(f"Convertido 'name' → 'items' em loot tag entry: {old_name}")
    return data


@register("snapshot4", [FileType.LOOT_TABLE])
def migrate_set_loot_table(data: Any, result: MigrationResult) -> Any:
    """Migrar name → tag em minecraft:set_loot_table (S4-17)."""
    if not isinstance(data, dict):
        return data
    pools = data.get("pools", [])
    for pool in pools:
        if not isinstance(pool, dict):
            continue
        for entry in pool.get("entries", []):
            if not isinstance(entry, dict):
                continue
            modifier = entry.get("modifier")
            if isinstance(modifier, dict) and modifier.get("type") == "minecraft:set_loot_table":
                if "name" in modifier:
                    modifier["tag"] = modifier.pop("name")
                    result.add_change("Renomeado 'name' → 'tag' em set_loot_table")
    return data


@register("snapshot4", [FileType.LOOT_TABLE])
def migrate_exploration_map_destination(data: Any, result: MigrationResult) -> Any:
    """Tornar destination obrigatório em minecraft:exploration_map (S4-18)."""
    if not isinstance(data, dict):
        return data
    pools = data.get("pools", [])
    for pool in pools:
        if not isinstance(pool, dict):
            continue
        for entry in pool.get("entries", []):
            if not isinstance(entry, dict):
                continue
            modifier = entry.get("modifier")
            if isinstance(modifier, dict) and modifier.get("type") == "minecraft:exploration_map":
                if "destination" not in modifier:
                    modifier["destination"] = "minecraft:monument"
                    result.add_warning("Adicionado destination padrão (minecraft:monument) em exploration_map")
    return data


@register("snapshot7", [FileType.LOOT_TABLE])
def migrate_exploration_map_s7(data: Any, result: MigrationResult) -> Any:
    """Remover map_color de exploration_map e atualizar item (S7-04, S7-05)."""
    if not isinstance(data, dict):
        return data
    pools = data.get("pools", [])
    for pool in pools:
        if not isinstance(pool, dict):
            continue
        for entry in pool.get("entries", []):
            if not isinstance(entry, dict):
                continue
            # Verificar modifier e functions dentro de sequences
            _migrate_exploration_map_in_entry(entry, result)
    return data


def _migrate_exploration_map_in_entry(entry: dict, result: MigrationResult):
    """Migrar exploration_map dentro de um entry (incluindo sequences)."""
    modifier = entry.get("modifier")
    if isinstance(modifier, dict):
        if modifier.get("type") == "minecraft:exploration_map":
            _fix_exploration_map(modifier, entry, result)
        elif modifier.get("type") == "minecraft:sequence":
            for fn in modifier.get("functions", []):
                if isinstance(fn, dict) and fn.get("type") == "minecraft:exploration_map":
                    _fix_exploration_map(fn, entry, result)


def _fix_exploration_map(func: dict, entry: dict, result: MigrationResult):
    """Corrigir uma exploration_map function específica."""
    if "map_color" in func:
        del func["map_color"]
        result.add_change("Removido campo 'map_color' de exploration_map")
    if entry.get("type") == "minecraft:item" and entry.get("name") == "minecraft:map":
        entry["name"] = "minecraft:filled_map"
        result.add_change("Atualizado item de minecraft:map para minecraft:filled_map")


@register("snapshot4", [FileType.LOOT_TABLE])
def fix_pool_type_to_condition(data: Any, result: MigrationResult) -> Any:
    """Corrigir 'type' que deveria ser 'condition' em pools (S4-pool-fix).

    Se um pool tem 'type' mas não tem 'entries' com esse tipo,
    provavelmente é uma condition que foi nomeada incorretamente.
    """
    if not isinstance(data, dict):
        return data
    pools = data.get("pools", [])
    if not isinstance(pools, list):
        return data
    for pool in pools:
        if not isinstance(pool, dict):
            continue
        # Se tem 'type' mas não é um tipo de pool válido, converter para condition
        if "type" in pool and "condition" not in pool:
            type_val = pool["type"]
            # Verificar se parece uma condition (referência a predicate)
            if isinstance(type_val, str) and "_conditions" in type_val:
                pool["condition"] = pool.pop("type")
                result.add_change(f"Convertido 'type' → 'condition' em pool: {type_val}")
    return data


@register("snapshot4", [FileType.LOOT_TABLE])
def fix_exploration_map_destination(data: Any, result: MigrationResult) -> Any:
    """Adicionar prefixo '#' ao destination de exploration_map (S4-map-fix).

    Destinations que referenciam structures/tags precisam de '#' prefix.
    """
    if not isinstance(data, dict):
        return data
    pools = data.get("pools", [])
    if not isinstance(pools, list):
        return data
    for pool in pools:
        if not isinstance(pool, dict):
            continue
        for entry in pool.get("entries", []):
            if not isinstance(entry, dict):
                continue
            modifier = entry.get("modifier")
            if isinstance(modifier, dict) and modifier.get("type") == "minecraft:exploration_map":
                dest = modifier.get("destination")
                if isinstance(dest, str) and not dest.startswith("#"):
                    modifier["destination"] = f"#{dest}"
                    result.add_change(f"Adicionado '#' prefix ao destination: {dest}")
            # Verificar functions em sequences
            if isinstance(modifier, dict) and modifier.get("type") == "minecraft:sequence":
                for fn in modifier.get("functions", []):
                    if isinstance(fn, dict) and fn.get("type") == "minecraft:exploration_map":
                        dest = fn.get("destination")
                        if isinstance(dest, str) and not dest.startswith("#"):
                            fn["destination"] = f"#{dest}"
                            result.add_change(f"Adicionado '#' prefix ao destination: {dest}")
    return data


@register("snapshot4", [FileType.LOOT_TABLE, FileType.PREDICATE,
                         FileType.ADVANCEMENT, FileType.ENCHANTMENT,
                         FileType.ITEM_MODIFIER])
def convert_damage_type_string_to_object(data: Any, result: MigrationResult) -> Any:
    """Converter damage_type de string para objeto com tags (S4-damage).

    Converte {"type":"minecraft:is_fall"} para {"type":{"tags":[{"id":"#minecraft:is_fall","expected":true}]}}.
    Se o type está no mesmo nível que "blocked", adiciona "is_direct".
    Também corrige ids em tags que precisam de '#' prefix.
    """
    if not isinstance(data, dict):
        return data

    if "type" in data and isinstance(data["type"], str):
        old_type = data["type"]
        # Verificar se parece um damage type reference
        # Específicos: is_fall, is_projectile, is_explosion, bypasses_shield, etc.
        # NÃO inclui: on_fire, attack_speed, attack_damage, etc.
        is_damage_type = (
            ":is_" in old_type
            or ":bypasses_" in old_type
            or old_type.startswith("is_")
            or old_type.startswith("bypasses_")
            or old_type.startswith("#")
        )
        if is_damage_type or "blocked" in data:
            tag_id = old_type if old_type.startswith("#") else f"#{old_type}"
            new_type: dict[str, Any] = {
                "tags": [{"id": tag_id, "expected": True}]
            }
            if "blocked" in data:
                new_type["is_direct"] = True
            data["type"] = new_type
            result.add_change(f"Convertido damage_type string '{old_type}' para objeto")

    # Corrigir ids em tags arrays (adicionar '#' prefix)
    if "tags" in data and isinstance(data["tags"], list):
        for tag in data["tags"]:
            if isinstance(tag, dict) and "id" in tag:
                tag_id = tag["id"]
                if isinstance(tag_id, str) and ":" in tag_id and not tag_id.startswith("#"):
                    tag["id"] = f"#{tag_id}"
                    result.add_change(f"Adicionado '#' prefix ao tag id: {tag_id}")

    for value in data.values():
        if isinstance(value, dict):
            convert_damage_type_string_to_object(value, result)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    convert_damage_type_string_to_object(item, result)
    return data


@register("snapshot4", [FileType.LOOT_TABLE, FileType.PREDICATE,
                         FileType.ADVANCEMENT, FileType.ENCHANTMENT,
                         FileType.ITEM_MODIFIER])
def unwrap_condition_arrays(data: Any, result: MigrationResult) -> Any:
    """Desempacotar arrays em fields de condição que deveriam ser objetos (S4-unwrap).

    Converte {"location":[{"type":"minecraft:match_tool",...}]} para
    {"location":{"type":"minecraft:match_tool",...}}.

    Se o array tem múltiplos items, wrap em all_of:
    {"location":[{...},{...}]} → {"location":{"type":"minecraft:all_of","terms":[{...},{...}]}}
    """
    if not isinstance(data, dict):
        return data

    condition_fields = {"location", "player", "entity", "item", "damage", "weapon", "tool"}
    for field in condition_fields:
        if field in data and isinstance(data[field], list):
            if len(data[field]) == 1:
                data[field] = data[field][0]
                result.add_change(f"Desempacotado array em '{field}'")
            elif len(data[field]) > 1:
                data[field] = {"type": "minecraft:all_of", "terms": data[field]}
                result.add_change(f"Wrap array de '{field}' em all_of")

    for value in data.values():
        if isinstance(value, dict):
            unwrap_condition_arrays(value, result)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    unwrap_condition_arrays(item, result)
    return data


@register("snapshot4", [FileType.LOOT_TABLE])
def fix_standalone_conditions(data: Any, result: MigrationResult) -> Any:
    """Renomear condition → type em condições standalone (S4-condition-fix).

    Converte {"condition":"killed_by_player"} para {"type":"killed_by_player"}.
    """
    if not isinstance(data, dict):
        return data

    if "condition" in data and "type" not in data:
        cond_val = data["condition"]
        if isinstance(cond_val, str) and cond_val.lower() in {"killed_by_player", "survives_explosion"}:
            data["type"] = data.pop("condition")
            result.add_change(f"Renomeado condition standalone → type: {data['type']}")

    for value in data.values():
        if isinstance(value, dict):
            fix_standalone_conditions(value, result)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    fix_standalone_conditions(item, result)
    return data
