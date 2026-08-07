"""Classe base para regras de migração."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RuleType(Enum):
    PREDICATE = "predicate"
    LOOT_TABLE = "loot_table"
    ITEM_MODIFIER = "item_modifier"
    RECIPE = "recipe"
    MCFUNCTION = "mcfunction"
    ADVANCEMENT = "advancement"
    BLOCK_STATE = "block_state"
    ENCHANTMENT = "enchantment"
    ANY = "any"


@dataclass
class RuleResult:
    applied: bool = False
    changes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    replacement: Any = None

    def add_change(self, description: str):
        self.changes.append(description)
        self.applied = True

    def add_warning(self, description: str):
        self.warnings.append(description)

    def set_replacement(self, value: Any):
        """Define um valor de substituição para o nó atual.

        Usado por regras que transformam um dicionário em um valor
        simples (ex: minecraft:reference → referência direta como string).
        """
        self.replacement = value
        self.applied = True


@dataclass
class RuleContext:
    """Contexto de aplicação de uma regra dentro do JSON.

    `path` é a sequência de chaves/índices desde a raiz do arquivo até o
    nó atual. Permite que regras apliquem somente nos locais corretos
    (ex: number providers só em 'rolls'/'bonus_rolls', entity predicates
    só dentro de wrappers entity_properties).
    """
    path: tuple[object, ...] = ()

    @property
    def parent_key(self) -> object | None:
        """Chave/index do nó pai (None se raiz)."""
        return self.path[-1] if self.path else None

    @property
    def grandparent_key(self) -> object | None:
        return self.path[-2] if len(self.path) >= 2 else None

    def is_key(self, *keys: object) -> bool:
        return self.parent_key in keys


class Rule(ABC):
    """Classe abstrata base para todas as regras de migração."""

    # Contexto do nó atual, preenchido pelo orquestrador antes de cada
    # chamada a matches()/apply().
    _context: RuleContext = RuleContext()

    @property
    def context(self) -> RuleContext:
        return self._context

    @property
    @abstractmethod
    def rule_id(self) -> str:
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        pass

    @property
    @abstractmethod
    def snapshot_version(self) -> str:
        pass

    @property
    @abstractmethod
    def target_types(self) -> list[RuleType]:
        pass

    @abstractmethod
    def matches(self, data: Any, file_type: RuleType) -> bool:
        pass

    @abstractmethod
    def apply(self, data: Any, file_type: RuleType) -> RuleResult:
        pass

    def migrate_text(self, content: str) -> tuple[str, list[str]]:
        """Transforma conteúdo textual (ex: arquivos .mcfunction).

        Sobrescreva em regras que operam sobre texto bruto. Retorna o
        novo conteúdo e a lista de mudanças aplicadas.
        """
        return content, []

    def applies_to(self, file_type: RuleType) -> bool:
        return RuleType.ANY in self.target_types or file_type in self.target_types

    def __repr__(self) -> str:
        return f"<Rule {self.rule_id}: {self.description}>"
