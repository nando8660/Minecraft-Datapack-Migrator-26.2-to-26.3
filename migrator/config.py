"""Sistema de configuração."""
from __future__ import annotations

import json
import sys
from pathlib import Path


def get_config_path() -> Path:
    if sys.platform == "win32":
        base = Path.home() / "AppData" / "Local" / "MigradorDatapack"
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / "MigradorDatapack"
    else:
        base = Path.home() / ".config" / "MigradorDatapack"
    return base / "config.json"


DEFAULT_CONFIG = {
    "last_source": "",
    "copy_unchanged": True,
    "mode": "new_datapack",
}


def load_config() -> dict:
    path = get_config_path()
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()


def save_config(config: dict):
    path = get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")


def update_config(key: str, value):
    config = load_config()
    config[key] = value
    save_config(config)


def get_output_path(source: Path, suffix: str = "output") -> Path:
    """Gera caminho de output automático na pasta do datapack.

    Sempre retorna "<nome>-<suffix>". Se já existir um output anterior,
    ele é sobrescrito na migração (sem incremento de contador).
    """
    return source.parent / f"{source.name}-{suffix}"
