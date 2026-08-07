"""Regras de migração da Snapshot 4 (pack format 111.0)."""
from __future__ import annotations

from typing import Any

from .base import Rule, RuleResult, RuleType


class PredicateConditionToType(Rule):
    rule_id = "predicate_condition_to_type"
    description = "Renomear 'condition' → 'type' em predicates"
    snapshot_version = "snapshot4"
    target_types = [RuleType.PREDICATE, RuleType.ADVANCEMENT, RuleType.ITEM_MODIFIER]

    def matches(self, data: Any, file_type: RuleType) -> bool:
        if not isinstance(data, dict):
            return False
        if "condition" not in data or "type" in data:
            return False
        # Objetos de loot function usam 'function' como discriminador;
        # 'condition' neles é um campo, não o tipo do predicate.
        if "function" in data:
            return False
        return True

    def apply(self, data: Any, file_type: RuleType) -> RuleResult:
        result = RuleResult()
        if self.matches(data, file_type):
            data["type"] = data.pop("condition")
            result.add_change("Renomeado 'condition' → 'type'")
        # Wrapper implícito de entity predicate só na raiz de arquivos
        # de predicate — para não vazar para nodes aninhados.
        if file_type == RuleType.PREDICATE and not self.context.path:
            self.migrar_condicao_padrao(data, result)
        return result

    def migrar_condicao_padrao(self, data: dict, result: RuleResult):
        """Converte wrapper implícito de entity predicate para o formato
        explícito com 'type': minecraft:entity_properties.

        Só é aplicado quando o dict é claramente um entity predicate na
        forma antiga: possui 'entity' E 'predicate' no mesmo nível e não
        possui tampouco 'type'/'condition'.
        """
        if "type" in data or "condition" in data:
            return
        if "entity" in data and "predicate" in data:
            data["type"] = "minecraft:entity_properties"
            result.add_change("Adicionado 'type': minecraft:entity_properties")


class RemovePredicateReference(Rule):
    rule_id = "remove_predicate_reference"
    description = "Substituir reference por referência direta"
    snapshot_version = "snapshot4"
    target_types = [RuleType.ANY]

    REFERENCE_VALUES = ("reference", "minecraft:reference")
    DISCRIMINATORS = ("type", "function", "condition")

    def matches(self, data: Any, file_type: RuleType) -> bool:
        if not isinstance(data, dict):
            return False
        return any(data.get(key) in self.REFERENCE_VALUES for key in self.DISCRIMINATORS)

    def apply(self, data: Any, file_type: RuleType) -> RuleResult:
        result = RuleResult()
        if self.matches(data, file_type):
            name = data.get("name", "")
            if name:
                result.set_replacement(name)
                result.add_change(f"Substituído reference por referência direta: {name}")
            else:
                result.add_warning("reference sem campo 'name'; revisar manualmente")
        return result


class AllOfExplicit(Rule):
    rule_id = "all_of_explicit"
    description = "Listas inline devem usar minecraft:all_of explícito"
    snapshot_version = "snapshot4"
    target_types = [RuleType.PREDICATE]

    def matches(self, data: Any, file_type: RuleType) -> bool:
        if not isinstance(data, dict):
            return False
        if data.get("type") != "minecraft:all_of":
            return False
        terms = data.get("terms", [])
        return isinstance(terms, list) and any(isinstance(t, list) for t in terms)

    def apply(self, data: Any, file_type: RuleType) -> RuleResult:
        result = RuleResult()
        if self.matches(data, file_type):
            terms = data.get("terms", [])
            new_terms = []
            for term in terms:
                if isinstance(term, list):
                    wrapped = {"type": "minecraft:all_of", "terms": term}
                    new_terms.append(wrapped)
                    result.add_change("Convertida lista inline em minecraft:all_of explícito")
                else:
                    new_terms.append(term)
            data["terms"] = new_terms
        return result


class BlockStatePropertyToMatchBlock(Rule):
    rule_id = "block_state_property_to_match_block"
    description = "Converter minecraft:block_state_property → minecraft:match_block"
    snapshot_version = "snapshot4"
    target_types = [
        RuleType.PREDICATE,
        RuleType.ADVANCEMENT,
        RuleType.LOOT_TABLE,
        RuleType.ITEM_MODIFIER,
        RuleType.RECIPE,
    ]

    def matches(self, data: Any, file_type: RuleType) -> bool:
        if not isinstance(data, dict):
            return False
        return data.get("condition") == "minecraft:block_state_property" or \
               data.get("type") == "minecraft:block_state_property"

    def apply(self, data: Any, file_type: RuleType) -> RuleResult:
        result = RuleResult()
        if self.matches(data, file_type):
            data["type"] = "minecraft:match_block"
            if "condition" in data:
                del data["condition"]

            if "block" in data:
                data["blocks"] = data.pop("block")

            if "properties" in data:
                data["state"] = data.pop("properties")

            result.add_change("Convertido minecraft:block_state_property → minecraft:match_block")
        return result


