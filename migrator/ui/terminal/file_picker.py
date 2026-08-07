"""Seleção de pasta via diálogo nativo do Windows."""
from __future__ import annotations

import sys
import os
from pathlib import Path


def select_folder_native(title: str = "Selecionar pasta") -> Path | None:
    """Abre o diálogo nativo de seleção de pasta do Windows."""
    if sys.platform == "win32":
        try:
            # Corrigir DPI scaling no Windows
            import ctypes
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(2)
            except Exception:
                try:
                    ctypes.windll.user32.SetProcessDPIAware()
                except Exception:
                    pass

            import tkinter as tk
            from tkinter import filedialog

            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)

            folder = filedialog.askdirectory(title=title)
            root.destroy()

            if folder:
                return Path(folder)
            return None
        except Exception:
            return _select_folder_fallback(title)
    else:
        return _select_folder_fallback(title)


def _select_folder_fallback(title: str) -> Path | None:
    """Fallback para sistemas sem tkinter."""
    from .input import read_key
    from .dialogs import clear_screen, print_header

    current = Path.home().resolve()

    while True:
        items = []

        if current.parent != current:
            items.append((".. (voltar)", current.parent))

        try:
            for entry in sorted(current.iterdir()):
                if entry.is_dir() and not entry.name.startswith("."):
                    items.append((entry.name, entry))
        except PermissionError:
            current = current.parent
            continue

        selected = 0
        while True:
            clear_screen()
            print_header(title)
            print(f"\n  {current}\n")

            for i, (name, path) in enumerate(items):
                prefix = " > " if i == selected else "   "
                print(f"  {prefix}{name}")

            print()
            print("  ↑↓ navegar  Enter selecionar  Esc voltar  Q cancelar")

            key = read_key()
            if key == "up":
                selected = (selected - 1) % len(items) if items else 0
            elif key == "down":
                selected = (selected + 1) % len(items) if items else 0
            elif key == "enter" and items:
                name, path = items[selected]
                if name == ".. (voltar)":
                    current = path
                    break
                current = path
                break
            elif key == "left":
                if current.parent != current:
                    current = path.parent
                    break
            elif key == "q":
                return None

        # Confirmar seleção
        clear_screen()
        print_header(title)
        print(f"\n  Pasta:\n  {current}\n")

        from .dialogs import select_option
        result = select_option("Confirmar?", ["Sim", "Não"])
        if result == "":
            return None
        if result == "Sim":
            return current
