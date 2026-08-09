"""Sistema de patch para datapacks migrados."""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


def criar_manifest(datapack_path: Path, nome: str, uuid_valor: str | None = None) -> dict:
    """Cria .migration_manifest.json na raiz do datapack (registro POS-migracao).
    UUID fica em arquivo separado (.datapack_uuid) para ser independente.
    Se uuid_valor for fornecido, usa ele (prioridade sobre arquivo local).
    """
    # Determina UUID: prioriza argumento, depois arquivo local, depois cria novo
    uuid_path = datapack_path / ".datapack_uuid"
    if uuid_valor:
        uuid_path.write_text(uuid_valor, encoding="utf-8")
    elif uuid_path.exists():
        uuid_valor = uuid_path.read_text(encoding="utf-8").strip()
    else:
        uuid_valor = str(uuid.uuid4())
        uuid_path.write_text(uuid_valor, encoding="utf-8")

    manifest = {
        "versao": "1.0",
        "timestamp": datetime.now().isoformat(),
        "uuid": uuid_valor,
        "datapack": nome,
        "arquivos": {}
    }

    # Registra estado ATUAL (pos-migracao/pos-alteracoes)
    for arquivo in datapack_path.rglob("*"):
        if arquivo.is_file() and arquivo.name not in (".migration_manifest.json", ".datapack_uuid"):
            relativo = str(arquivo.relative_to(datapack_path)).replace("\\", "/")
            manifest["arquivos"][relativo] = {
                "hash": hashlib.md5(arquivo.read_bytes()).hexdigest()
            }

    caminho_manifest = datapack_path / ".migration_manifest.json"
    caminho_manifest.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    return manifest


def ler_uuid(datapack_path: Path) -> str | None:
    """Le UUID do arquivo .datapack_uuid."""
    uuid_path = datapack_path / ".datapack_uuid"
    if uuid_path.exists():
        return uuid_path.read_text(encoding="utf-8").strip()
    return None


def ler_manifest(datapack_path: Path) -> dict | None:
    """Le .migration_manifest.json. Retorna None se nao existir.
    Se o manifesto estiver no formato antigo (tamanho/data), reconstrói com hash."""
    caminho = datapack_path / ".migration_manifest.json"
    if not caminho.exists():
        return None
    try:
        data = json.loads(caminho.read_text(encoding="utf-8"))
        # Garante que UUID existe (prioriza arquivo separado)
        uuid_valor = ler_uuid(datapack_path)
        if uuid_valor:
            data["uuid"] = uuid_valor
        elif "uuid" not in data:
            data["uuid"] = str(uuid.uuid4())
            caminho.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        # Detecta formato antigo (tem "tamanho" em vez de "hash") e reconstrói
        arquivos = data.get("arquivos", {})
        if arquivos and any("hash" not in v for v in arquivos.values()):
            # Reconstrói manifest com hashes
            nome = data.get("datapack", datapack_path.name)
            return criar_manifest(datapack_path, nome, data.get("uuid"))
        return data
    except (json.JSONDecodeError, KeyError):
        return None


def verificar_integridade(datapack_path: Path, manifest: dict) -> bool:
    """Verifica se o manifest nao foi alterado manualmente."""
    caminho = datapack_path / ".migration_manifest.json"
    if not caminho.exists():
        return False
    try:
        data = json.loads(caminho.read_text(encoding="utf-8"))
        return data.get("timestamp") == manifest.get("timestamp")
    except Exception:
        return False


def comparar_com_manifest(datapack_path: Path, manifest: dict) -> dict:
    """Compara estado atual do datapack com o manifest.
    Retorna {modificados, adicionados, removidos}.
    Usa hash MD5 do conteudo para detectar qualquer mudanca, independente do timestamp.
    """
    arquivos_manifest = manifest.get("arquivos", {})
    estado_atual = {}

    for arquivo in datapack_path.rglob("*"):
        if arquivo.is_file() and arquivo.name not in (".migration_manifest.json", ".datapack_uuid"):
            relativo = str(arquivo.relative_to(datapack_path)).replace("\\", "/")
            estado_atual[relativo] = {
                "hash": hashlib.md5(arquivo.read_bytes()).hexdigest()
            }

    modificados = []
    adicionados = []
    removidos = []

    for rel, info in estado_atual.items():
        if rel in arquivos_manifest:
            if info["hash"] != arquivos_manifest[rel].get("hash"):
                modificados.append(rel)
        else:
            adicionados.append(rel)

    for rel in arquivos_manifest:
        if rel not in estado_atual:
            removidos.append(rel)

    return {
        "modificados": modificados,
        "adicionados": adicionados,
        "removidos": removidos,
    }