class EntityPredicateRestructure(Rule):
    rule_id = "entity_predicate_restructure"
    description = "Reestruturar entity predicates (type → minecraft:entity_type, killer → attacker)"
    snapshot_version = "snapshot4"
    target_types = [
        RuleType.PREDICATE,
        RuleType.ADVANCEMENT,
        RuleType.LOOT_TABLE,
        RuleType.ITEM_MODIFIER,
    ]

    KILLER_RENAMES = {
        "killer": "attacker",
        "direct_killer": "direct_attacker",
        "killer_player": "attacking_player",
    }

    NESTED_ENTITY_FIELDS = (
        "attacker",
        "direct_attacker",
        "attacking_player",
        "passenger",
        "vehicle",
        "targeted_entity",
        "root_vehicle",
    )

    @staticmethod
    def _is_entity_properties_wrapper(data: dict) -> bool:
        return data.get("condition") == "minecraft:entity_properties" or \
               data.get("type") == "minecraft:entity_properties"

    def matches(self, data: Any, file_type: RuleType) -> bool:
        if not isinstance(data, dict):
            return False
        return self._is_entity_properties_wrapper(data) and isinstance(data.get("predicate"), dict)

    def _restructure(self, ep: dict, result: RuleResult):
        if not isinstance(ep, dict):
            return
        if "type" in ep and "minecraft:entity_type" not in ep:
            ep["minecraft:entity_type"] = ep.pop("type")
            result.add_change("Renomeado 'type' → 'minecraft:entity_type' em entity predicate")
        for old, new in self.KILLER_RENAMES.items():
            if old in ep:
                ep[new] = ep.pop(old)
                result.add_change(f"Renomeado '{old}' → '{new}' em entity predicate")
        for field in self.NESTED_ENTITY_FIELDS:
            if field in ep and isinstance(ep[field], dict):
                self._restructure(ep[field], result)

    def apply(self, data: Any, file_type: RuleType) -> RuleResult:
        result = RuleResult()
        if self.matches(data, file_type):
            self._restructure(data["predicate"], result)
            result.add_warning(
                "Entity predicate migrado; revisar manualmente "
                "(especialmente em advancements)"
            )
        return result


class EntitySubPredicateRename(Rule):
    rule_id = "entity_sub_predicate_rename"
    description = "Renomear sub-predicates de entity (player → minecraft:type_specific/player)"
    snapshot_version = "snapshot4"
    target_types = [
        RuleType.PREDICATE,
        RuleType.ADVANCEMENT,
        RuleType.LOOT_TABLE,
        RuleType.ITEM_MODIFIER,
    ]

    SUB_PREDICATE_MAP = {
        "lightning": "minecraft:type_specific/lightning",
        "fishing_hook": "minecraft:type_specific/fishing_hook",
        "player": "minecraft:type_specific/player",
        "raider": "minecraft:type_specific/raider",
        "sheep": "minecraft:type_specific/sheep",
        "slime": "minecraft:cube_mob",
    }

    def matches(self, data: Any, file_type: RuleType) -> bool:
        if not isinstance(data, dict):
            return False
        if not EntityPredicateRestructure._is_entity_properties_wrapper(data):
            return False
        ep = data.get("predicate")
        return isinstance(ep, dict) and any(k in ep for k in self.SUB_PREDICATE_MAP)

    def apply(self, data: Any, file_type: RuleType) -> RuleResult:
        result = RuleResult()
        if self.matches(data, file_type):
            ep = data["predicate"]
            for old, new in self.SUB_PREDICATE_MAP.items():
                if old in ep:
                    ep[new] = ep.pop(old)
                    result.add_change(f"Renomeado sub-predicate '{old}' → '{new}'")
        return result


