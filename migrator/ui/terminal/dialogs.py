"""Interface de terminal - Diálogos com navegação por setas."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from .input import read_key


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def print_header(title: str):
    width = 60
    print("\n" + "=" * width)
    print(f"  {title}")
    print("=" * width)


def print_success(message: str):
    print(f"  [OK] {message}")


def print_error(message: str):
    print(f"  [ERRO] {message}")


def print_warning(message: str):
    print(f"  [AVISO] {message}")


def print_info(message: str):
    print(f"  [INFO] {message}")


def select_option(title: str, options: list[str]) -> str:
    current = 0
    while True:
        clear_screen()
        print_header(title)
        print()

        for i, option in enumerate(options):
            if i == current:
                print(f"  > {option} <")
            else:
                print(f"    {option}")

        print()
        print("  ↑↓ navegar  Enter confirmar  Q cancelar")

        key = read_key()
        if key == "up":
            current = (current - 1) % len(options)
        elif key == "down":
            current = (current + 1) % len(options)
        elif key == "enter":
            return options[current]
        elif key == "q":
            return ""


def confirm(message: str) -> bool:
    current = 0
    options = ["Sim", "Não"]

    while True:
        clear_screen()
        print_header("CONFIRMAÇÃO")
        print(f"\n  {message}\n")

        for i, option in enumerate(options):
            if i == current:
                print(f"  > {option} <")
            else:
                print(f"    {option}")

        print()
        print("  ↑↓ navegar  Enter confirmar  Q cancelar")

        key = read_key()
        if key == "up":
            current = (current - 1) % len(options)
        elif key == "down":
            current = (current + 1) % len(options)
        elif key == "enter":
            return current == 0
        elif key == "q":
            return False


def select_folder(start: Path | None = None) -> Path | None:
    current = (start or Path.home()).resolve()

    while True:
        items = []

        if current.parent != current:
            items.append((".. (voltar)", current.parent, True))

        try:
            for entry in sorted(current.iterdir()):
                if entry.is_dir() and not entry.name.startswith("."):
                    items.append((entry.name, entry, True))
        except PermissionError:
            print_error("Sem permissão")
            input("  Enter para voltar...")
            if current.parent != current:
                current = current.parent
            continue

        selected = 0
        while True:
            clear_screen()
            print_header("SELECIONAR PASTA")
            print(f"\n  {current}\n")

            if not items:
                print("  (nenhuma subpasta)")

            for i, (name, path, is_dir) in enumerate(items):
                prefix = " > " if i == selected else "   "
                print(f"  {prefix}{name}")

            print()
            print("  ↑↓ navegar  Enter confirmar  Esc voltar  Q cancelar")

            key = read_key()
            if key == "up":
                selected = (selected - 1) % len(items) if items else 0
            elif key == "down":
                selected = (selected + 1) % len(items) if items else 0
            elif key == "enter" and items:
                name, path, is_dir = items[selected]
                if name == ".. (voltar)":
                    current = path
                    break
                current = path
                break
            elif key == "left":
                if current.parent != current:
                    current = current.parent
                    break
            elif key == "q":
                return None

        # Mostrar pasta atual como opção de seleção
        clear_screen()
        print_header("SELECIONAR PASTA")
        print(f"\n  Pasta selecionada:\n")
        print(f"  {current}\n")

        result = select_option(
            "Confirmar?",
            [f"Sim, usar esta pasta", "Não, continuar navegando"]
        )
        if result == "":
            return None
        if "Sim" in result:
            return current


def select_file(start: Path | None = None, extension: str = ".json") -> Path | None:
    current = (start or Path.cwd()).resolve()

    while True:
        clear_screen()
        print_header("SELECIONAR ARQUIVO")
        print(f"\n  {current}\n")

        items = []

        if current.parent != current:
            items.append((".. (pasta pai)", current.parent, True))

        try:
            for entry in sorted(current.iterdir()):
                if entry.name.startswith("."):
                    continue
                if entry.is_dir():
                    items.append((entry.name, entry, True))
                elif entry.suffix == extension:
                    items.append((entry.name, entry, False))
        except PermissionError:
            print_error("Sem permissão")
            input("  Enter para voltar...")
            if current.parent != current:
                current = current.parent
            continue

        if not items:
            print("  (nenhum arquivo encontrado)")

        selected = 0
        while True:
            clear_screen()
            print_header("SELECIONAR ARQUIVO")
            print(f"\n  {current}\n")

            for i, (name, path, is_dir) in enumerate(items):
                prefix = "> " if i == selected else "  "
                icon = "[D]" if is_dir else "[F]"
                print(f"  {prefix}{icon} {name}")

            print()
            print("  ↑↓ navegar  Enter selecionar  Esc voltar  Q cancelar")

            key = read_key()
            if key == "up":
                selected = (selected - 1) % len(items)
            elif key == "down":
                selected = (selected + 1) % len(items)
            elif key == "enter":
                name, path, is_dir = items[selected]
                if name == ".. (pasta pai)":
                    current = path
                    break
                if is_dir:
                    current = path
                    break
                else:
                    return path
            elif key == "left":
                if current.parent != current:
                    current = current.parent
                    break
            elif key == "q":
                return None

        # Se voltou ao loop externo sem selecionar arquivo,continuar
