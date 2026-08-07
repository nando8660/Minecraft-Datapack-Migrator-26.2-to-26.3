"""Migrador de Datapacks Minecraft - Entry Point"""
from __future__ import annotations

import sys
from pathlib import Path

from migrator.auto_install import ensure_dependencies
if not ensure_dependencies():
    sys.exit(1)

from migrator.config import load_config, update_config, get_output_path
from migrator.core.migrate import MigrationOptions, migrate_datapack, migrate_to_flat_datapack
from migrator.core.versions import VERSIONS
from migrator.core.overlay.collapse import collapse_to_new_overlay, collapse_to_flat_datapack
from migrator.ui.terminal.menus import (
    show_welcome,
    select_datapack,
    show_main_menu,
    show_collapse_menu,
    select_target_version,
    show_collapse_report,
    show_report,
    show_exit,
)
from migrator.ui.terminal.dialogs import (
    clear_screen,
    print_header,
    print_info,
    print_error,
)


def main():
    show_welcome()

    # 1. Selecionar datapack
    source = select_datapack()
    if source is None:
        show_exit()
        return

    while True:
        # 2. Mostrar opções
        action = show_main_menu(source)

        if action == "exit":
            show_exit()
            break

        if action == "migrate":
            # 3. Selecionar versão de destino
            version = select_target_version()
            if not version:
                print_info("Operação cancelada.")
                input("\n  Pressione Enter para continuar...")
                continue

            # 4. Gerar destino automático
            destination = get_output_path(source)

            # 5. Migrar
            options = MigrationOptions(
                destination=destination,
                mode="new_datapack",
                target_version=version,
            )

            version_info = VERSIONS[version]
            clear_screen()
            print_header("MIGRANDO...")
            print(f"\n  Origem: {source}")
            print(f"  Destino: {destination}")
            print(f"  Versão: {version_info['label']}")
            print(f"  Novo overlay: {version_info['overlay']}")
            print()

            try:
                report = migrate_datapack(source, options)
                show_report(report.summary())
            except Exception as e:
                print_error(f"Erro durante a migração: {e}")
                input("\n  Pressione Enter para continuar...")

        elif action == "flat":
            # 3. Selecionar versão de destino
            version = select_target_version()
            if not version:
                print_info("Operação cancelada.")
                input("\n  Pressione Enter para continuar...")
                continue

            # 4. Gerar destino automático
            destination = get_output_path(source, "flat")

            # 5. Migrar para datapack flat
            options = MigrationOptions(
                destination=destination,
                mode="flat_datapack",
                target_version=version,
            )

            version_info = VERSIONS[version]
            clear_screen()
            print_header("MIGRANDO PARA DATAPACK FLAT...")
            print(f"\n  Origem: {source}")
            print(f"  Destino: {destination}")
            print(f"  Versão: {version_info['label']}")
            print(f"  Modo: Flat (sem overlays)")
            print()

            try:
                report = migrate_to_flat_datapack(source, options)
                show_report(report.summary())
            except Exception as e:
                print_error(f"Erro durante a migração: {e}")
                input("\n  Pressione Enter para continuar...")

        elif action == "collapse":
            # 3. Escolher modo de colapso
            collapse_mode = show_collapse_menu(source)
            if not collapse_mode:
                continue

            # 4. Gerar destino automático
            destination = get_output_path(source, "collapsed")

            # 5. Colapsar
            clear_screen()
            print_header("COLAPSANDO OVERLAYS...")
            print(f"\n  Origem: {source}")
            print(f"  Destino: {destination}")
            print(f"  Modo: {collapse_mode}")
            print()

            try:
                if collapse_mode == "new_overlay":
                    report = collapse_to_new_overlay(source, destination)
                else:
                    report = collapse_to_flat_datapack(source, destination)

                show_collapse_report(report)
            except Exception as e:
                print_error(f"Erro ao colapsar overlays: {e}")
                input("\n  Pressione Enter para continuar...")


if __name__ == "__main__":
    main()
