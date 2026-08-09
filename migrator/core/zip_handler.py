"""Handler para arquivos zip."""
from __future__ import annotations

import zipfile
import shutil
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
    """Adiciona um arquivo a um zip existente (so se nao estiver la)."""
    if nome_no_zip is None:
        nome_no_zip = arquivo_path.name
    with zipfile.ZipFile(zip_path, 'a') as z:
        # Verifica se o arquivo ja existe no zip
        existing_names = z.namelist()
        if nome_no_zip not in existing_names:
            z.write(arquivo_path, nome_no_zip)


def limpar_temp():
    """Remove pasta temp_migration."""
    if TEMP_DIR.exists():
        shutil.rmtree(TEMP_DIR)