class SheepColorRemove(Rule):
    rule_id = "sheep_color_remove"
    description = "Remover campo 'color' de predicates de sheep"
    snapshot_version = "snapshot4"
    target_types = [
        RuleType.PREDICATE,
        RuleType.ADVANCEMENT,
        RuleType.LOOT_TABLE,
        RuleType.ITEM_MODIFIER,
    ]

    def matches(self, data: Any, file_type: RuleType) -> bool:
        if not isinstance(data, dict):
            return False
        if not EntityPredicateRestructure._is_entity_properties_wrapper(data):
            return False
        ep = data.get("predicate")
        return isinstance(ep, dict) and isinstance(ep.get("sheep"), dict) and "color" in ep["sheep"]

    def apply(self, data: Any, file_type: RuleType) -> RuleResult:
        result = RuleResult()
        if self.matches(data, file_type):
            del data["predicate"]["sheep"]["color"]
            result.add_change("Removido campo 'color' de predicate de sheep")
        return result


class AdvancementTriggerToContextAware(Rule):
    rule_id = "advancement_trigger_to_context_aware"
    description = "Converter predicates de triggers de advancement em ContextAwarePredicate (all_of)"
    snapshot_version = "snapshot4"
    target_types = [RuleType.ADVANCEMENT]

    ENTITY_KEYS = ("entity", "source_entity", "villager", "bystander")
    DAMAGE_KEYS = ("killing_blow", "damage")

    CONTEXT_TYPES = {
        "all_of",
        "any_of",
        "entity_properties",
        "location_check",
        "damage_source_properties",
        "entity_scores",
        "item",
        "match_tool",
        "table_bonus",
        "random_chance",
        "random_chance_with_enchanted_bonus",
        "inverted",
        "check_event",
    }

    @staticmethod
    def _is_context(value: Any) -> bool:
        if not isinstance(value, dict):
            return False
        if "terms" in value:
            return True
        if "condition" in value:
            return True
        t = value.get("type")
        if not isinstance(t, str):
            return False
        return t.split(":", 1)[-1] in AdvancementTriggerToContextAware.CONTEXT_TYPES

    @staticmethod
    def _strip_minecraft_ns(rid: str) -> str:
        if rid.startswith("minecraft:"):
            return rid[len("minecraft:"):]
        return rid

    @classmethod
    def _normalize_biomes(cls, biomes: Any) -> Any:
        if isinstance(biomes, str):
            if biomes.startswith("#"):
                return biomes
            return [cls._strip_minecraft_ns(biomes)]
        if isinstance(biomes, list):
            return [
                cls._strip_minecraft_ns(b)
                if isinstance(b, str) and not b.startswith("#")
                else b
                for b in biomes
            ]
        return biomes

    @classmethod
    def _entity_to_context(cls, entity: dict) -> dict:
        terms = []
        ep = {}
        location = None
        for key, value in entity.items():
            if key == "location":
                location = value
            else:
                ep[key] = value
        if ep:
            terms.append({"type": "entity_properties", "entity": "this", "predicate": ep})
        if location is not None:
            loc = dict(location)
            if "biomes" in loc:
                biomes = cls._normalize_biomes(loc["biomes"])
                if biomes is not None:
                    loc["biomes"] = biomes
            terms.append({"type": "location_check", "predicate": loc})
        return {"type": "all_of", "terms": terms}

    @staticmethod
    def _damage_to_context(ds: dict) -> dict:
        return {
            "type": "all_of",
            "terms": [
                {"type": "damage_source_properties", "entity": "this", "predicate": ds}
            ],
        }

    PLAYER_CONTEXT_TRIGGERS = {"minecraft:entity_hurt_player"}
    PLAYER_SUB_PREDICATES = ("slots", "equipment", "flags", "movement")

    @classmethod
    def _prefix_player_sub_predicates(cls, predicate: dict) -> dict:
        renamed = {}
        for key, value in predicate.items():
            if key in cls.PLAYER_SUB_PREDICATES:
                renamed["minecraft:" + key] = value
            else:
                renamed[key] = value
        return renamed

    @classmethod
    def _player_to_context(cls, raw: dict) -> dict:
        return {
            "type": "minecraft:entity_properties",
            "entity": "this",
            "predicate": cls._prefix_player_sub_predicates(raw),
        }

    def _raw_values(self, conditions: dict, trigger: str):
        for key in self.ENTITY_KEYS:
            value = conditions.get(key)
            if isinstance(value, dict) and value and not self._is_context(value):
                yield key, value
        if trigger in self.PLAYER_CONTEXT_TRIGGERS:
            value = conditions.get("player")
            if isinstance(value, dict) and value and not self._is_context(value):
                yield "player", value

    def matches(self, data: Any, file_type: RuleType) -> bool:
        if file_type != RuleType.ADVANCEMENT or not isinstance(data, dict):
            return False
        criteria = data.get("criteria")
        if not isinstance(criteria, dict):
            return False
        for criterion in criteria.values():
            if not isinstance(criterion, dict):
                continue
            conditions = criterion.get("conditions")
            if not isinstance(conditions, dict):
                continue
            for _ in self._raw_values(conditions, criterion.get("trigger")):
                return True
        return False

    def apply(self, data: Any, file_type: RuleType) -> RuleResult:
        result = RuleResult()
        if file_type != RuleType.ADVANCEMENT or not isinstance(data, dict):
            return result
        criteria = data.get("criteria")
        if not isinstance(criteria, dict):
            return result
        for name, criterion in criteria.items():
            if not isinstance(criterion, dict):
                continue
            conditions = criterion.get("conditions")
            if not isinstance(conditions, dict):
                continue
            for key, value in list(self._raw_values(conditions, criterion.get("trigger"))):
                if key == "player":
                    conditions[key] = self._player_to_context(value)
                else:
                    conditions[key] = self._entity_to_context(value)
                result.add_change(
                    f"Convertido '{key}' do criterion '{name}' para ContextAwarePredicate"
                )
        return result


