"""Regras de migração da Snapshot 7 (pack format 115.0)."""
from __future__ import annotations

import re
from typing import Any

from .base import Rule, RuleResult, RuleType


_BLOCK_STATE_TEXT_RE = re.compile(
    r'\{\s*"Name"\s*:\s*"([^"]+)"\s*,\s*"Properties"\s*:'
)
_BLOCK_STATE_SIMPLE_TEXT_RE = re.compile(
    r'\{\s*"Name"\s*:\s*"(minecraft:[^"]+)"\s*\}'
)


class BlockStateFieldsRename(Rule):
    rule_id = "block_state_fields_rename"
    description = "Renomear 'Name' → 'id' e 'Properties' → 'properties' em block states"
    snapshot_version = "snapshot7"
    target_types = [RuleType.BLOCK_STATE, RuleType.ANY]

    def matches(self, data: Any, file_type: RuleType) -> bool:
        if not isinstance(data, dict):
            return False
        if "Properties" in data:
            return True
        name = data.get("Name")
        return isinstance(name, str) and name.startswith("minecraft:")

    def apply(self, data: Any, file_type: RuleType) -> RuleResult:
        result = RuleResult()
        if not isinstance(data, dict):
            return result
        if "Name" in data and "id" not in data:
            data["id"] = data.pop("Name")
            result.add_change("Renomeado 'Name' → 'id' em block state")
        if "Properties" in data and "properties" not in data:
            data["properties"] = data.pop("Properties")
            result.add_change("Renomeado 'Properties' → 'properties' em block state")
        return result

    def migrate_text(self, content: str) -> tuple[str, list[str]]:
        changes = []
        count = 0

        def repl_with_properties(match):
            nonlocal count
            count += 1
            return f'{{"id": "{match.group(1)}", "properties":'

        def repl_simple(match):
            nonlocal count
            count += 1
            return f'{{"id": "{match.group(1)}"}}'

        new_content = _BLOCK_STATE_TEXT_RE.sub(repl_with_properties, content)
        new_content = _BLOCK_STATE_SIMPLE_TEXT_RE.sub(repl_simple, new_content)
        if new_content != content:
            changes.append(
                f"Renomeado 'Name' → 'id' e 'Properties' → 'properties' "
                f"em block state ({count}x)"
            )
        return new_content, changes


class ExplorationMapItemChange(Rule):
    rule_id = "exploration_map_item_change"
    description = "Atualizar minecraft:exploration_map para usar filled_map"
    snapshot_version = "snapshot7"
    target_types = [RuleType.LOOT_TABLE]

    def _iter_funcs(self, value):
        """Percorre recursivamente um valor de modifier (dict/lista/sequence)."""
        if isinstance(value, dict):
            yield value
            for sub in ("functions", "modifier"):
                if sub in value:
                    for f in self._iter_funcs(value[sub]):
                        yield f
        elif isinstance(value, list):
            for item in value:
                for f in self._iter_funcs(item):
                    yield f

    def _is_exploration(self, func) -> bool:
        return isinstance(func, dict) and (
            func.get("function") == "minecraft:exploration_map"
            or func.get("type") == "minecraft:exploration_map"
        )

    def _entry_funcs(self, entry: dict):
        return entry.get("functions", entry.get("modifier", []))

    def matches(self, data: Any, file_type: RuleType) -> bool:
        if not isinstance(data, dict):
            return False
        pools = data.get("pools", [])
        for pool in pools:
            if not isinstance(pool, dict):
                continue
            for entry in pool.get("entries", []):
                if isinstance(entry, dict) and any(
                    self._is_exploration(f) for f in self._iter_funcs(self._entry_funcs(entry))
                ):
                    return True
        return False

    def apply(self, data: Any, file_type: RuleType) -> RuleResult:
        result = RuleResult()
        if not self.matches(data, file_type):
            return result

        pools = data.get("pools", [])
        for pool in pools:
            if not isinstance(pool, dict):
                continue
            for entry in pool.get("entries", []):
                if not isinstance(entry, dict):
                    continue

                funcs = list(self._iter_funcs(self._entry_funcs(entry)))
                has_exploration = any(self._is_exploration(f) for f in funcs)

                for func in funcs:
                    if self._is_exploration(func) and "map_color" in func:
                        del func["map_color"]
                        result.add_change("Removido campo 'map_color' de exploration_map")

                if has_exploration and entry.get("type") == "minecraft:item" \
                        and entry.get("name") == "minecraft:map":
                    entry["name"] = "minecraft:filled_map"
                    result.add_change("Atualizado item de minecraft:map para minecraft:filled_map")

        return result


class ExplorationMapDestinationTag(Rule):
    rule_id = "exploration_map_destination_tag"
    description = "Adicionar prefixo '#' ao campo 'destination' de minecraft:exploration_map"
    snapshot_version = "snapshot7"
    target_types = [RuleType.ANY]

    def matches(self, data: Any, file_type: RuleType) -> bool:
        if not isinstance(data, dict):
            return False
        is_exploration = data.get("function") == "minecraft:exploration_map" \
            or data.get("type") == "minecraft:exploration_map"
        return is_exploration and isinstance(data.get("destination"), str)

    def apply(self, data: Any, file_type: RuleType) -> RuleResult:
        result = RuleResult()
        if not self.matches(data, file_type):
            return result
        destination = data["destination"]
        if not destination.startswith("#"):
            data["destination"] = "#" + destination
            result.add_change(
                "Adicionado prefixo '#' ao destination de minecraft:exploration_map"
            )
        return result


class SwingAnimationReplace(Rule):
    rule_id = "swing_animation_replace"
    description = "Substituir minecraft:swing_animation por attack_animation/interact_animation"
    snapshot_version = "snapshot7"
    target_types = [RuleType.ANY]

    def matches(self, data: Any, file_type: RuleType) -> bool:
        if isinstance(data, dict):
            return "minecraft:swing_animation" in data
        return False

    def apply(self, data: Any, file_type: RuleType) -> RuleResult:
        result = RuleResult()
        if self.matches(data, file_type):
            if "minecraft:swing_animation" in data:
                del data["minecraft:swing_animation"]
                result.add_change("Removido minecraft:swing_animation (substituído por attack_animation/interact_animation)")
                result.add_warning("Requer revisão manual: adicionar attack_animation e/ou interact_animation conforme necessário")
        return result


SNAPSHOT7_RULES = [
    BlockStateFieldsRename(),
    ExplorationMapItemChange(),
    ExplorationMapDestinationTag(),
    SwingAnimationReplace(),
]
