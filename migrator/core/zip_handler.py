"""Handler para arquivos zip."""
from __future__ import annotations

import os
import zipfile
import shutil
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
TEMP_DIR = PROJECT_ROOT / "temp_migration"


def eh_zip(caminho: Path) -> bool:
    """Detecta zip pela extensao."""
    return caminho.suffix.lower() == ".zip"


def extrair_zip(zip_path: Path) -> Path:
    """Extrai zip para temp_migration/<nome>/."""
    destino = TEMP_DIR / zip_path.stem
    if destino.exists():
        shutil.rmtree(destino)
    destino.mkdir(parents=True)
    with zipfile.ZipFile(zip_path, 'r') as z:
        z.extractall(destino)
    return destino


def adicionar_ao_zip(zip_path: Path, arquivo_path: Path, nome_no_zip: str = None):
    """Adiciona um arquivo a um zip existente. Remove versões antigas do mesmo nome antes."""
    if nome_no_zip is None:
        nome_no_zip = arquivo_path.name
    # Remove entradas antigas com mesmo nome/base antes de adicionar
    _remover_do_zip(zip_path, nome_no_zip)
    with zipfile.ZipFile(zip_path, 'a') as z:
        z.write(arquivo_path, nome_no_zip)


def _remover_do_zip(zip_path: Path, nome_alvo: str):
    """Remove todas as entradas do zip cujo basename == nome_alvo."""
    if not zip_path.exists():
        return
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".zip", dir=zip_path.parent)
    os.close(tmp_fd)
    with zipfile.ZipFile(zip_path, 'r') as zin:
        with zipfile.ZipFile(tmp_path, 'w') as zout:
            for item in zin.infolist():
                if os.path.basename(item.filename) != nome_alvo:
                    zout.writestr(item, zin.read(item.filename))
    os.replace(tmp_path, zip_path)


def limpar_temp():
    """Remove pasta temp_migration."""
    if TEMP_DIR.exists():
        shutil.rmtree(TEMP_DIR)
