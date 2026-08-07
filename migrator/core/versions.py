"""Metadados de versões de destino da migração."""
from __future__ import annotations

VERSIONS: dict[str, dict] = {
    "snapshot1": {
        "label": "26.3 Snapshot 1",
        "pack_format": 108,
        "overlay": "26.3-snapshot-1_or_higher",
    },
    "snapshot2": {
        "label": "26.3 Snapshot 2",
        "pack_format": 109,
        "overlay": "26.3-snapshot-2_or_higher",
    },
    "snapshot3": {
        "label": "26.3 Snapshot 3",
        "pack_format": 110,
        "overlay": "26.3-snapshot-3_or_higher",
    },
    "snapshot4": {
        "label": "26.3 Snapshot 4",
        "pack_format": 111,
        "overlay": "26.3-snapshot-4_or_higher",
    },
    "snapshot5": {
        "label": "26.3 Snapshot 5",
        "pack_format": 112,
        "overlay": "26.3-snapshot-5_or_higher",
    },
    "snapshot6": {
        "label": "26.3 Snapshot 6",
        "pack_format": 113,
        "overlay": "26.3-snapshot-6_or_higher",
    },
    "snapshot7": {
        "label": "26.3 Snapshot 7",
        "pack_format": 115,
        "overlay": "26.3-snapshot-7_or_higher",
    },
    "release": {
        "label": "26.3 Release",
        "pack_format": 115,
        "overlay": "26.3_or_higher",
    },
}
