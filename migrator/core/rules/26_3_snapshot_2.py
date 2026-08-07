"""Regras de migração da Snapshot 2 (pack format 109.0)."""
from __future__ import annotations

from typing import Any

from .base import Rule, RuleResult, RuleType


class BlocksJsonRemoveDefinition(Rule):
    rule_id = "blocks_json_remove_definition"
    description = "Remover campo 'definition' de blocks.json"
    snapshot_version = "snapshot2"
    target_types = [RuleType.ANY]

    def matches(self, data: Any, file_type: RuleType) -> bool:
        if not isinstance(data, dict):
            return False
        return "definition" in data

    def apply(self, data: Any, file_type: RuleType) -> RuleResult:
        result = RuleResult()
        if self.matches(data, file_type):
            del data["definition"]
            result.add_change("Removido campo 'definition' de blocks.json")
        return result


SNAPSHOT2_RULES = [
    BlocksJsonRemoveDefinition(),
]