class AdvancementTriggerListToAllOf(Rule):
    rule_id = "advancement_trigger_list_to_all_of"
    description = "Converter listas de condições de campos de contexto de triggers em {type: all_of, terms}"
    snapshot_version = "snapshot4"
    target_types = [RuleType.ADVANCEMENT]

    CONTEXT_KEYS = (
        "player",
        "entity",
        "source_entity",
        "villager",
        "bystander",
        "killing_blow",
        "damage",
    )

    def _iter_conditions(self, data: Any, file_type: RuleType):
        if file_type != RuleType.ADVANCEMENT or not isinstance(data, dict):
            return
        criteria = data.get("criteria")
        if not isinstance(criteria, dict):
            return
        for name, criterion in criteria.items():
            if not isinstance(criterion, dict):
                continue
            conditions = criterion.get("conditions")
            if not isinstance(conditions, dict):
                continue
            for key in self.CONTEXT_KEYS:
                value = conditions.get(key)
                if isinstance(value, list) and value and all(
                    isinstance(v, dict) for v in value
                ):
                    yield name, conditions, key, value

    def matches(self, data: Any, file_type: RuleType) -> bool:
        for _ in self._iter_conditions(data, file_type):
            return True
        return False

    def apply(self, data: Any, file_type: RuleType) -> RuleResult:
        result = RuleResult()
        for name, conditions, key, value in self._iter_conditions(data, file_type):
            if len(value) == 1:
                conditions[key] = value[0]
                result.add_change(
                    f"Desempacotado '{key}' do criterion '{name}' (lista de 1 condição)"
                )
            else:
                conditions[key] = {"type": "all_of", "terms": value}
                result.add_change(
                    f"Convertido '{key}' do criterion '{name}' para {{type: all_of, terms}}"
                )
        return result


class AdvancementTriggerFieldPluralize(Rule):
    rule_id = "advancement_trigger_field_pluralize"
    description = "Pluralizar campos de condições de triggers de advancement (recipe → recipes, etc.)"
    snapshot_version = "snapshot4"
    target_types = [RuleType.ADVANCEMENT]

    TRIGGER_RENAMES = {
        "minecraft:recipe_unlocked": {"recipe": "recipes"},
        "minecraft:player_generates_container_loot": {"loot_table": "loot_tables"},
    }

    def matches(self, data: Any, file_type: RuleType) -> bool:
        if file_type != RuleType.ADVANCEMENT or not isinstance(data, dict):
            return False
        criteria = data.get("criteria")
        if not isinstance(criteria, dict):
            return False
        for criterion in criteria.values():
            if not isinstance(criterion, dict):
                continue
            renames = self.TRIGGER_RENAMES.get(criterion.get("trigger"))
            if not renames:
                continue
            conditions = criterion.get("conditions")
            if not isinstance(conditions, dict):
                continue
            if any(key in conditions for key in renames):
                return True
        return False

    def apply(self, data: Any, file_type: RuleType) -> RuleResult:
        result = RuleResult()
        if file_type != RuleType.ADVANCEMENT or not isinstance(data, dict):
            return result
        criteria = data.get("criteria")
        if not isinstance(criteria, dict):
            return result
        for name, criterion in criteria.items():
            if not isinstance(criterion, dict):
                continue
            renames = self.TRIGGER_RENAMES.get(criterion.get("trigger"))
            if not renames:
                continue
            conditions = criterion.get("conditions")
            if not isinstance(conditions, dict):
                continue
            for old, new in renames.items():
                if old in conditions and new not in conditions:
                    conditions[new] = conditions.pop(old)
                    result.add_change(
                        f"Pluralizado '{old}' → '{new}' no criterion '{name}'"
                    )
        return result


