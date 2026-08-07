"""Regras de migração adicionais da Snapshot 4 (pack format 111.0)."""
from __future__ import annotations

from typing import Any

from .base import Rule, RuleResult, RuleType


class LootConditionToType(Rule):
    rule_id = "loot_condition_to_type"
    description = "Renomear 'condition' → 'type' em condições aninhadas de loot tables"
    snapshot_version = "snapshot4"
    target_types = [RuleType.LOOT_TABLE]

    POOL_KEYS = ("entries", "rolls", "bonus_rolls")

    def matches(self, data: Any, file_type: RuleType) -> bool:
        if not isinstance(data, dict):
            return False
        if "condition" not in data or "type" in data:
            return False
        if "function" in data:
            return False
        # Pools e entries usam 'condition' como nome do campo (formato novo);
        # não converter nesse nível — só em objetos de condição aninhados.
        if any(k in data for k in self.POOL_KEYS):
            return False
        return True

    def apply(self, data: Any, file_type: RuleType) -> RuleResult:
        result = RuleResult()
        if self.matches(data, file_type):
            data["type"] = data.pop("condition")
            result.add_change("Renomeado 'condition' → 'type' em condição de loot table")
        return result


class NumberProviderMinMaxToUniform(Rule):
    rule_id = "number_provider_min_max_to_uniform"
    description = "Adicionar 'type': minecraft:uniform a providers de rolls/bonus_rolls (dicts com min/max)"
    snapshot_version = "snapshot4"
    target_types = [RuleType.LOOT_TABLE, RuleType.ITEM_MODIFIER]

    # Campos cujo valor deve ser um NumberProvider. Dicts com min/max em
    # outros contextos (ex: predicates de distance, level) NÃO devem virar
    # uniform — só os do NumberProvider de rolls/bonus_rolls dos pools.
    PROVIDER_FIELDS = {"rolls", "bonus_rolls", "count"}

    def matches(self, data: Any, file_type: RuleType) -> bool:
        if not isinstance(data, dict):
            return False
        if "min" not in data or "max" not in data:
            return False
        if "type" in data:
            return False
        if "condition" in data or "function" in data:
            return False
        return self.context.is_key(*self.PROVIDER_FIELDS)

    def apply(self, data: Any, file_type: RuleType) -> RuleResult:
        result = RuleResult()
        if self.matches(data, file_type):
            data["type"] = "minecraft:uniform"
            result.add_change("Adicionado 'type': minecraft:uniform a provider implícito")
        return result


class EnchantmentConditionToType(Rule):
    rule_id = "enchantment_condition_to_type"
    description = "Renomear 'condition' → 'type' em enchantments (requirements de effects)"
    snapshot_version = "snapshot4"
    target_types = [RuleType.ENCHANTMENT]

    def matches(self, data: Any, file_type: RuleType) -> bool:
        if not isinstance(data, dict):
            return False
        if "condition" not in data or "type" in data:
            return False
        if "function" in data:
            return False
        return True

    def apply(self, data: Any, file_type: RuleType) -> RuleResult:
        result = RuleResult()
        if self.matches(data, file_type):
            data["type"] = data.pop("condition")
            result.add_change("Renomeado 'condition' → 'type' em requirements de enchantment")
        return result


class LootTagEntryNameToItems(Rule):
    rule_id = "loot_tag_entry_name_to_items"
    description = "Converter 'name' → 'items' em loot pool entries do tipo tag"
    snapshot_version = "snapshot4"
    target_types = [RuleType.LOOT_TABLE]

    def matches(self, data: Any, file_type: RuleType) -> bool:
        if not isinstance(data, dict):
            return False
        pools = data.get("pools", [])
        for pool in pools:
            if not isinstance(pool, dict):
                continue
            for entry in pool.get("entries", []):
                if not isinstance(entry, dict):
                    continue
                if entry.get("type") == "minecraft:tag" and "name" in entry:
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
                if entry.get("type") == "minecraft:tag" and "name" in entry:
                    old_name = entry["name"]
                    if not old_name.startswith("#"):
                        entry["items"] = f"#{old_name}"
                    else:
                        entry["items"] = old_name
                    del entry["name"]
                    result.add_change(f"Convertido 'name' → 'items' em loot tag entry: {old_name}")
        return result


class SingleObjectArrayUnwrap(Rule):
    rule_id = "single_object_array_unwrap"
    description = "Desempacotar arrays de um único dict em campos como location/entity/item"
    snapshot_version = "snapshot4"
    target_types = [
        RuleType.PREDICATE,
        RuleType.ADVANCEMENT,
        RuleType.ITEM_MODIFIER,
        RuleType.LOOT_TABLE,
    ]

    FIELDS = ("location", "entity", "item", "player", "vehicle", "passenger", "attacker",
              "direct_attacker", "attacking_player", "targeted_entity", "root_vehicle")

    def matches(self, data: Any, file_type: RuleType) -> bool:
        if not isinstance(data, dict):
            return False
        for field in self.FIELDS:
            value = data.get(field)
            if isinstance(value, list) and len(value) == 1 and isinstance(value[0], dict):
                return True
        return False

    def apply(self, data: Any, file_type: RuleType) -> RuleResult:
        result = RuleResult()
        if not self.matches(data, file_type):
            return result
        for field in self.FIELDS:
            value = data.get(field)
            if isinstance(value, list) and len(value) == 1 and isinstance(value[0], dict):
                data[field] = value[0]
                result.add_change(f"Desempacotado '{field}' de array para objeto")
        return result


EXTRA_RULES = [
    LootConditionToType(),
    NumberProviderMinMaxToUniform(),
    EnchantmentConditionToType(),
    LootTagEntryNameToItems(),
    SingleObjectArrayUnwrap(),
]
