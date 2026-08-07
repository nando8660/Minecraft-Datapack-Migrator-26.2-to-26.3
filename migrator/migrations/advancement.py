"""Migrações de advancements (Snapshot 4)."""
from __future__ import annotations

from typing import Any

from ..core.scanner import FileType
from ..core.engine import register, MigrationResult


TRIGGER_RENAMES = {
    "minecraft:bee_nest_destroyed": {"block": "blocks"},
    "minecraft:enter_block": {"block": "blocks"},
    "minecraft:slide_down_block": {"block": "blocks"},
    "minecraft:player_generates_container_loot": {"loot_table": "loot_tables"},
    "minecraft:recipe_unlocked": {"recipe": "recipes"},
    "minecraft:recipe_crafted": {"recipe_id": "recipes"},
    "minecraft:crafter_recipe_crafted": {"recipe_id": "recipes"},
}

PLAYER_CONTEXT_TRIGGERS = {"minecraft:entity_hurt_player"}


@register("snapshot4", [FileType.ADVANCEMENT])
def rename_advancement_trigger_fields(data: Any, result: MigrationResult) -> Any:
    """Renomear campos de triggers de advancement (S4-22, S4-23, S4-24)."""
    if not isinstance(data, dict):
        return data
    criteria = data.get("criteria")
    if not isinstance(criteria, dict):
        return data
    for name, criterion in criteria.items():
        if not isinstance(criterion, dict):
            continue
        trigger = criterion.get("trigger", "")
        renames = TRIGGER_RENAMES.get(trigger)
        if not renames:
            continue
        conditions = criterion.get("conditions")
        if not isinstance(conditions, dict):
            continue
        for old_key, new_key in renames.items():
            if old_key in conditions and new_key not in conditions:
                conditions[new_key] = conditions.pop(old_key)
                result.add_change(
                    f"Pluralizado '{old_key}' → '{new_key}' no criterion '{name}'"
                )
    return data


def _is_context_aware(value: Any) -> bool:
    """Verifica se um valor já é ContextAwarePredicate."""
    if not isinstance(value, dict):
        return False
    if "terms" in value:
        return True
    if "condition" in value or "type" in value:
        t = value.get("type", "")
        if isinstance(t, str) and t.startswith("minecraft:"):
            return True
    return False


def _is_condition_like(value: dict) -> bool:
    """Verifica se um valor é uma condition (não predicate).

    Conditions têm campos como 'chance' (random_chance),
    'type' com valores de condição (random_chance, killed_by_player, etc.),
    'condition', etc.

    NÃO inclui predicate fields como 'slots', 'equipment', 'flags', 'movement'.
    """
    # Se tem 'type' ou 'condition' como string com namespace de condição
    t = value.get("type") or value.get("condition")
    if isinstance(t, str):
        condition_types = {"random_chance", "killed_by_player", "survives_explosion",
                          "random_chance_with_looting", "entity_properties",
                          "damage_source_properties", "location_check", "match_tool",
                          "inverted", "all_of", "any_of", "reference"}
        if t in condition_types or (":" in t and t.split(":")[-1] in condition_types):
            return True
    # Se tem 'chance' (é random_chance ou similar)
    if "chance" in value:
        return True
    return False


@register("snapshot4", [FileType.ADVANCEMENT])
def convert_advancement_entity_fields(data: Any, result: MigrationResult) -> Any:
    """Converter campos de entity/player para ContextAwarePredicate (S4-20, S4-21)."""
    if not isinstance(data, dict):
        return data
    criteria = data.get("criteria")
    if not isinstance(criteria, dict):
        return data
    for name, criterion in criteria.items():
        if not isinstance(criterion, dict):
            continue
        conditions = criterion.get("conditions")
        if not isinstance(conditions, dict):
            continue
        for key in ("entity", "source_entity", "villager", "bystander"):
            value = conditions.get(key)
            if isinstance(value, dict) and value and not _is_context_aware(value):
                conditions[key] = _entity_to_context(value, result)
                result.add_change(
                    f"Convertido '{key}' do criterion '{name}' para ContextAwarePredicate"
                )
        # Converter player para entity_properties em TODOS os triggers
        # Mas apenas se o valor não é uma condition (chance, type, etc.)
        value = conditions.get("player")
        if isinstance(value, dict) and value and not _is_context_aware(value):
            if value.get("type") == "minecraft:entity_properties":
                continue
            # Não converter se é uma condition (tem chance, type, etc.)
            if _is_condition_like(value):
                continue
            conditions["player"] = _player_to_context(value, result)
            result.add_change(
                f"Convertido 'player' do criterion '{name}' para ContextAwarePredicate"
            )
    return data


