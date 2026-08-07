"""Regras de migração"""
import importlib
from .base import Rule

_snapshot2 = importlib.import_module(".26_3_snapshot_2", package="migrator.core.rules")
_snapshot4 = importlib.import_module(".26_3_snapshot_4", package="migrator.core.rules")
_snapshot7 = importlib.import_module(".26_3_snapshot_7", package="migrator.core.rules")
_snapshot_extra = importlib.import_module(".26_3_snapshot_extra", package="migrator.core.rules")

SNAPSHOT2_RULES = _snapshot2.SNAPSHOT2_RULES
SNAPSHOT4_RULES = _snapshot4.SNAPSHOT4_RULES
SNAPSHOT7_RULES = _snapshot7.SNAPSHOT7_RULES
EXTRA_RULES = _snapshot_extra.EXTRA_RULES

ALL_RULES = SNAPSHOT2_RULES + SNAPSHOT4_RULES + SNAPSHOT7_RULES + EXTRA_RULES
