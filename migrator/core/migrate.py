"""Orquestrador principal de migração."""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .scanner import DatapackScanResult, FileType, ScannedFile, scan_datapack
from .report import FileReport, MigrationReport
from .versions import VERSIONS

# Importar módulos de migração para registrar as funções no engine
from ..migrations import blocks, tags, trim, decorated_pot  # noqa: F401
from ..migrations import loot_table, predicate, advancement  # noqa: F401
from ..migrations import mcfunction, data_components, slot_source  # noqa: F401
from ..migrations import number_providers  # noqa: F401


@dataclass
class MigrationOptions:
    destination: Path
    mode: str = "new_datapack"
    target_version: str = "snapshot4"
    copy_unchanged: bool = True


@dataclass
class OverlayEntry:
    directory: str
    min_format: int
    max_format: int | None
    data_dir: Path


FILE_TYPE_MAP = {
    FileType.LOOT_TABLE: FileType.LOOT_TABLE,
    FileType.PREDICATE: FileType.PREDICATE,
    FileType.ITEM_MODIFIER: FileType.ITEM_MODIFIER,
    FileType.RECIPE: FileType.RECIPE,
    FileType.MCFUNCTION: FileType.MCFUNCTION,
    FileType.ADVANCEMENT: FileType.ADVANCEMENT,
    FileType.ENCHANTMENT: FileType.ENCHANTMENT,
    FileType.BLOCKS: FileType.BLOCKS,
    FileType.TAG: FileType.TAG,
    FileType.DAMAGE_TYPE: FileType.DAMAGE_TYPE,
}


def process_file(scanned: ScannedFile, target_version: str) -> FileReport:
    """Processa um arquivo usando o novo engine de migrações schema-driven."""
    from .engine import apply_migrations, apply_text_migrations

    report = FileReport(
        path=scanned.relative_path,
        file_type=scanned.file_type.value,
    )

    if scanned.file_type == FileType.MCFUNCTION:
        content = scanned.original_content
        new_content, mig_result = apply_text_migrations(content, target_version)
        if mig_result.changes:
            report.modified = True
            report.changes = mig_result.changes
            report.warnings = mig_result.warnings
            report.rules_applied = ["mcfunction_text"]
            scanned.original_content = new_content
        return report

    if scanned.data is None:
        return report

    # Desempacotar predicates com lista de 1 elemento
    root_unwrapped = False
    if (
        scanned.file_type == FileType.PREDICATE
        and isinstance(scanned.data, list)
        and len(scanned.data) == 1
        and isinstance(scanned.data[0], dict)
    ):
        scanned.data = scanned.data[0]
        root_unwrapped = True

    # Aplicar migrações schema-driven
    rule_type = FILE_TYPE_MAP.get(scanned.file_type, FileType.UNKNOWN)
    if rule_type == FileType.UNKNOWN:
        rule_type = scanned.file_type

    migrated_data, mig_result = apply_migrations(
        scanned.data, rule_type, target_version
    )

    if root_unwrapped:
        mig_result.changes.insert(
            0, "Desempacotado arquivo de predicate de array (1 elemento) para objeto"
        )

    if mig_result.changes:
        report.modified = True
        report.changes = mig_result.changes
        report.warnings = mig_result.warnings
        report.rules_applied = ["schema_migration"]
        scanned.data = migrated_data

    return report


def load_overlay_entries(source: Path) -> list[OverlayEntry]:
    """Carrega overlays em ordem de carregamento do pack.mcmeta.

    A ordem retornada segue pack.mcmeta overlays.entries: quanto mais
    tarde no arquivo, maior a prioridade (sobrescreve os anteriores).
    """
    entries: list[OverlayEntry] = []

    pack_mcmeta = source / "pack.mcmeta"
    if pack_mcmeta.exists():
        try:
            data = json.loads(pack_mcmeta.read_text(encoding="utf-8"))
            raw = data.get("overlays", {}).get("entries", [])
            for e in raw:
                directory = e.get("directory", "")
                if not directory:
                    continue
                min_format = int(e.get("min_format", 0))
                max_format = e.get("max_format")
                if isinstance(max_format, list):
                    max_format = max_format[0] if max_format else None
                entries.append(OverlayEntry(
                    directory=directory,
                    min_format=min_format,
                    max_format=max_format,
                    data_dir=source / directory / "data",
                ))
        except Exception:
            pass

    # Convenção de teste do projeto: data/_overlay_N
    data_dir = source / "data"
    if data_dir.exists():
        test_overlays = sorted(
            [d for d in data_dir.iterdir()
             if d.is_dir() and d.name.startswith("_overlay_")],
            key=lambda d: int(d.name.split("_")[-1]) if d.name.split("_")[-1].isdigit() else 0
        )
        for ov in test_overlays:
            entries.append(OverlayEntry(
                directory=ov.name,
                min_format=0,
                max_format=None,
                data_dir=ov,
            ))

    return entries