class LootPoolConditionsRename(Rule):
    rule_id = "loot_pool_conditions_rename"
    description = "Renomear 'conditions' → 'condition' em loot pools e entries"
    snapshot_version = "snapshot4"
    target_types = [RuleType.LOOT_TABLE]

    def _entry_has_conditions(self, entries: Any) -> bool:
        if not isinstance(entries, list):
            return False
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if "conditions" in entry:
                return True
            for sub in ("children", "entries"):
                if self._entry_has_conditions(entry.get(sub)):
                    return True
        return False

    def matches(self, data: Any, file_type: RuleType) -> bool:
        if not isinstance(data, dict):
            return False
        pools = data.get("pools", [])
        for pool in pools:
            if isinstance(pool, dict) and "conditions" in pool:
                return True
            if isinstance(pool, dict) and self._entry_has_conditions(pool.get("entries", [])):
                return True
        return False

    def _migrate_condition(self, cond, result: RuleResult):
        if isinstance(cond, dict):
            if "condition" in cond and "type" not in cond and "function" not in cond:
                cond["type"] = cond.pop("condition")
                result.add_change("Renomeado 'condition' → 'type' em condição aninhada")
        return cond

    def _migrate_entry_conditions(self, entries: Any, result: RuleResult):
        if not isinstance(entries, list):
            return
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if "conditions" in entry:
                old_conds = entry["conditions"]
                migrated_value: Any = None
                if isinstance(old_conds, list):
                    migrated = [self._migrate_condition(c, result) for c in old_conds]
                    if len(migrated) > 1:
                        migrated_value = {
                            "type": "minecraft:all_of",
                            "terms": migrated,
                        }
                        result.add_change("Convertida lista de condições em minecraft:all_of em entry")
                    elif len(migrated) == 1:
                        migrated_value = migrated[0]
                else:
                    migrated_value = self._migrate_condition(old_conds, result)
                if migrated_value:
                    entry["condition"] = migrated_value
                    result.add_change("Renomeado 'conditions' → 'condition' em entry")
                else:
                    result.add_change("Removido campo 'conditions' vazio em entry")
                del entry["conditions"]
            for sub in ("children", "entries"):
                self._migrate_entry_conditions(entry.get(sub), result)

    def apply(self, data: Any, file_type: RuleType) -> RuleResult:
        result = RuleResult()
        if not self.matches(data, file_type):
            return result

        pools = data.get("pools", [])
        for pool in pools:
            if not isinstance(pool, dict):
                continue

            if "conditions" in pool:
                old_conds = pool["conditions"]
                migrated_value: Any = None
                if isinstance(old_conds, list):
                    migrated = [self._migrate_condition(c, result) for c in old_conds]
                    if len(migrated) > 1:
                        migrated_value = {
                            "type": "minecraft:all_of",
                            "terms": migrated,
                        }
                        result.add_change("Convertida lista de condições em minecraft:all_of")
                    elif len(migrated) == 1:
                        migrated_value = migrated[0]
                else:
                    migrated_value = self._migrate_condition(old_conds, result)
                if migrated_value:
                    pool["condition"] = migrated_value
                    result.add_change("Renomeado 'conditions' → 'condition' em pool")
                else:
                    result.add_change("Removido campo 'conditions' vazio em pool")
                del pool["conditions"]

            self._migrate_entry_conditions(pool.get("entries", []), result)

        return result


