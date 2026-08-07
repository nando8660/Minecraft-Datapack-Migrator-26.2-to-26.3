"""Scanner para identificação e leitura de arquivos de datapack."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class FileType(Enum):
    LOOT_TABLE = "loot_table"
    PREDICATE = "predicate"
    ITEM_MODIFIER = "item_modifier"
    RECIPE = "recipe"
    MCFUNCTION = "mcfunction"
    ADVANCEMENT = "advancement"
    BLOCKS = "blocks"
    TAG = "tag"
    ENCHANTMENT = "enchantment"
    DAMAGE_TYPE = "damage_type"
    UNKNOWN = "unknown"


@dataclass
class ScannedFile:
    path: Path
    relative_path: str
    file_type: FileType
    data: Any = None
    namespace: str = ""
    original_content: str = ""

    @property
    def data_relative_path(self) -> str:
        """Caminho relativo à raiz de data/ (ignora overlays).

        Exemplos:
          data/armor_re/advancement/x.json           -> armor_re/advancement/x.json
          25w44a_or_higher/data/armor_re/x.json      -> armor_re/x.json
          data/_overlay_0/test/loot_tables/x.json    -> test/loot_tables/x.json
        """
        parts = self.relative_path.replace("\\", "/").split("/")
        idx = _find_data_index(tuple(parts))
        if idx == -1:
            return self.relative_path.replace("\\", "/")
        rest = parts[idx + 1:]
        if rest and rest[0].startswith("_overlay_"):
            rest = rest[1:]
        return "/".join(rest)


@dataclass
class DatapackScanResult:
    root: Path
    files: list[ScannedFile] = field(default_factory=list)
    namespaces: dict[str, list[ScannedFile]] = field(default_factory=dict)
    errors: list[tuple[Path, str]] = field(default_factory=list)

    @property
    def total_files(self) -> int:
        return len(self.files)

    @property
    def modified_count(self) -> int:
        return sum(1 for f in self.files if f.data is not None)


# Nomes de categoria aceitos (plural = formato antigo, singular = formato novo)
CATEGORY_TO_TYPE: dict[str, FileType] = {
    "loot_tables": FileType.LOOT_TABLE,
    "loot_table": FileType.LOOT_TABLE,
    "predicates": FileType.PREDICATE,
    "predicate": FileType.PREDICATE,
    "item_modifier": FileType.ITEM_MODIFIER,
    "recipes": FileType.RECIPE,
    "recipe": FileType.RECIPE,
    "advancements": FileType.ADVANCEMENT,
    "advancement": FileType.ADVANCEMENT,
    "functions": FileType.MCFUNCTION,
    "function": FileType.MCFUNCTION,
    "tags": FileType.TAG,
    "tag": FileType.TAG,
    "blocks": FileType.BLOCKS,
    "enchantments": FileType.ENCHANTMENT,
    "enchantment": FileType.ENCHANTMENT,
    "damage_type": FileType.DAMAGE_TYPE,
}


def _find_data_index(parts: tuple[str, ...]) -> int:
    """Encontra o índice do diretório 'data'.

    Suporta datapack normal (data/...) e overlays reais
    (25w44a_or_higher/data/...) ou nossa convenção de teste
    (data/_overlay_0/...).
    """
    if parts and parts[0] == "data":
        return 0
    if len(parts) >= 2 and parts[1] == "data":
        return 1
    return -1


def _skip_overlay_segment(parts: tuple[str, ...], data_idx: int) -> int:
    """Ajusta o índice para pular um segmento _overlay_N logo após data/.

    Usado na convenção de teste do projeto (data/_overlay_0/<ns>/...).
    """
    if data_idx + 1 < len(parts) and parts[data_idx + 1].startswith("_overlay_"):
        return data_idx + 1
    return data_idx


def classify_file(rel_path: Path) -> FileType:
    parts = rel_path.parts
    data_idx = _find_data_index(parts)

    if data_idx == -1 or len(parts) < data_idx + 3:
        # Arquivo de data generation no nível do namespace (ex: data/<ns>/blocks.json)
        if parts and parts[-1] == "blocks.json":
            return FileType.BLOCKS
        return FileType.UNKNOWN

    data_idx = _skip_overlay_segment(parts, data_idx)
    if len(parts) < data_idx + 3:
        return FileType.UNKNOWN

    if parts[-1] == "blocks.json":
        return FileType.BLOCKS

    category = parts[data_idx + 2]
    return CATEGORY_TO_TYPE.get(category, FileType.UNKNOWN)


def extract_namespace(rel_path: Path) -> str:
    parts = rel_path.parts
    data_idx = _find_data_index(parts)

    if data_idx != -1 and len(parts) >= data_idx + 3:
        data_idx = _skip_overlay_segment(parts, data_idx)
        if len(parts) >= data_idx + 3:
            return parts[data_idx + 1]
    return ""


def scan_datapack(root: Path) -> DatapackScanResult:
    result = DatapackScanResult(root=root)

    pack_mcmeta = root / "pack.mcmeta"
    if not pack_mcmeta.exists():
        result.errors.append((root, "pack.mcmeta não encontrado"))
        return result

    for dirpath, dirnames, filenames in os.walk(root):
        for filename in filenames:
            if filename == "pack.mcmeta":
                continue

            full_path = Path(dirpath) / filename
            rel_path = full_path.relative_to(root)

            file_type = classify_file(rel_path)

            scanned = ScannedFile(
                path=full_path,
                relative_path=str(rel_path),
                file_type=file_type,
                namespace=extract_namespace(rel_path),
            )

            if file_type in (FileType.LOOT_TABLE, FileType.PREDICATE, FileType.ITEM_MODIFIER,
                             FileType.RECIPE, FileType.ADVANCEMENT,
                             FileType.BLOCKS, FileType.ENCHANTMENT, FileType.TAG,
                             FileType.DAMAGE_TYPE):
                try:
                    with open(full_path, "r", encoding="utf-8") as f:
                        scanned.original_content = f.read()
                    scanned.data = json.loads(scanned.original_content)
                except json.JSONDecodeError as e:
                    result.errors.append((full_path, f"JSON inválido: {e}"))
                except Exception as e:
                    result.errors.append((full_path, f"Erro ao ler: {e}"))
            elif file_type == FileType.MCFUNCTION:
                try:
                    with open(full_path, "r", encoding="utf-8") as f:
                        scanned.original_content = f.read()
                except Exception as e:
                    result.errors.append((full_path, f"Erro ao ler: {e}"))

            result.files.append(scanned)

            ns = scanned.namespace
            if ns:
                if ns not in result.namespaces:
                    result.namespaces[ns] = []
                result.namespaces[ns].append(scanned)

    return result