def is_overlay_active(entry: OverlayEntry, target_format: int) -> bool:
    if target_format < entry.min_format:
        return False
    if entry.max_format is not None and target_format > entry.max_format:
        return False
    return True


def get_effective_files(source: Path, target_format: int) -> dict[str, Path]:
    """Retorna, para cada caminho relativo a data/, o arquivo efetivo.

    Respeita a ordem de carregamento do pack.mcmeta: overlays ativos para
    a versão alvo são aplicados em ordem, e o último sobrescreve os
    anteriores. Arquivos de data/ raiz têm menor prioridade.

    Se não existe data/ raiz (datapack usa apenas overlays), todos os
    arquivos de overlays são tratados como base.
    """
    effective: dict[str, Path] = {}

    # Arquivos base de data/ (fora de overlays) — menor prioridade
    base_data = source / "data"
    has_base_data = False
    if base_data.exists():
        for p in base_data.rglob("*"):
            if not p.is_file():
                continue
            parts = p.relative_to(base_data).parts
            if parts and parts[0].startswith("_overlay_"):
                continue
            has_base_data = True
            rel = str(p.relative_to(base_data)).replace("\\", "/")
            effective[rel] = p

    # Overlays ativos em ordem de carregamento
    active_overlays = []
    for entry in load_overlay_entries(source):
        if has_base_data:
            # Com data/ raiz, overlays só valem se ativos para target_format
            if not is_overlay_active(entry, target_format):
                continue
        else:
            # Sem data/ raiz, overlays são a única fonte — incluir todos
            # que tenham min_format <= target_format
            if entry.min_format > target_format:
                continue
        active_overlays.append(entry)

    for entry in active_overlays:
        if not entry.data_dir.exists():
            continue
        for p in entry.data_dir.rglob("*"):
            if p.is_file():
                rel = str(p.relative_to(entry.data_dir)).replace("\\", "/")
                effective[rel] = p

    return effective


def write_migrated_file(scanned: ScannedFile, dest_file: Path):
    dest_file.parent.mkdir(parents=True, exist_ok=True)
    if scanned.file_type == FileType.MCFUNCTION:
        with open(dest_file, "w", encoding="utf-8") as f:
            f.write(scanned.original_content)
    elif scanned.data is not None:
        with open(dest_file, "w", encoding="utf-8") as f:
            json.dump(scanned.data, f, indent=2, ensure_ascii=False)
            f.write("\n")
    elif scanned.original_content:
        # Fallback: escreve conteúdo original para JSONs não mapeados
        with open(dest_file, "w", encoding="utf-8") as f:
            f.write(scanned.original_content)


def _fix_filter_paths(filter_data: dict) -> dict:
    """Corrigir paths no filter.block para usar formato regex correto.

    O Minecraft espera que o campo 'path' seja uma regex.
    Transforma 'recipe/tnt.json' em '/tnt.json' (regex que termina com /tnt.json).
    """
    if not filter_data:
        return filter_data
    block = filter_data.get("block", [])
    for entry in block:
        path_val = entry.get("path", "")
        # Se o path contém '/', transformar em regex '/filename.ext'
        if "/" in path_val:
            filename = path_val.rsplit("/", 1)[-1]
            entry["path"] = f"/{filename}"
    return filter_data