class LootPoolFunctionsRename(Rule):
    rule_id = "loot_pool_functions_rename"
    description = "Renomear 'functions' → 'modifier' em loot pools e entries"
    snapshot_version = "snapshot4"
    target_types = [RuleType.LOOT_TABLE]

    def _entry_has_functions(self, entries: Any) -> bool:
        if not isinstance(entries, list):
            return False
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if "functions" in entry:
                return True
            for sub in ("children", "entries"):
                if self._entry_has_functions(entry.get(sub)):
                    return True
        return False

    def matches(self, data: Any, file_type: RuleType) -> bool:
        if not isinstance(data, dict):
            return False
        if "functions" in data and "pools" in data:
            return True
        pools = data.get("pools", [])
        for pool in pools:
            if isinstance(pool, dict) and "functions" in pool:
                return True
            if isinstance(pool, dict) and self._entry_has_functions(pool.get("entries", [])):
                return True
        return False

    def _migrate_entry_functions(self, entries: Any, result: RuleResult):
        if not isinstance(entries, list):
            return
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if "functions" in entry:
                old_funcs = entry["functions"]
                if isinstance(old_funcs, list) and len(old_funcs) > 1:
                    entry["modifier"] = {
                        "type": "minecraft:sequence",
                        "functions": old_funcs,
                    }
                    result.add_change("Convertida lista de funções em minecraft:sequence em entry")
                elif isinstance(old_funcs, list) and len(old_funcs) == 1:
                    entry["modifier"] = old_funcs[0]
                    result.add_change("Renomeado 'functions' → 'modifier' em entry")
                elif old_funcs:
                    entry["modifier"] = old_funcs
                    result.add_change("Renomeado 'functions' → 'modifier' em entry")
                else:
                    result.add_change("Removido campo 'functions' vazio em entry")
                del entry["functions"]
            for sub in ("children", "entries"):
                self._migrate_entry_functions(entry.get(sub), result)

    def apply(self, data: Any, file_type: RuleType) -> RuleResult:
        result = RuleResult()
        if not self.matches(data, file_type):
            return result

        if "functions" in data and "pools" in data:
            old_funcs = data["functions"]
            if isinstance(old_funcs, list) and len(old_funcs) > 1:
                data["modifier"] = {
                    "type": "minecraft:sequence",
                    "functions": old_funcs,
                }
                result.add_change("Convertida lista de funções em minecraft:sequence")
            elif isinstance(old_funcs, list) and len(old_funcs) == 1:
                data["modifier"] = old_funcs[0]
                result.add_change("Renomeado 'functions' → 'modifier' em loot table")
            elif old_funcs:
                data["modifier"] = old_funcs
                result.add_change("Renomeado 'functions' → 'modifier' em loot table")
            else:
                result.add_change("Removido campo 'functions' vazio em loot table")
            del data["functions"]

        pools = data.get("pools", [])
        for pool in pools:
            if not isinstance(pool, dict):
                continue

            if "functions" in pool:
                old_funcs = pool["functions"]
                if isinstance(old_funcs, list) and len(old_funcs) > 1:
                    pool["modifier"] = {
                        "type": "minecraft:sequence",
                        "functions": old_funcs,
                    }
                    result.add_change("Convertida lista de funções em minecraft:sequence")
                elif isinstance(old_funcs, list) and len(old_funcs) == 1:
                    pool["modifier"] = old_funcs[0]
                    result.add_change("Renomeado 'functions' → 'modifier' em pool")
                elif old_funcs:
                    pool["modifier"] = old_funcs
                    result.add_change("Renomeado 'functions' → 'modifier' em pool")
                else:
                    result.add_change("Removido campo 'functions' vazio em pool")
                del pool["functions"]

            self._migrate_entry_functions(pool.get("entries", []), result)

        return result


class LootFunctionConditionsRename(Rule):
    rule_id = "loot_function_conditions_rename"
    description = "Renomear 'conditions' → 'condition' em loot functions"
    snapshot_version = "snapshot4"
    target_types = [RuleType.LOOT_TABLE]

    def matches(self, data: Any, file_type: RuleType) -> bool:
        if not isinstance(data, dict):
            return False
        return "conditions" in data and ("function" in data or "type" in data)

    def apply(self, data: Any, file_type: RuleType) -> RuleResult:
        result = RuleResult()
        if not self.matches(data, file_type):
            return result

        def migrate_inner(cond):
            if isinstance(cond, dict):
                if "condition" in cond and "type" not in cond and "function" not in cond:
                    cond["type"] = cond.pop("condition")
                    result.add_change("Renomeado 'condition' → 'type' em condição aninhada")
            return cond

        old_conds = data["conditions"]
        migrated_value: Any = None
        if isinstance(old_conds, list):
            migrated = [migrate_inner(c) for c in old_conds]
            if len(migrated) > 1:
                migrated_value = {
                    "type": "minecraft:all_of",
                    "terms": migrated,
                }
                result.add_change("Convertida lista de condições em minecraft:all_of")
            elif len(migrated) == 1:
                migrated_value = migrated[0]
        else:
            migrated_value = migrate_inner(old_conds)
        if migrated_value:
            data["condition"] = migrated_value
            result.add_change("Renomeado 'conditions' → 'condition' em loot function")
        else:
            result.add_change("Removido campo 'conditions' vazio em loot function")
        del data["conditions"]
        return result


