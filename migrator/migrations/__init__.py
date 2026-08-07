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
    number_providers,
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
    "number_providers",
]
