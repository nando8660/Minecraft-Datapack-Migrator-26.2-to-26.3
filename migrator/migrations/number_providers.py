"""Migrações de number providers (Snapshot 4)."""
from __future__ import annotations

from typing import Any

from ..core.scanner import FileType
from ..core.engine import register, MigrationResult


_ALL_TYPES = [FileType.PREDICATE, FileType.ADVANCEMENT, FileType.LOOT_TABLE,
              FileType.ITEM_MODIFIER, FileType.ENCHANTMENT, FileType.RECIPE,
              FileType.TAG]


@register("snapshot4", _ALL_TYPES)
def add_uniform_type_to_number_providers(data: Any, result: MigrationResult) -> Any:
    """Adicionar 'type': 'minecraft:uniform' a number providers implicitos.

    Na Snapshot 4, number providers precisam de 'type' explicito.
    Dicts com 'min' e 'max' mas sem 'type' devem receber
    'type': 'minecraft:uniform'.

    Aplica-se recursivamente a todo o JSON, incluindo níveis aninhados
    onde max é outro number provider (dict).

    Não aplica a:
    - time_check.value (é um range simples, não number provider)
    """
    if isinstance(data, dict):
        # Verificar se e um number provider implicito
        if ("min" in data and "max" in data and "type" not in data
                and "condition" not in data and "function" not in data):
            # Adiciona uniform independente de min/max serem números ou dicts
            # (min:number, max:number) OU (min:number, max:dict) são ambos number providers
            data["type"] = "minecraft:uniform"
            result.add_change("Adicionado 'type': 'minecraft:uniform' a number provider implicito")
        # Recursao
        for key, value in data.items():
            # Não adicionar uniform ao value de time_check (é range, não provider)
            if key == "value" and data.get("type") == "minecraft:time_check":
                continue
            add_uniform_type_to_number_providers(value, result)
    elif isinstance(data, list):
        for item in data:
            add_uniform_type_to_number_providers(item, result)
    return data


@register("snapshot4", [FileType.LOOT_TABLE, FileType.ITEM_MODIFIER])
def rename_function_to_type_recursive(data: Any, result: MigrationResult) -> Any:
    """Renomear 'function' → 'type' recursivamente em loot functions.

    Em 26.3, loot functions usam 'type' em vez de 'function'.
    Aplica-se a functions dentro de entries, sequences, e modifiers.
    """
    if isinstance(data, dict):
        if "function" in data and "type" not in data:
            data["type"] = data.pop("function")
            result.add_change("Renomeado 'function' → 'type' em loot function")
        for value in data.values():
            rename_function_to_type_recursive(value, result)
    elif isinstance(data, list):
        for item in data:
            rename_function_to_type_recursive(item, result)
    return data


@register("snapshot4", [FileType.PREDICATE, FileType.ADVANCEMENT,
                         FileType.LOOT_TABLE, FileType.ITEM_MODIFIER])
def rename_condition_to_type_recursive(data: Any, result: MigrationResult) -> Any:
    """Renomear 'condition' → 'type' recursivamente em predicates.

    Em 26.3, predicates usam 'type' em vez de 'condition'.
    Aplica-se a predicates em qualquer nivel de aninhamento.
    """
    if isinstance(data, dict):
        if ("condition" in data and "type" not in data
                and "function" not in data):
            cond_val = data.get("condition")
            # Verifica se o valor de 'condition' parece um tipo de predicate
            # (string com namespace 'minecraft:' ou 'modid:')
            should_rename = False
            if isinstance(cond_val, str) and ":" in cond_val:
                should_rename = True
            else:
                # Verifica indicadores de predicate
                predicate_indicators = {"entity", "predicate", "block", "blocks",
                                        "properties", "state", "terms", "chance",
                                        "unenchanted_chance", "enchanted_chance",
                                        "enchantment", "term", "inverted"}
                if any(ind in data for ind in predicate_indicators):
                    should_rename = True
            if should_rename:
                data["type"] = data.pop("condition")
                result.add_change("Renomeado 'condition' → 'type' em predicate")
        for value in data.values():
            rename_condition_to_type_recursive(value, result)
    elif isinstance(data, list):
        for item in data:
            rename_condition_to_type_recursive(item, result)
    return data
