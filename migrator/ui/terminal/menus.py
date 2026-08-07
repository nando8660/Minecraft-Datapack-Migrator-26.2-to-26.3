"""Interface de terminal - Menus com novo fluxo."""
from __future__ import annotations

from pathlib import Path

from .dialogs import (
    clear_screen,
    print_header,
    print_info,
    print_error,
    select_option,
)
from .file_picker import select_folder_native
from migrator.config import load_config, update_config, get_output_path
from migrator.core.overlay.collapse import (
    discover_overlays,
    collapse_to_new_overlay,
    collapse_to_flat_datapack,
)


def show_welcome():
    clear_screen()
    print_header("MIGRADOR DE DATAPACKS MINECRAFT")
    print("""
  Framework de Migração para Minecraft 26.3+

  Ferramenta para migrar automaticamente datapacks antigos
  para o formato exigido pelas snapshots 26.3 e pela
  release correspondente.
    """)
    input("  Pressione Enter para continuar...")


def select_datapack() -> Path | None:
    """Abre diálogo nativo para selecionar datapack."""
    config = load_config()
    last = config.get("last_source", "")

    if last and Path(last).exists():
        result = select_option(
            "DATAPACK",
            [
                f"Último: {Path(last).name}",
                "Selecionar outra pasta",
            ]
        )
        if result == "":
            return None
        if "Último" in result:
            return Path(last)

    folder = select_folder_native("Selecione a pasta do datapack")
    if folder:
        update_config("last_source", str(folder))
    return folder


def show_main_menu(source: Path) -> str:
    """Mostra opções após selecionar datapack."""
    overlays = discover_overlays(source)
    overlay_info = f" ({len(overlays)} overlay(s))" if overlays else " (sem overlays)"

    result = select_option(
        f"DATAPACK: {source.name}{overlay_info}",
        [
            "Atualizar para nova versão",
            "Migrar para datapack flat (versão única)",
            "Colapsar overlays",
            "Sair",
        ]
    )
    if result == "":
        return "exit"
    if "Atualizar" in result:
        return "migrate"
    if "flat" in result.lower():
        return "flat"
    if "Colapsar" in result:
        return "collapse"
    return "exit"


def show_collapse_menu(source: Path) -> str:
    """Mostra opções de colapso de overlays."""
    overlays = discover_overlays(source)

    if not overlays:
        print_info("Este datapack não possui overlays.")
        input("\n  Pressione Enter para voltar...")
        return ""

    overlay_names = [o.name for o in overlays]
    print(f"\n  Overlays encontrados: {', '.join(overlay_names)}\n")

    result = select_option(
        "MODO DE COLAPSO",
        [
            "Colapsar em novo overlay (mantém estrutura)",
            "Colapsar em novo datapack flat (sem overlays)",
        ]
    )
    if result == "":
        return ""
    if "novo overlay" in result:
        return "new_overlay"
    if "flat" in result:
        return "flat"
    return ""


def select_target_version() -> str:
    """Seleciona versão de destino para migração."""
    result = select_option(
        "VERSÃO DE DESTINO",
        [
            "26.3 Snapshot 1 (pack 108)",
            "26.3 Snapshot 2 (pack 109)",
            "26.3 Snapshot 3 (pack 110)",
            "26.3 Snapshot 4 (pack 111)",
            "26.3 Snapshot 5 (pack 112)",
            "26.3 Snapshot 6 (pack 113)",
            "26.3 Snapshot 7 (pack 115)",
            "26.3 Release (pack final)",
        ]
    )
    if result == "":
        return ""
    if "Snapshot 1" in result:
        return "snapshot1"
    if "Snapshot 2" in result:
        return "snapshot2"
    if "Snapshot 3" in result:
        return "snapshot3"
    if "Snapshot 4" in result:
        return "snapshot4"
    if "Snapshot 5" in result:
        return "snapshot5"
    if "Snapshot 6" in result:
        return "snapshot6"
    if "Snapshot 7" in result:
        return "snapshot7"
    if "Release" in result:
        return "release"
    return ""


def show_collapse_report(report):
    """Mostra relatório de colapso de overlays."""
    clear_screen()
    print_header("RELATÓRIO DE COLAPSO")
    print(f"""
  Origem: {report.source}
  Destino: {report.destination}
  Modo: {report.mode}

  Overlays encontrados: {len(report.overlays_found)}
  {', '.join(report.overlays_found) if report.overlays_found else 'Nenhum'}

  Arquivos colapsados: {report.files_collapsed}
  Arquivos escritos: {report.files_written}
  Conflitos resolvidos: {report.conflicts_resolved}
    """)

    if report.errors:
        print("  Erros:")
        for err in report.errors:
            print(f"    - {err}")

    input("\n  Pressione Enter para voltar ao menu...")


def show_report(report_summary: str):
    clear_screen()
    print_header("RELATÓRIO DE MIGRAÇÃO")
    print(report_summary)
    input("\n  Pressione Enter para voltar ao menu...")


def show_exit():
    clear_screen()
    print_header("OBRIGADO POR USAR O MIGRADOR")
    print("\n  Até logo!\n")