def _entity_to_context(entity: dict, result: MigrationResult) -> dict:
    """Converter entity predicate inline para ContextAwarePredicate (all_of)."""
    terms: list[dict[str, Any]] = []
    ep: dict[str, Any] = {}
    location = None
    for key, value in entity.items():
        if key == "location":
            location = value
        else:
            ep[key] = value
    if ep:
        terms.append({"type": "minecraft:entity_properties", "entity": "this", "predicate": ep})
    if location is not None:
        loc = dict(location)
        if "biomes" in loc:
            loc["biomes"] = _normalize_biomes(loc["biomes"])
        terms.append({"type": "minecraft:location_check", "predicate": loc})
    return {"type": "minecraft:all_of", "terms": terms}


def _player_to_context(raw: dict, result: MigrationResult) -> dict:
    """Converter player predicate inline para entity_properties."""
    return {
        "type": "minecraft:entity_properties",
        "entity": "this",
        "predicate": _prefix_player_sub_predicates(raw),
    }


def _prefix_player_sub_predicates(predicate: dict) -> dict:
    """Adicionar prefixo minecraft: a sub-predicates de player."""
    renamed: dict[str, Any] = {}
    player_subs = ("slots", "equipment", "flags", "movement")
    for key, value in predicate.items():
        if key in player_subs:
            renamed[f"minecraft:{key}"] = value
        else:
            renamed[key] = value
    return renamed


def _normalize_biomes(biomes: Any) -> Any:
    """Normalizar biomes removendo prefixo minecraft: (exceto tags)."""
    if isinstance(biomes, str):
        if biomes.startswith("#"):
            return biomes
        return biomes.replace("minecraft:", "") if biomes.startswith("minecraft:") else biomes
    if isinstance(biomes, list):
        return [_normalize_biomes(b) for b in biomes]
    return biomes


@register("snapshot4", [FileType.ADVANCEMENT])
def convert_advancement_list_conditions(data: Any, result: MigrationResult) -> Any:
    """Converter listas de condições em all_of explícito (S4-21)."""
    if not isinstance(data, dict):
        return data
    criteria = data.get("criteria")
    if not isinstance(criteria, dict):
        return data
    context_keys = (
        "player", "entity", "source_entity", "villager", "bystander",
        "killing_blow", "damage",
    )
    for name, criterion in criteria.items():
        if not isinstance(criterion, dict):
            continue
        conditions = criterion.get("conditions")
        if not isinstance(conditions, dict):
            continue
        for key in context_keys:
            value = conditions.get(key)
            if isinstance(value, list) and value and all(isinstance(v, dict) for v in value):
                if len(value) == 1:
                    conditions[key] = value[0]
                    result.add_change(f"Desempacotado '{key}' do criterion '{name}'")
                else:
                    conditions[key] = {"type": "minecraft:all_of", "terms": value}
                    result.add_change(f"Convertido '{key}' do criterion '{name}' para all_of")
    return data


@register("snapshot3", [FileType.ADVANCEMENT])
def rename_bed_rule_field(data: Any, result: MigrationResult) -> Any:
    """Renomear explodes → destroy_on_use em bed_rule (S3-03)."""
    if not isinstance(data, dict):
        return data
    if data.get("type") == "minecraft:gameplay/bed_rule":
        if "explodes" in data:
            data["destroy_on_use"] = data.pop("explodes")
            result.add_change("Renomeado 'explodes' → 'destroy_on_use' em bed_rule")
    return data