def criar_patch(datapack_path: Path, destino: Path, nome_base: str) -> tuple[Path, dict]:
    """Cria pasta do patch com arquivos modificados/adicionados + removimentos.txt.
    Se ja existir, incrementa com _2, _3, etc.
    Retorna (caminho_patch, estatisticas).
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nome_pasta = f"patch_{nome_base}_{timestamp}"

    # Verifica duplicatas e incrementa
    patch_path = destino / nome_pasta
    contador = 2
    while patch_path.exists():
        patch_path = destino / f"{nome_pasta}_{contador}"
        contador += 1

    patch_path.mkdir(parents=True, exist_ok=True)

    manifest = ler_manifest(datapack_path)
    if not manifest:
        return patch_path, {"modificados": 0, "adicionados": 0, "removidos": 0}

    comparacao = comparar_com_manifest(datapack_path, manifest)

    # Copia arquivos modificados e adicionados
    for rel in comparacao["modificados"] + comparacao["adicionados"]:
        origem = datapack_path / rel
        destino_arquivo = patch_path / rel
        destino_arquivo.parent.mkdir(parents=True, exist_ok=True)
        destino_arquivo.write_bytes(origem.read_bytes())

    # Cria removimentos.txt se houver removidos
    if comparacao["removidos"]:
        removimentos_path = patch_path / "removimentos.txt"
        linhas = ["# Arquivos removidos - aplique com 'Aplicar Patch'\n"]
        linhas.extend(sorted(comparacao["removidos"]))
        removimentos_path.write_text("\n".join(linhas), encoding="utf-8")


    # Copia arquivos de rastreamento pro patch
    manifest_patch = patch_path / ".migration_manifest.json"
    manifest_patch.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    uuid_patch = patch_path / ".datapack_uuid"
    uuid_patch.write_text(manifest.get("uuid", ""), encoding="utf-8")

    return patch_path, {
        "modificados": len(comparacao["modificados"]),
        "adicionados": len(comparacao["adicionados"]),
        "removidos": len(comparacao["removidos"]),
    }


def buscar_patch_compativel(datapack_path: Path, patch_destino: Path) -> Path | None:
    """Busca patch compativel por UUID."""
    uuid_atual = ler_uuid(datapack_path)
    if not uuid_atual:
        return None

    melhores = []
    for pasta in patch_destino.iterdir():
        if not pasta.is_dir():
            continue
        # Busca UUID no arquivo separado ou no manifest
        patch_uuid = ler_uuid(pasta)
        if not patch_uuid:
            patch_manifest_path = pasta / ".migration_manifest.json"
            if patch_manifest_path.exists():
                try:
                    patch_manifest = json.loads(patch_manifest_path.read_text(encoding="utf-8"))
                    patch_uuid = patch_manifest.get("uuid")
                except Exception:
                    continue
        if patch_uuid == uuid_atual:
            manifest_path = pasta / ".migration_manifest.json"
            timestamp = ""
            if manifest_path.exists():
                try:
                    m = json.loads(manifest_path.read_text(encoding="utf-8"))
                    timestamp = m.get("timestamp", "")
                except Exception:
                    pass
            melhores.append((timestamp, pasta))

    if not melhores:
        return None

    # Retorna o mais recente (timestamp mais alto)
    melhores.sort(key=lambda x: x[0], reverse=True)
    return melhores[0][1]


def aplicar_patch(datapack_path: Path, patch_path: Path) -> dict:
    """Aplica patch no datapack: copia arquivos + remove listados em removimentos.txt."""
    stats = {"copiados": 0, "removidos": 0}

    for arquivo in patch_path.rglob("*"):
        if arquivo.is_file() and arquivo.name != ".migration_manifest.json" and arquivo.name != "removimentos.txt":
            relativo = arquivo.relative_to(patch_path)
            destino = datapack_path / relativo
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_bytes(arquivo.read_bytes())
            stats["copiados"] += 1

    # Processa removimentos.txt
    removimentos_path = patch_path / "removimentos.txt"
    if removimentos_path.exists():
        linhas = removimentos_path.read_text(encoding="utf-8").splitlines()
        for linha in linhas:
            linha = linha.strip()
            if not linha or linha.startswith("#"):
                continue
            arquivo_remover = datapack_path / linha
            if arquivo_remover.exists():
                arquivo_remover.unlink()
                stats["removidos"] += 1

    return stats
