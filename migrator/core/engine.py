"""Engine de migração schema-driven.

Aplica migrações incrementais por tipo de arquivo e snapshot,
usando funções de migração ancoradas em caminhos exatos do esquema.
"""
from __future__ import annotations

from typing import Any, Callable

from ..core.scanner import FileType


class MigrationResult:
    """Resultado de migrações aplicadas a um arquivo."""
    def __init__(self):
        self.changes: list[str] = []
        self.warnings: list[str] = []

    def add_change(self, description: str):
        self.changes.append(description)

    def add_warning(self, description: str):
        self.warnings.append(description)

# (snapshot_version, file_type) → lista de funções de migração
MIGRATION_REGISTRY: dict[tuple[str, FileType], list[Callable]] = {}

SNAPSHOT_ORDER = ["snapshot1", "snapshot2", "snapshot3", "snapshot4",
                  "snapshot5", "snapshot6", "snapshot7"]

# Versão de destino por snapshot (pack_format)
SNAPSHOT_FORMATS = {
    "snapshot1": 108,
    "snapshot2": 109,
    "snapshot3": 110,
    "snapshot4": 111,
    "snapshot5": 112,
    "snapshot6": 113,
    "snapshot7": 115,
}


def register(snapshot_version: str, file_types: list[FileType]):
    """Decorator para registrar uma função de migração."""
    def decorator(func: Callable) -> Callable:
        for ft in file_types:
            key = (snapshot_version, ft)
            if key not in MIGRATION_REGISTRY:
                MIGRATION_REGISTRY[key] = []
            MIGRATION_REGISTRY[key].append(func)
        return func
    return decorator


def apply_migrations(
    data: Any,
    file_type: FileType,
    target_version: str,
) -> tuple[Any, MigrationResult]:
    """Aplica migrações em ordem de snapshot até target_version.

    Para arquivos JSON (loot tables, predicates, advancements, etc).
    """
    result = MigrationResult()
    target_format = SNAPSHOT_FORMATS.get(target_version, 0)

    for snap in SNAPSHOT_ORDER:
        snap_format = SNAPSHOT_FORMATS.get(snap, 0)
        if snap_format > target_format:
            break

        key = (snap, file_type)
        if key not in MIGRATION_REGISTRY:
            continue

        for migrate_fn in MIGRATION_REGISTRY[key]:
            data = migrate_fn(data, result) or data

    return data, result


def apply_text_migrations(
    content: str,
    target_version: str,
) -> tuple[str, MigrationResult]:
    """Aplica migrações textuais (mcfunction) em ordem de snapshot."""
    result = MigrationResult()
    target_format = SNAPSHOT_FORMATS.get(target_version, 0)

    for snap in SNAPSHOT_ORDER:
        snap_format = SNAPSHOT_FORMATS.get(snap, 0)
        if snap_format > target_format:
            break

        key = (snap, FileType.MCFUNCTION)
        if key not in MIGRATION_REGISTRY:
            continue

        for migrate_fn in MIGRATION_REGISTRY[key]:
            content = migrate_fn(content, result) or content

    return content, result
