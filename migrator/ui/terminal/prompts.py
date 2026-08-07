"""Interface de terminal - Prompts."""
from __future__ import annotations

from pathlib import Path


def prompt_yes_no(message: str, default: bool = True) -> bool:
    suffix = " [S/n]" if default else " [s/N]"
    while True:
        response = input(f"  {message}{suffix}: ").strip().lower()
        if not response:
            return default
        if response in ("s", "sim", "y", "yes"):
            return True
        if response in ("n", "nao", "não", "no"):
            return False
        print("  Resposta inválida. Digite 's' ou 'n'.")


def prompt_choice(message: str, options: list[str], default: int = 0) -> int:
    print(f"\n  {message}:")
    for i, option in enumerate(options):
        marker = "→" if i == default else " "
        print(f"  {marker} [{i + 1}] {option}")

    while True:
        try:
            response = input(f"\n  Selecione (1-{len(options)}) [{default + 1}]: ").strip()
            if not response:
                return default
            index = int(response) - 1
            if 0 <= index < len(options):
                return index
            print(f"  Digite um número entre 1 e {len(options)}.")
        except ValueError:
            print("  Digite um número válido.")


def prompt_path(message: str, must_exist: bool = True) -> Path | None:
    while True:
        response = input(f"  {message}: ").strip()

        if not response:
            return None

        path = Path(response)

        if must_exist and not path.exists():
            print(f"  Caminho não encontrado: {path}")
            continue

        return path


def prompt_text(message: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    response = input(f"  {message}{suffix}: ").strip()
    return response if response else default