class LootFunctionTypeRename(Rule):
    rule_id = "loot_function_type_rename"
    description = "Renomear 'function' → 'type' em loot functions"
    snapshot_version = "snapshot4"
    target_types = [RuleType.LOOT_TABLE]

    def matches(self, data: Any, file_type: RuleType) -> bool:
        if not isinstance(data, dict):
            return False
        return "function" in data and "type" not in data

    def apply(self, data: Any, file_type: RuleType) -> RuleResult:
        result = RuleResult()
        if self.matches(data, file_type):
            data["type"] = data.pop("function")
            result.add_change("Renomeado 'function' → 'type' em loot function")
        return result


class ItemModifierConditionsRename(Rule):
    rule_id = "item_modifier_conditions_rename"
    description = "Renomear 'conditions' → 'condition' em item modifiers"
    snapshot_version = "snapshot4"
    target_types = [RuleType.ITEM_MODIFIER]

    def matches(self, data: Any, file_type: RuleType) -> bool:
        if not isinstance(data, dict):
            return False
        return "conditions" in data

    def apply(self, data: Any, file_type: RuleType) -> RuleResult:
        result = RuleResult()
        if not self.matches(data, file_type):
            return result

        def migrate_inner(cond):
            if isinstance(cond, dict):
                if "condition" in cond and "type" not in cond and "function" not in cond:
                    cond["type"] = cond.pop("condition")
                    result.add_change("Renomeado 'condition' → 'type' em condição aninhada")
            return cond

        old_conds = data["conditions"]
        migrated_value: Any = None
        if isinstance(old_conds, list):
            migrated = [migrate_inner(c) for c in old_conds]
            if len(migrated) > 1:
                migrated_value = {
                    "type": "minecraft:all_of",
                    "terms": migrated,
                }
                result.add_change("Convertida lista de condições em minecraft:all_of")
            elif len(migrated) == 1:
                migrated_value = migrated[0]
        else:
            migrated_value = migrate_inner(old_conds)
        if migrated_value:
            data["condition"] = migrated_value
            result.add_change("Renomeado 'conditions' → 'condition' em item modifier")
        else:
            result.add_change("Removido campo 'conditions' vazio em item modifier")
        del data["conditions"]
        return result


class ItemModifierFunctionsRename(Rule):
    rule_id = "item_modifier_functions_rename"
    description = "Renomear 'function' → 'type' e 'functions' → 'modifier' em item modifiers"
    snapshot_version = "snapshot4"
    target_types = [RuleType.ITEM_MODIFIER]

    def matches(self, data: Any, file_type: RuleType) -> bool:
        if not isinstance(data, dict):
            return False
        return ("function" in data and "type" not in data) or "functions" in data

    def apply(self, data: Any, file_type: RuleType) -> RuleResult:
        result = RuleResult()
        if not self.matches(data, file_type):
            return result

        if "function" in data and "type" not in data:
            data["type"] = data.pop("function")
            result.add_change("Renomeado 'function' → 'type' em item modifier")

        if "functions" in data:
            old_funcs = data["functions"]
            if isinstance(old_funcs, list) and len(old_funcs) > 1:
                data["modifier"] = {
                    "type": "minecraft:sequence",
                    "functions": old_funcs,
                }
                result.add_change("Convertida lista de funções em minecraft:sequence")
            elif isinstance(old_funcs, list) and len(old_funcs) == 1:
                data["modifier"] = old_funcs[0]
                result.add_change("Renomeado 'functions' → 'modifier' em item modifier")
            elif old_funcs:
                data["modifier"] = old_funcs
                result.add_change("Renomeado 'functions' → 'modifier' em item modifier")
            else:
                result.add_change("Removido campo 'functions' vazio em item modifier")
            del data["functions"]
        return result


class NumberFieldToProvider(Rule):
    rule_id = "number_field_to_provider"
    description = "Converter uniform provider implícito em minecraft:uniform explícito"
    snapshot_version = "snapshot4"
    target_types = [RuleType.LOOT_TABLE]

    FIELDS = ("rolls", "bonus_rolls")

    def matches(self, data: Any, file_type: RuleType) -> bool:
        if not isinstance(data, dict):
            return False
        pools = data.get("pools", [])
        for pool in pools:
            if isinstance(pool, dict):
                for field in self.FIELDS:
                    v = pool.get(field)
                    if isinstance(v, dict) and "min" in v and "max" in v and "type" not in v:
                        return True
        return False

    def apply(self, data: Any, file_type: RuleType) -> RuleResult:
        result = RuleResult()
        if not self.matches(data, file_type):
            return result

        pools = data.get("pools", [])
        for pool in pools:
            if isinstance(pool, dict):
                for field in self.FIELDS:
                    v = pool.get(field)
                    if isinstance(v, dict) and "min" in v and "max" in v and "type" not in v:
                        pool[field] = {"type": "minecraft:uniform", **v}
                        result.add_change(f"Convertido '{field}' para minecraft:uniform explícito")
        return result


