"""Migrações de advancements (Snapshot 4)."""
from __future__ import annotations

from typing import Any

from ..core.scanner import FileType
from ..core.engine import register
from ..core.engine import MigrationResult


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
        trigger = criterion.get("trigger", "")
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

        if trigger in PLAYER_CONTEXT_TRIGGERS:
            value = conditions.get("player")
            if isinstance(value, dict) and value and not _is_context_aware(value):
                conditions["player"] = _player_to_context(value, result)
                result.add_change(
                    f"Convertido 'player' do criterion '{name}' para ContextAwarePredicate"
                )
    return data


def _entity_to_context(entity: dict, result: MigrationResult) -> dict:
    """Converter entity predicate inline para ContextAwarePredicate (all_of)."""
    terms = []
    ep = {}
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
    renamed = {}
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
                    result.add_change(
                        f"Desempacotado '{key}' do criterion '{name}'"
                    )
                else:
                    conditions[key] = {"type": "minecraft:all_of", "terms": value}
                    result.add_change(
                        f"Convertido '{key}' do criterion '{name}' para all_of"
                    )
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
"""Base para migrações schema-driven."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MigrationResult:
    """Resultado de uma migração aplicada a um arquivo."""
    changes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_change(self, description: str):
        self.changes.append(description)

    def add_warning(self, description: str):
        self.warnings.append(description)


def get_nested(data: Any, path: tuple[object, ...]) -> Any | None:
    """Navega um caminho em estrutura dict/list.

    Retorna None se o caminho não existir. Suporta:
    - chaves de dict
    - índices de list
    - '*' como wildcard (percorre todos os elementos de lista/itens de dict)
    """
    current = data
    for key in path:
        if current is None:
            return None
        if key == "*":
            return current  # o chamador trata o wildcard
        if isinstance(current, dict):
            current = current.get(key)
        elif isinstance(current, list):
            if isinstance(key, int) and 0 <= key < len(current):
                current = current[key]
            else:
                return None
        else:
            return None
    return current


def set_nested(data: Any, path: tuple[object, ...], value: Any) -> bool:
    """Define um valor em um caminho. Retorna True se bem-sucedido."""
    if not path:
        return False
    parent_path = path[:-1]
    final_key = path[-1]

    parent = _resolve_parent(data, parent_path)
    if parent is None:
        return False

    if isinstance(parent, dict):
        if final_key == "*":
            return False
        parent[final_key] = value
        return True
    if isinstance(parent, list):
        if isinstance(final_key, int) and 0 <= final_key < len(parent):
            parent[final_key] = value
            return True
        return False
    return False


def del_nested(data: Any, path: tuple[object, ...]) -> bool:
    """Remove um valor em um caminho. Retorna True se bem-sucedido."""
    if not path:
        return False
    parent_path = path[:-1]
    final_key = path[-1]

    parent = _resolve_parent(data, parent_path)
    if parent is None:
        return False

    if isinstance(parent, dict):
        if final_key == "*" or final_key not in parent:
            return False
        del parent[final_key]
        return True
    if isinstance(parent, list):
        if isinstance(final_key, int) and 0 <= final_key < len(parent):
            del parent[final_key]
            return True
        return False
    return False


def _resolve_parent(data: Any, path: tuple[object, ...]) -> Any | None:
    """Resolve o nó pai para um caminho dado."""
    current = data
    for key in path:
        if current is None:
            return None
        if key == "*":
            return current
        if isinstance(current, dict):
            current = current.get(key)
        elif isinstance(current, list):
            if isinstance(key, int) and 0 <= key < len(current):
                current = current[key]
            else:
                return None
        else:
            return None
    return current


def walk_list_items(data: Any, list_path: tuple[object, ...]) -> list[tuple[tuple[object, ...], Any]]:
    """Para um caminho com '*' no final, retorna todos os itens com seus caminhos.

    Ex: ("pools", "*") → [((pools, 0), {...}), ((pools, 1), {...}), ...]
    """
    collection = get_nested(data, list_path)
    if not isinstance(collection, list):
        return []
    return [(list_path + (i,), item) for i, item in enumerate(collection)]


def walk_dict_values(data: Any, path: tuple[object, ...]) -> list[tuple[tuple[object, ...], Any]]:
    """Para um caminho que leva a um dict, retorna todos os valores com suas chaves."""
    node = get_nested(data, path)
    if not isinstance(node, dict):
        return []
    return [(path + (k,), v) for k, v in node.items()]
"""Migrações de blocks.json (Snapshot 2)."""
from __future__ import annotations

from typing import Any

from ..core.scanner import FileType
from ..core.engine import register
from ..core.engine import MigrationResult


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
"""Migrações de data components (Snapshot 7)."""
from __future__ import annotations

from typing import Any

from ..core.scanner import FileType
from ..core.engine import register
from ..core.engine import MigrationResult


@register("snapshot7", [FileType.PREDICATE, FileType.ADVANCEMENT, FileType.LOOT_TABLE, FileType.ITEM_MODIFIER, FileType.ENCHANTMENT, FileType.RECIPE])
def replace_swing_animation(data: Any, result: MigrationResult) -> Any:
    """Substituir minecraft:swing_animation por attack/interact_animation (S7-02).

    A migração adiciona attack_animation e interact_animation com type: whack
    (o default vanila) quando swing_animation é encontrado.
    """
    if not isinstance(data, dict):
        return data
    if "minecraft:swing_animation" in data:
        old_value = data.pop("minecraft:swing_animation")
        # Se o valor antigo tiver type e duration, preservar
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


@register("snapshot7", [FileType.PREDICATE, FileType.ADVANCEMENT, FileType.LOOT_TABLE, FileType.ITEM_MODIFIER, FileType.ENCHANTMENT, FileType.RECIPE])
def remove_map_color(data: Any, result: MigrationResult) -> Any:
    """Remover minecraft:map_color de data components (S7-03)."""
    if not isinstance(data, dict):
        return data
    if "minecraft:map_color" in data:
        del data["minecraft:map_color"]
        result.add_change("Removido minecraft:map_color (descontinuado)")
    return data
"""Migrações de decorated pot (Snapshot 1)."""
from __future__ import annotations

from typing import Any

from ..core.scanner import FileType
from ..core.engine import register
from ..core.engine import MigrationResult


def _migrate_sherd_list_to_object(sherds: list) -> dict[str, Any]:
    """Converter lista de sherds para objeto com campos direcionais.

    Formato antigo: ["minecraft:brick", "minecraft:angler", ...]
    Formato novo: {"back": {...}, "left": {...}, "right": {...}, "front": {...}}
    """
    result = {}
    positions = ["back", "left", "right", "front"]
    for i, sherd in enumerate(sherds):
        if i >= 4:
            break
        if isinstance(sherd, str):
            result[positions[i]] = {"id": sherd, "count": 1}
        elif isinstance(sherd, dict):
            result[positions[i]] = sherd
    return result


@register("snapshot1", [FileType.PREDICATE, FileType.ADVANCEMENT, FileType.LOOT_TABLE, FileType.ITEM_MODIFIER, FileType.ENCHANTMENT, FileType.RECIPE])
def migrate_pot_decorations(data: Any, result: MigrationResult) -> Any:
    """Migrar minecraft:pot_decorations de lista para objeto (S1-01).

    Lista de 4 IDs → objeto {back, left, right, front}.
    """
    if not isinstance(data, dict):
        return data
    for key in ("minecraft:pot_decorations", "pot_decorations"):
        if key in data and isinstance(data[key], list):
            data[key] = _migrate_sherd_list_to_object(data[key])
            result.add_change("Convertido minecraft:pot_decorations de lista para objeto")
    return data


@register("snapshot1", [FileType.PREDICATE, FileType.ADVANCEMENT, FileType.LOOT_TABLE, FileType.ITEM_MODIFIER, FileType.ENCHANTMENT, FileType.RECIPE])
def migrate_decorated_pot_sherds(data: Any, result: MigrationResult) -> Any:
    """Migrar campo sherds de decorated_pot (S1-02).

    Lista de 4 IDs → objeto {back, left, right, front}.
    """
    if not isinstance(data, dict):
        return data
    if "sherds" in data and isinstance(data["sherds"], list):
        data["sherds"] = _migrate_sherd_list_to_object(data["sherds"])
        result.add_change("Convertido campo 'sherds' de lista para objeto")
    return data
"""Migrações de loot tables (Snapshot 4 + Snapshot 7)."""
from __future__ import annotations

from typing import Any

from ..core.scanner import FileType
from ..core.engine import register
from ..core.engine import MigrationResult


def _migrate_condition(cond: Any, result: MigrationResult) -> Any:
    """Migrar uma condição individual: condition → type."""
    if not isinstance(cond, dict):
        return cond
    if "condition" in cond and "type" not in cond and "function" not in cond:
        cond["type"] = cond.pop("condition")
        result.add_change("Renomeado 'condition' → 'type' em condição")
    return cond


def _migrate_conditions_field(obj: dict, field: str, result: MigrationResult, where: str):
    """Migrar campo conditions → condition em um objeto (pool, entry, function)."""
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
    """Migrar campo functions → modifier em um objeto (pool, entry)."""
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
    """Migrar uma loot function individual: function → type, conditions → condition."""
    if not isinstance(func, dict):
        return func
    # function → type
    if "function" in func and "type" not in func:
        func["type"] = func.pop("function")
        result.add_change("Renomeado 'function' → 'type' em loot function")
    # conditions → condition (dentro da function)
    _migrate_conditions_field(func, "conditions", result, "loot function")
    return func


def _migrate_entry(entry: Any, result: MigrationResult):
    """Migrar uma loot pool entry."""
    if not isinstance(entry, dict):
        return
    # conditions → condition
    _migrate_conditions_field(entry, "conditions", result, "entry")
    # functions → modifier
    _migrate_functions_field(entry, result, "entry")
    # functions dentro de modifier (se for sequence)
    modifier = entry.get("modifier")
    if isinstance(modifier, dict) and "functions" in modifier:
        for fn in modifier["functions"]:
            _migrate_function(fn, result)
    elif isinstance(modifier, list):
        for fn in modifier:
            _migrate_function(fn, result)
    # Recursão em children/entries
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
        # Migrar functions dentro de modifier do pool
        modifier = pool.get("modifier")
        if isinstance(modifier, dict) and "functions" in modifier:
            for fn in modifier["functions"]:
                _migrate_function(fn, result)
        # Entries
        for entry in pool.get("entries", []):
            _migrate_entry(entry, result)
    return data


@register("snapshot4", [FileType.LOOT_TABLE])
def migrate_loot_function_type(data: Any, result: MigrationResult) -> Any:
    """Migrar function → type em loot functions (S4-16).

    Percorre todas as functions em modifier/sequence.
    """
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
                if "name" in modifier:
                    del modifier["name"]
    return data


@register("snapshot4", [FileType.LOOT_TABLE])
def migrate_exploration_map_destination(data: Any, result: MigrationResult) -> Any:
    """Tornar destination obrigatório em minecraft:exploration_map (S4-18).

    Se destination não estiver presente, adicionar valor padrão.
    """
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
            modifier = entry.get("modifier")
            if isinstance(modifier, dict) and modifier.get("type") == "minecraft:exploration_map":
                if "map_color" in modifier:
                    del modifier["map_color"]
                    result.add_change("Removido campo 'map_color' de exploration_map")
                # Atualizar item de map para filled_map
                if entry.get("type") == "minecraft:item" and entry.get("name") == "minecraft:map":
                    entry["name"] = "minecraft:filled_map"
                    result.add_change("Atualizado item de minecraft:map para minecraft:filled_map")
    return data


@register("snapshot4", [FileType.LOOT_TABLE])
def remove_minecraft_reference_loot(data: Any, result: MigrationResult) -> Any:
    """Remover minecraft:reference de loot functions (S4-04)."""
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
            if isinstance(modifier, dict) and modifier.get("type") == "minecraft:reference":
                if "name" in modifier:
                    entry["modifier"] = modifier["name"]
                    result.add_change(f"Substituído minecraft:reference por: {modifier['name']}")
    return data
"""Migrações de mcfunction (Snapshot 7)."""
from __future__ import annotations

import re
from typing import Any

from ..core.scanner import FileType
from ..core.engine import register
from ..core.engine import MigrationResult


_BLOCK_STATE_TEXT_RE = re.compile(
    r'\{\s*"Name"\s*:\s*"([^"]+)"\s*,\s*"Properties"\s*:'
)
_BLOCK_STATE_SIMPLE_TEXT_RE = re.compile(
    r'\{\s*"Name"\s*:\s*"(minecraft:[^"]+)"\s*\}'
)


@register("snapshot7", [FileType.MCFUNCTION])
def rename_block_state_in_text(content: str, result: MigrationResult) -> str:
    """Renomear Name → id e Properties → properties em block states no texto (S7-01).

    Aplica-se a arquivos .mcfunction que contêm representações de block state.
    """
    changes = []

    def repl_with_properties(match):
        changes.append(match.group(1))
        return f'{{"id": "{match.group(1)}", "properties":'

    def repl_simple(match):
        changes.append(match.group(1))
        return f'{{"id": "{match.group(1)}"}}'

    new_content = _BLOCK_STATE_TEXT_RE.sub(repl_with_properties, content)
    new_content = _BLOCK_STATE_SIMPLE_TEXT_RE.sub(repl_simple, new_content)

    if changes:
        result.add_change(
            f"Renomeado 'Name' → 'id' e 'Properties' → 'properties' "
            f"em block state ({len(changes)}x)"
        )
    return new_content
"""Migrações de predicates de poção (Snapshot 3) e outros predicates."""
from __future__ import annotations

from typing import Any

from ..core.scanner import FileType
from ..core.engine import register
from ..core.engine import MigrationResult


@register("snapshot3", [FileType.PREDICATE, FileType.ADVANCEMENT,
                         FileType.LOOT_TABLE, FileType.ITEM_MODIFIER])
def migrate_potion_contents_predicate(data: Any, result: MigrationResult) -> Any:
    """Migrar minecraft:potion_contents de lista para objeto (S3-01).

    Formato antigo: ["potion1", "potion2"]
    Formato novo: {"potions": ["potion1", "potion2"], "effects": {...}, "size": N}

    A migração converte lista em {potions: [...]}. Campos effects/size não
    existiam no formato antigo, então não podem ser inferidos.
    """
    if not isinstance(data, dict):
        return data
    value = data.get("minecraft:potion_contents")
    if isinstance(value, (list, str)):
        new_value: dict[str, Any] = {}
        if isinstance(value, str):
            new_value["potions"] = [value]
        else:
            new_value["potions"] = value
        data["minecraft:potion_contents"] = new_value
        result.add_change(
            "Convertido minecraft:potion_contents para objeto {potions: [...]}"
        )
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

    # killer → attacker, direct_killer → direct_attacker, killer_player → attacking_player (S4-09)
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

    # sheep.color removal (S4-11) — após rename, procurar em type_specific/sheep
    for key in ("sheep", "minecraft:type_specific/sheep"):
        sheep = ep.get(key)
        if isinstance(sheep, dict) and "color" in sheep:
            del sheep["color"]
            result.add_change("Removido campo 'color' de predicate de sheep")

    # Recursão em campos de entity aninhados
    nested_fields = (
        "attacker", "direct_attacker", "attacking_player",
        "passenger", "vehicle", "targeted_entity", "root_vehicle",
    )
    for fld in nested_fields:
        if isinstance(ep.get(fld), dict):
            _restructure_entity_predicate(ep[fld], result)


@register("snapshot4", [FileType.PREDICATE, FileType.ADVANCEMENT,
                         FileType.LOOT_TABLE, FileType.ITEM_MODIFIER])
def restructure_entity_predicates(data: Any, result: MigrationResult) -> Any:
    """Reestruturar entity predicates dentro de wrappers (S4-08 a S4-11).

    Aplica-se recursivamente: percorre o JSON e transforma todo
    entity_properties.wrapper.predicate encontrado.
    """
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
    """Converter listas de predicates em minecraft:all_of explícito (S4-06).

    Aplica-se à raiz do arquivo predicate quando é uma lista,
    ou a campos 'terms' de all_of.
    """
    if isinstance(data, list) and data and all(isinstance(item, dict) for item in data):
        # Raiz é uma lista de predicates → all_of
        new_data = {"type": "minecraft:all_of", "terms": []}
        for item in data:
            new_item = rename_condition_to_type(item, result) or item
            new_data["terms"].append(new_item)
        result.add_change("Convertida lista raiz em minecraft:all_of explícito")
        return new_data
    return data


@register("snapshot4", [FileType.PREDICATE, FileType.ADVANCEMENT,
                         FileType.LOOT_TABLE, FileType.ITEM_MODIFIER,
                         FileType.PREDICATE, FileType.ADVANCEMENT, FileType.LOOT_TABLE, FileType.ITEM_MODIFIER])
def convert_block_state_property(data: Any, result: MigrationResult) -> Any:
    """Converter minecraft:block_state_property → minecraft:match_block (S4-07).

    Mapeia:
    - condition/type: block_state_property → match_block
    - block → blocks
    - properties → state
    """
    if not isinstance(data, dict):
        return data

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
        result.add_condition("Convertido block_state_property → match_block")
    return data


@register("snapshot4", [FileType.PREDICATE, FileType.ITEM_MODIFIER,
                         FileType.ADVANCEMENT, FileType.LOOT_TABLE])
def remove_minecraft_reference(data: Any, result: MigrationResult) -> Any:
    """Substituir minecraft:reference por referência direta (S4-03).

    Aplica-se a qualquer objeto {type: "minecraft:reference", name: "..."}.
    """
    if not isinstance(data, dict):
        return data
    if data.get("type") == "minecraft:reference" and isinstance(data.get("name"), str):
        ref_name = data["name"]
        result.add_change(f"Substituído minecraft:reference por referência direta: {ref_name}")
        return ref_name
    return data


def _ensure_entity_properties_default(data: dict, result: MigrationResult):
    """Adicionar type: minecraft:entity_properties quando implícito (S4-02).

    Aplica-se apenas à raiz de arquivos predicate, quando o dict tem
    'entity' e 'predicate' mas não tem 'type' nem 'condition'.
    """
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
"""Migrações de slot sources (Snapshot 4)."""
from __future__ import annotations

from typing import Any

from ..core.scanner import FileType
from ..core.engine import register
from ..core.engine import MigrationResult


@register("snapshot4", [FileType.PREDICATE, FileType.ADVANCEMENT, FileType.LOOT_TABLE, FileType.ITEM_MODIFIER, FileType.ENCHANTMENT, FileType.RECIPE])
def remove_minecraft_reference_slot_source(data: Any, result: MigrationResult) -> Any:
    """Remover minecraft:reference de slot sources (S4-05)."""
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
"""Migrações de tags (Snapshot 3, 4, 7)."""
from __future__ import annotations

from typing import Any

from ..core.scanner import FileType
from ..core.engine import register
from ..core.engine import MigrationResult


@register("snapshot3", [FileType.TAG])
def rename_dowses_campfires_tag(data: Any, result: MigrationResult) -> Any:
    """Renomear #dowses_campfires → #douses_campfiles (S3-02).

    Aplica-se ao conteúdo do arquivo de tag e ao nome do arquivo.
    """
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
def remove_map_color_component(data: Any, result: MigrationResult) -> Any:
    """Remover minecraft:map_color de data components (S7-03).

    Aplica-se a qualquer arquivo que referencie o componente.
    """
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
"""Migrações de trim materials (Snapshot 1)."""
from __future__ import annotations

from typing import Any

from ..core.scanner import FileType
from ..core.engine import register
from ..core.engine import MigrationResult


@register("snapshot1", [FileType.PREDICATE, FileType.ADVANCEMENT, FileType.LOOT_TABLE, FileType.ITEM_MODIFIER, FileType.ENCHANTMENT, FileType.RECIPE])
def rename_trim_asset_name(data: Any, result: MigrationResult) -> Any:
    """Renomear asset_name → palette em trim materials (S1-03)."""
    if not isinstance(data, dict):
        return data
    if "asset_name" in data and "palette" not in data:
        data["palette"] = data.pop("asset_name")
        result.add_change("Renomeado 'asset_name' → 'palette' em trim_material")
    return data


@register("snapshot1", [FileType.PREDICATE, FileType.ADVANCEMENT, FileType.LOOT_TABLE, FileType.ITEM_MODIFIER, FileType.ENCHANTMENT, FileType.RECIPE])
def remove_override_armor_assets(data: Any, result: MigrationResult) -> Any:
    """Remover override_armor_assets de trim materials (S1-04).

    Overrides agora ficam no Resource Pack (Equipment Asset).
    """
    if not isinstance(data, dict):
        return data
    if "override_armor_assets" in data:
        del data["override_armor_assets"]
        result.add_change("Removido 'override_armor_assets' de trim_material")
    return data
"""Migrações datapack 26.2 → 26.3.

Cada módulo contém funções de migração ancoradas em caminhos exatos
do esquema, eliminando falsos positivos e negativos.

Worldgen foi excluído do escopo.
"""
from . import (
    blocks,
    tags,
    trim,
    decorated_pot,
    loot_table,
    predicate,
    advancement,
    mcfunction,
    data_components,
    slot_source,
)

__all__ = [
    "blocks",
    "tags",
    "trim",
    "decorated_pot",
    "loot_table",
    "predicate",
    "advancement",
    "mcfunction",
    "data_components",
    "slot_source",
]
