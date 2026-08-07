"""Auto-instalador de dependências.

Roda antes de tudo e instala bibliotecas listadas em requirements.txt
que ainda não estão instaladas.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def get_requirements_path() -> Path:
    return Path(__file__).parent.parent.parent / "requirements.txt"


def get_installed_packages() -> dict[str, str]:
    result = subprocess.run(
        [sys.executable, "-m", "pip", "list", "--format=json"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return {}
    import json
    packages = json.loads(result.stdout)
    return {p["name"].lower(): p["version"] for p in packages}


def parse_requirements(path: Path) -> list[str]:
    if not path.exists():
        return []
    packages = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        packages.append(line)
    return packages


def install_package(package: str) -> bool:
    print(f"  Instalando {package}...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", package],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"  [ERRO] Falha ao instalar {package}")
        print(f"  {result.stderr.strip()}")
        return False
    print(f"  [OK] {package} instalado")
    return True


def ensure_dependencies() -> bool:
    req_path = get_requirements_path()
    required = parse_requirements(req_path)

    if not required:
        return True

    installed = get_installed_packages()
    missing = []

    for req in required:
        pkg_name = req.split("==")[0].split(">=")[0].split("<=")[0].split("!=")[0].strip().lower()
        if pkg_name not in installed:
            missing.append(req)

    if not missing:
        return True

    print(f"\n  {len(missing)} dependência(s) faltando:")
    for pkg in missing:
        print(f"    - {pkg}")

    print()
    for pkg in missing:
        if not install_package(pkg):
            return False

    return True


if __name__ == "__main__":
    if ensure_dependencies():
        print("\n  Todas as dependências instaladas.")
    else:
        print("\n  Erro ao instalar dependências.")
        sys.exit(1)