class PotionContentsPredicateConvert(Rule):
    rule_id = "potion_contents_predicate_convert"
    description = "Converter minecraft:potion_contents de lista para objeto {potions: [...]}"
    snapshot_version = "snapshot4"
    target_types = [RuleType.ANY]

    def matches(self, data: Any, file_type: RuleType) -> bool:
        if not isinstance(data, dict):
            return False
        value = data.get("minecraft:potion_contents")
        return isinstance(value, (list, str))

    def apply(self, data: Any, file_type: RuleType) -> RuleResult:
        result = RuleResult()
        if self.matches(data, file_type):
            value = data["minecraft:potion_contents"]
            data["minecraft:potion_contents"] = {"potions": value}
            result.add_change(
                "Convertido minecraft:potion_contents para objeto {potions: ...}"
            )
        return result


class DamageSourcePredicateTags(Rule):
    rule_id = "damage_source_predicate_tags"
    description = "Adicionar prefixo '#' aos ids de tags em minecraft:damage_source_properties"
    snapshot_version = "snapshot4"
    target_types = [RuleType.ANY]

    def matches(self, data: Any, file_type: RuleType) -> bool:
        if not isinstance(data, dict):
            return False
        tags = self._collect_tag_lists(data)
        return any(
            isinstance(t, dict)
            and isinstance(t.get("id"), str)
            and not t["id"].startswith("#")
            for tag_list in tags
            for t in tag_list
        )

    def _collect_tag_lists(self, data: dict) -> list:
        lists = []
        t = data.get("type")
        if isinstance(t, dict) and isinstance(t.get("tags"), list):
            lists.append(t["tags"])
        predicate = data.get("predicate")
        if isinstance(predicate, dict):
            pt = predicate.get("type")
            if isinstance(pt, dict) and isinstance(pt.get("tags"), list):
                lists.append(pt["tags"])
            if isinstance(predicate.get("tags"), list):
                lists.append(predicate["tags"])
        return lists

    def apply(self, data: Any, file_type: RuleType) -> RuleResult:
        result = RuleResult()
        if not isinstance(data, dict):
            return result
        for tags in self._collect_tag_lists(data):
            for t in tags:
                if isinstance(t, dict) and isinstance(t.get("id"), str) \
                        and not t["id"].startswith("#"):
                    t["id"] = "#" + t["id"]
                    result.add_change(
                        "Adicionado prefixo '#' ao id de tag em damage_source_properties"
                    )
        return result


class RemoveEmptyConditionModifier(Rule):
    rule_id = "remove_empty_condition_modifier"
    description = "Remover campos 'condition'/'modifier' vazios (lista ou objeto vazio)"
    snapshot_version = "snapshot4"
    target_types = [
        RuleType.LOOT_TABLE,
        RuleType.ITEM_MODIFIER,
        RuleType.PREDICATE,
        RuleType.ADVANCEMENT,
    ]

    FIELDS = ("condition", "modifier")

    def matches(self, data: Any, file_type: RuleType) -> bool:
        if not isinstance(data, dict):
            return False
        return any(
            field in data and isinstance(data[field], (list, dict)) and len(data[field]) == 0
            for field in self.FIELDS
        )

    def apply(self, data: Any, file_type: RuleType) -> RuleResult:
        result = RuleResult()
        if not self.matches(data, file_type):
            return result
        for field in self.FIELDS:
            if field in data and isinstance(data[field], (list, dict)) and len(data[field]) == 0:
                del data[field]
                result.add_change(f"Removido campo '{field}' vazio")
        return result


SNAPSHOT4_RULES = [
    PredicateConditionToType(),
    RemovePredicateReference(),
    AllOfExplicit(),
    BlockStatePropertyToMatchBlock(),
    EntityPredicateRestructure(),
    SheepColorRemove(),
    EntitySubPredicateRename(),
    AdvancementTriggerToContextAware(),
    AdvancementTriggerListToAllOf(),
    AdvancementTriggerFieldPluralize(),
    LootPoolConditionsRename(),
    LootPoolFunctionsRename(),
    LootFunctionConditionsRename(),
    LootFunctionTypeRename(),
    ItemModifierConditionsRename(),
    ItemModifierFunctionsRename(),
    NumberFieldToProvider(),
    PotionContentsPredicateConvert(),
    DamageSourcePredicateTags(),
    RemoveEmptyConditionModifier(),
]
