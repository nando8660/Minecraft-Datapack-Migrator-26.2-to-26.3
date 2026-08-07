"""Sistema de colapso de overlays de datapacks."""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class OverlayInfo:
    name: str
    path: Path
    files: list[Path] = field(default_factory=list)


@dataclass
class CollapseReport:
    source: Path
    destination: Path
    mode: str
    overlays_found: list[str] = field(default_factory=list)
    files_collapsed: int = 0
    files_written: int = 0
    conflicts_resolved: int = 0
    errors: list[str] = field(default_factory=list)


def discover_overlays(datapack_path: Path) -> list[OverlayInfo]:
    """Descobre todos os overlays em um datapack.

    Suporta dois formatos:
    1. Overlays reais do Minecraft, declarados em pack.mcmeta
       (ex: <root>/25w44a_or_higher/data/...)
    2. Convenção de teste usada pelo projeto
       (ex: <root>/data/_overlay_0/...)
    """
    overlays = []

    def add_overlay(name: str, base_path: Path):
        files = list(base_path.rglob("*")) if base_path.exists() else []
        overlays.append(OverlayInfo(name=name, path=base_path, files=files))

    # 1. Overlays reais do pack.mcmeta (diretórios no nível do root)
    pack_mcmeta = datapack_path / "pack.mcmeta"
    if pack_mcmeta.exists():
        try:
            data = json.loads(pack_mcmeta.read_text(encoding="utf-8"))
            entries = data.get("overlays", {}).get("entries", [])
            for entry in entries:
                directory = entry.get("directory", "")
                if not directory:
                    continue
                base = datapack_path / directory / "data"
                if base.exists():
                    add_overlay(directory, base)
        except Exception:
            pass

    # 2. Convenção de teste: data/_overlay_N
    data_dir = datapack_path / "data"
    if data_dir.exists():
        test_overlays = sorted(
            [d for d in data_dir.iterdir()
             if d.is_dir() and d.name.startswith("_overlay_")],
            key=lambda d: int(d.name.split("_")[-1]) if d.name.split("_")[-1].isdigit() else 0
        )
        for overlay_dir in test_overlays:
            add_overlay(overlay_dir.name, overlay_dir)

    return overlays


def get_file_relative_path(file_path: Path, base_path: Path) -> str:
    """Retorna caminho relativo com / como separador."""
    return str(file_path.relative_to(base_path)).replace("\\", "/")


def collapse_to_new_overlay(
    source: Path,
    destination: Path,
    overlay_name: str = "_overlay_0"
) -> CollapseReport:
    """Colapsa todos os overlays em um único novo overlay.

    O datapack resultado continua usando overlays.
    """
    report = CollapseReport(
        source=source,
        destination=destination,
        mode="novo_overlay"
    )

    overlays = discover_overlays(source)
    report.overlays_found = [o.name for o in overlays]

    if not overlays:
        report.errors.append("Nenhum overlay encontrado no datapack")
        return report

    # Coleção de arquivos: caminho_relativo -> conteúdo
    merged_files: dict[str, Path] = {}

    for overlay in overlays:
        for file_path in overlay.files:
            if file_path.is_file():
                rel_path = get_file_relative_path(file_path, overlay.path)
                merged_files[rel_path] = file_path
                report.files_collapsed += 1

    # Detectar convenção: overlays reais ficam no nível do root
    # (25w44a_or_higher/data), overlays de teste ficam em data/_overlay_N
    real_convention = bool(overlays) and overlays[0].path.parent.parent == source

    # Sobrescreve output anterior, se houver
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True, exist_ok=True)

    # Copiar pack.mcmeta
    pack_mcmeta = source / "pack.mcmeta"
    if pack_mcmeta.exists():
        shutil.copy2(pack_mcmeta, destination / "pack.mcmeta")

    if real_convention:
        dest_overlay = destination / overlay_name / "data"
    else:
        dest_overlay = destination / "data" / overlay_name
    dest_overlay.mkdir(parents=True, exist_ok=True)

    # Copiar arquivos fundidos
    for rel_path, source_file in merged_files.items():
        dest_file = dest_overlay / rel_path
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_file, dest_file)
        report.files_written += 1

    return report


def collapse_to_flat_datapack(
    source: Path,
    destination: Path
) -> CollapseReport:
    """Colapsa todos os overlays em um datapack flat (sem overlays).

    Todo o resultado vai direto para data/.
    """
    report = CollapseReport(
        source=source,
        destination=destination,
        mode="datapack_flat"
    )

    overlays = discover_overlays(source)
    overlay_names = {o.name for o in overlays}
    report.overlays_found = [o.name for o in overlays]

    # Coleção final: base tem menor prioridade, último overlay tem maior
    merged_files: dict[str, Path] = {}

    # Arquivos base de data/ (fora de overlays)
    data_dir = source / "data"
    if data_dir.exists():
        for file_path in data_dir.rglob("*"):
            if file_path.is_file():
                parts = file_path.relative_to(data_dir).parts
                if parts and parts[0] in overlay_names:
                    continue
                rel_path = str(file_path.relative_to(data_dir)).replace("\\", "/")
                merged_files[rel_path] = file_path

    # Adicionar arquivos dos overlays em ordem
    for overlay in overlays:
        for file_path in overlay.files:
            if file_path.is_file():
                rel_path = get_file_relative_path(file_path, overlay.path)
                if rel_path in merged_files:
                    report.conflicts_resolved += 1
                merged_files[rel_path] = file_path
                report.files_collapsed += 1

    # Criar destino (sobrescreve output anterior, se houver)
    if destination.exists():
        shutil.rmtree(destination)
    dest_data = destination / "data"
    dest_data.mkdir(parents=True, exist_ok=True)

    # Copiar pack.mcmeta
    pack_mcmeta = source / "pack.mcmeta"
    if pack_mcmeta.exists():
        shutil.copy2(pack_mcmeta, destination / "pack.mcmeta")

    # Copiar arquivos fundidos
    for rel_path, source_file in merged_files.items():
        dest_file = dest_data / rel_path
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_file, dest_file)
        report.files_written += 1

    return report