def update_pack_mcmeta(destination: Path, overlay_name: str, target_format: int):
    """Atualiza o pack.mcmeta com o novo overlay e formato máximo.

    - Atualiza pack.max_format para [target_format, 0]
    - Atualiza max_format de todos os overlays para [target_format, 0]
    - Adiciona o novo overlay com min_format e max_format = [target_format, 0]
    - Corrige paths do filter.block para formato regex
    """
    path = destination / "pack.mcmeta"
    if not path.exists():
        return

    data = json.loads(path.read_text(encoding="utf-8"))

    # Corrigir filter paths antes de qualquer coisa
    if "filter" in data:
        data["filter"] = _fix_filter_paths(data["filter"])

    # Atualizar max_format do pack raiz
    pack = data.get("pack", {})
    pack["max_format"] = [target_format, 0]
    data["pack"] = pack

    # Atualizar max_format de todos os overlays para [target_format, 0]
    entries = data.get("overlays", {}).get("entries", [])
    for entry in entries:
        entry["max_format"] = [target_format, 0]

    if not any(e.get("directory") == overlay_name for e in entries):
        new_entry = {
            "directory": overlay_name,
            "min_format": target_format,
            "max_format": [target_format, 0],
        }
        entries.append(new_entry)

    data.setdefault("overlays", {})["entries"] = entries

    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def migrate_datapack(source: Path, options: MigrationOptions) -> MigrationReport:
    """Migra um datapack copiando-o inteiro e criando um novo overlay.

    Fluxo:
    1. Copia o datapack inteiro para o destino.
    2. Escaneia todos os arquivos (respeitando overlays).
    3. Para cada arquivo efetivo, aplica migrações e escreve no novo overlay.
    4. Atualiza o pack.mcmeta com o novo overlay.
    """
    destination = options.destination

    report = MigrationReport(
        source_path=str(source),
        destination_path=str(destination),
        mode=options.mode,
    )

    version_info = VERSIONS.get(options.target_version)
    if version_info is None:
        raise ValueError(f"Versão de destino desconhecida: {options.target_version}")

    overlay_name = version_info["overlay"]
    target_format = version_info["pack_format"]
    report.target_version = version_info["label"]
    report.overlay_name = overlay_name

    # 1. Copiar datapack inteiro
    # Se já existe um output anterior, apaga antes de recriar (sobrescreve).
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)

    # 2. Escanear fonte para carregar JSONs
    scan_result = scan_datapack(source)
    report.global_errors = [f"{path}: {err}" for path, err in scan_result.errors]
    by_path: dict[str, ScannedFile] = {}
    for scanned in scan_result.files:
        by_path[scanned.data_relative_path] = scanned

    # 3. Arquivos efetivos respeitando ordem de carregamento
    effective_files = get_effective_files(source, target_format)

    dest_overlay = destination / overlay_name / "data"

    # 4. Checar e migrar
    for rel, file_path in effective_files.items():
        scanned = by_path.get(rel)
        if scanned is None:
            report.add_file_report(FileReport(path=rel, file_type="unknown"))
            continue

        file_report = process_file(scanned, options.target_version)
        report.add_file_report(file_report)

        # Escrever no overlay:
        # - Se copy_unchanged=True: copia TODOS os arquivos (overlay autocontido)
        # - Se copy_unchanged=False: copia só os modificados (economiza espaco)
        if options.copy_unchanged or file_report.modified:
            write_migrated_file(scanned, dest_overlay / rel)
            report.overlay_copied += 1
        else:
            report.overlay_skipped += 1

    # 5. Atualizar pack.mcmeta
    update_pack_mcmeta(destination, overlay_name, target_format)

    return report


def migrate_to_flat_datapack(source: Path, options: MigrationOptions) -> MigrationReport:
    """Migra todos os arquivos para um datapack flat (sem overlays).

    Coleta arquivos efetivos respeitando prioridade dos overlays,
    aplica migrações, e escreve tudo diretamente em data/.
    O pack.mcmeta resultante tem apenas pack_format (sem overlays).

    Fluxo:
    1. Escanear source para carregar JSONs.
    2. Coletar arquivos efetivos (respeitando prioridade dos overlays).
    3. Para cada arquivo, aplicar migrações.
    4. Escrever todos os arquivos migrados em destination/data/.
    5. Criar pack.mcmeta simples com apenas pack_format.
    """
    destination = options.destination

    report = MigrationReport(
        source_path=str(source),
        destination_path=str(destination),
        mode="flat_datapack",
    )

    version_info = VERSIONS.get(options.target_version)
    if version_info is None:
        raise ValueError(f"Versão de destino desconhecida: {options.target_version}")

    target_format = version_info["pack_format"]
    report.target_version = version_info["label"]
    report.overlay_name = "(flat - sem overlays)"

    # 1. Escanear fonte para carregar JSONs
    scan_result = scan_datapack(source)
    report.global_errors = [f"{path}: {err}" for path, err in scan_result.errors]
    by_path: dict[str, ScannedFile] = {}
    for scanned in scan_result.files:
        by_path[scanned.data_relative_path] = scanned

    # 2. Arquivos efetivos respeitando ordem de carregamento
    effective_files = get_effective_files(source, target_format)

    dest_data = destination / "data"

    # 3. Checar e migrar cada arquivo
    for rel, file_path in effective_files.items():
        scanned = by_path.get(rel)
        if scanned is None:
            report.add_file_report(FileReport(path=rel, file_type="unknown"))
            continue

        file_report = process_file(scanned, options.target_version)
        report.add_file_report(file_report)

        # Escrever arquivo migrado diretamente em data/
        write_migrated_file(scanned, dest_data / rel)

    # 4. Criar pack.mcmeta flat (sem overlays)
    _create_flat_pack_mcmeta(destination, source, target_format)

    return report


def _create_flat_pack_mcmeta(destination: Path, source: Path, target_format: int):
    """Cria um pack.mcmeta flat (sem overlays) compatível apenas com a versão alvo."""
    # Copiar description do pack.mcmeta original se existir
    description = "Datapack migrado"
    source_mcmeta = source / "pack.mcmeta"
    if source_mcmeta.exists():
        try:
            original = json.loads(source_mcmeta.read_text(encoding="utf-8"))
            description = original.get("pack", {}).get("description", description)
        except Exception:
            pass

    pack_mcmeta = {
        "pack": {
            "min_format": target_format,
            "max_format": [target_format, 0],
            "description": description,
        }
    }

    destination.mkdir(parents=True, exist_ok=True)
    mcmeta_path = destination / "pack.mcmeta"
    mcmeta_path.write_text(
        json.dumps(pack_mcmeta, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
