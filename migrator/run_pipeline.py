"""Pipeline completo: UI + migracao + copia pos-migracao + sistema de patch."""
from __future__ import annotations

import sys
import io
import json
import shutil
from pathlib import Path
from datetime import datetime

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
CONFIG_PATH = PROJECT_ROOT / "config.json"
REPORT_PATH = PROJECT_ROOT / "migration_report.txt"

sys.path.insert(0, str(PROJECT_ROOT))
from migrator.core.migrate import MigrationOptions, migrate_datapack, migrate_to_flat_datapack
from migrator.core.versions import VERSIONS
from migrator.core.patch import criar_manifest, ler_manifest, ler_uuid, criar_patch, aplicar_patch, buscar_patch_compativel, verificar_integridade, comparar_com_manifest
from migrator.core.zip_handler import eh_zip, extrair_zip, adicionar_ao_zip, limpar_temp
from migrator.ui.terminal.ui import (
    Menu, MenuSelecao, GerenciadorLista, ItemMenu, Cor, limpar_tela, escrever,
)
from migrator.ui.terminal.input import read_key


def carregar_config() -> dict:
    """Carrega config.json ou cria padrão."""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return _config_padrao()


def salvar_config(config: dict):
    """Salva config.json."""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def _config_padrao() -> dict:
    return {
        "datapacks": [],
        "outputs": [],
        "patches": [],
        "nomes_saida": [],
        "datapack_ativo": 0,
        "output_ativo": 0,
        "patch_ativo": 0,
        "nome_saida_ativo": 0,
        "versao": "snapshot7",
        "modo_flat": False,
        "patch_pos_migracao": False,
        "aplicar_patch": False,
        "sair_aqui": False,
        "patch_destino": "",
        "ultimo_caminho": "",
    }


def obter_versoes() -> list[tuple[str, str]]:
    """Retorna lista de (rotulo, chave) para versões."""
    return [(info["label"], chave) for chave, info in VERSIONS.items()]


# ========== MENU PRINCIPAL ==========

def menu_principal(config: dict) -> str | None:
    """Menu principal. Retorna 'migrar', 'criar_patch', 'aplicar_patch', ou None."""
    datapacks = config.get("datapacks", [])
    outputs = config.get("outputs", [])
    patches = config.get("patches", [])
    nomes_saida = config.get("nomes_saida", [])

    items = [
        ItemMenu("submenu", "Datapack:", referencia="datapack"),
        ItemMenu("submenu", "Versao alvo:", referencia="versao"),
        ItemMenu("submenu", "Saida:", referencia="saida"),
        ItemMenu("submenu", "Nome do arquivo:", referencia="nome_saida"),
        ItemMenu("toggle", "Sair aqui", referencia="sair_aqui"),
        ItemMenu("separador", ""),
        ItemMenu("toggle", "Modo", referencia="modo_flat"),
        ItemMenu("toggle", "Aplicar patch pos-migracao", referencia="patch_pos_migracao"),
        ItemMenu("separador", ""),
        ItemMenu("botao", "Migrar", referencia="migrar"),
        ItemMenu("submenu", "Patch ->", referencia="patch_menu"),
    ]

    def atualizar_estado():
        idx_dp = config.get("datapack_ativo", 0)
        idx_out = config.get("output_ativo", 0)
        idx_nome = config.get("nome_saida_ativo", 0)

        nome_dp = datapacks[idx_dp]["nome"] if datapacks else "(nenhum)"
        nome_out = outputs[idx_out]["nome"] if outputs else "(nenhum)"
        nome_arquivo = nomes_saida[idx_nome]["nome"] if nomes_saida else "(nenhum)"
        versao_label = VERSIONS.get(config.get("versao", "snapshot7"), {}).get("label", "?")

        # Caminho de saida = output + nome do arquivo selecionado
        caminho_out = ""
        if outputs:
            caminho_base = outputs[idx_out].get("caminho", "")
            caminho_out = str(Path(caminho_base) / nome_arquivo) if nome_arquivo != "(nenhum)" else caminho_base

        items[0].rotulo = f"Datapack: {nome_dp}"
        items[0].caminho = datapacks[idx_dp].get("caminho", "") if datapacks else ""
        items[1].rotulo = f"Versao alvo: {versao_label}"
        items[1].caminho = ""
        items[2].rotulo = f"Saida: {nome_out}"
        items[2].habilitado = not config.get("sair_aqui", False)
        items[2].caminho = caminho_out
        items[3].rotulo = f"Nome do arquivo: {nome_arquivo}"
        items[3].caminho = ""

        items[4].valor = config.get("sair_aqui", False)
        items[6].valor = config.get("modo_flat", False)
        items[7].valor = config.get("patch_pos_migracao", False)

    menu = Menu("MIGRADOR DE DATAPACK", items, config=config, salvar_fn=lambda: salvar_config(config), atualizar_fn=atualizar_estado)
    cursor_salvo = 0

    while True:
        atualizar_estado()
        menu.items = items
        menu.cursor = cursor_salvo
        resultado = menu.executar()
        acao, referencia, cursor = resultado
        cursor_salvo = cursor

        if acao == "sair":
            return None

        if acao == "botao" and referencia == "migrar":
            if not datapacks:
                _mostrar_mensagem("Adicione pelo menos um datapack!")
                continue
            if not outputs:
                _mostrar_mensagem("Adicione pelo menos uma saida!")
                continue
            return "migrar"

        if acao == "submenu" and referencia == "versao":
            _selecionar_versao(config)
        elif acao == "submenu" and referencia == "datapack":
            novos, novo_idx = GerenciadorLista("Datapacks", datapacks, ultimo_caminho=config.get("ultimo_caminho", "")).executar()
            config["datapacks"] = novos
            config["datapack_ativo"] = min(novo_idx, max(0, len(novos) - 1))
            if novos:
                config["ultimo_caminho"] = novos[min(novo_idx, len(novos) - 1)].get("caminho", "")
            salvar_config(config)
        elif acao == "submenu" and referencia == "saida":
            novos, novo_idx = GerenciadorLista("Saidas", outputs, ultimo_caminho=config.get("ultimo_caminho", "")).executar()
            config["outputs"] = novos
            config["output_ativo"] = min(novo_idx, max(0, len(novos) - 1))
            if novos:
                config["ultimo_caminho"] = novos[min(novo_idx, len(novos) - 1)].get("caminho", "")
            salvar_config(config)
        elif acao == "submenu" and referencia == "nome_saida":
            novos, novo_idx = GerenciadorLista("Nomes de Saida", nomes_saida, modo_nome=True).executar()
            config["nomes_saida"] = novos
            config["nome_saida_ativo"] = min(novo_idx, max(0, len(novos) - 1)) if novos else 0
            salvar_config(config)
        elif acao == "submenu" and referencia == "patch_menu":
            resultado_patch = menu_patch(config)
            if resultado_patch:
                return resultado_patch


def menu_patch(config: dict) -> str | None:
    """Submenu dedicado a patches."""
    patches = config.get("patches", [])
    patch_dest = config.get("patch_destino", "")

    items = [
        ItemMenu("submenu", "Onde salvar Patches:", referencia="patch_destino"),
        ItemMenu("separador", ""),
        ItemMenu("botao", "Criar Patch", referencia="criar_patch"),
        ItemMenu("botao", "Aplicar Patch", referencia="aplicar_patch"),
        ItemMenu("separador", ""),
        ItemMenu("botao", "Voltar", referencia="voltar"),
    ]

    menu = Menu("PATCH", items, config=config, salvar_fn=lambda: salvar_config(config))
    cursor_salvo = 0

    while True:
        patch_dest = config.get("patch_destino", "")
        items[0].rotulo = f"Onde salvar Patches: {patch_dest or '(nao definido)'}"
        items[0].caminho = patch_dest if patch_dest else ""

        menu.items = items
        menu.cursor = cursor_salvo
        resultado = menu.executar()
        acao, referencia, cursor = resultado
        cursor_salvo = cursor

        if acao == "sair" or (acao == "botao" and referencia == "voltar"):
            return None

        if acao == "submenu" and referencia == "patch_destino":
            novo_caminho = _pedir_caminho_dialog("Onde salvar Patches")
            if novo_caminho:
                config["patch_destino"] = novo_caminho
                config["ultimo_caminho"] = novo_caminho
                salvar_config(config)

        if acao == "botao" and referencia == "criar_patch":
            return "criar_patch"

        if acao == "botao" and referencia == "aplicar_patch":
            return "aplicar_patch"


# ========== ACOES ==========

def executar_migracao(config: dict) -> str:
    """Executa a migracao. Retorna resumo."""
    idx_dp = config.get("datapack_ativo", 0)
    idx_out = config.get("output_ativo", 0)
    datapacks = config.get("datapacks", [])
    outputs = config.get("outputs", [])

    source = Path(datapacks[idx_dp]["caminho"])
    nome_input = datapacks[idx_dp].get("nome", source.name)

    # Detecta zip e extrai se necessario
    zip_extraido = None
    if eh_zip(source):
        limpar_temp()
        zip_extraido = source
        source = extrair_zip(source)
        escrever(f"  [INFO] Zip extraido: {zip_extraido.name}\n")

        # Cria/adiciona UUID no zip antes de migrar
        uuid_path_temp = source / ".datapack_uuid"
        if not uuid_path_temp.exists():
            import uuid as uuid_mod
            uuid_valor = str(uuid_mod.uuid4())
            uuid_path_temp.write_text(uuid_valor, encoding="utf-8")
        # Adiciona UUID ao zip original
        adicionar_ao_zip(zip_extraido, uuid_path_temp, ".datapack_uuid")

    # Determina nome do arquivo de saida
    idx_nome = config.get("nome_saida_ativo", 0)
    nomes_saida = config.get("nomes_saida", [])
    nome_arquivo = nomes_saida[idx_nome]["nome"] if nomes_saida else None

    if config.get("sair_aqui", False):
        if nome_arquivo:
            destination = PROJECT_ROOT / "output" / nome_arquivo
        else:
            destination = PROJECT_ROOT / "output"
    else:
        # Usa nome do arquivo selecionado no caminho de saida
        caminho_base = outputs[idx_out]["caminho"] if outputs else ""
        destination = Path(caminho_base) / nome_arquivo if nome_arquivo and nome_arquivo != "(nenhum)" else Path(caminho_base)

    # Subdividir output em flat/overlay quando sair_aqui
    if config.get("sair_aqui", False):
        modo_flat = config.get("modo_flat", False)
        idx_nome = config.get("nome_saida_ativo", 0)
        nomes_saida = config.get("nomes_saida", [])
        nome_arquivo = nomes_saida[idx_nome]["nome"] if nomes_saida else "datapack"
        subpasta = "flat" if modo_flat else "overlay"
        destination = PROJECT_ROOT / "output" / subpasta / nome_arquivo

    version = config.get("versao", "snapshot7")
    modo_flat = config.get("modo_flat", False)

    # Flat sempre copia tudo; overlay só copia modificados
    copy_unchanged = True if modo_flat else False

    options = MigrationOptions(
        destination=destination,
        mode="flat_datapack" if modo_flat else "new_datapack",
        target_version=version,
        copy_unchanged=copy_unchanged,
    )

    if modo_flat:
        report = migrate_to_flat_datapack(source, options)
    else:
        report = migrate_datapack(source, options)

    # Gerencia UUID: prioriza input, depois config, depois cria novo
    uuid_valor = ler_uuid(source)

    if not uuid_valor:
        uuids = config.get("uuids", {})
        uuid_valor = uuids.get(nome_input)
        if not uuid_valor:
            import uuid as uuid_mod
            uuid_valor = str(uuid_mod.uuid4())

    # Salva UUID no INPUT (sobrevive a renomeacao/mudanca de local)
    uuid_path_input = source / ".datapack_uuid"
    uuid_path_input.write_text(uuid_valor, encoding="utf-8")

    # Cria manifest no OUTPUT (com UUID do input)
    criar_manifest(destination, nome=destination.name, uuid_valor=uuid_valor)
    salvar_config(config)

    # Aplicar patch automatico se configurado
    if config.get("patch_pos_migracao", False):
        patch_dest = Path(config.get("patch_destino", "."))
        if patch_dest.exists():
            patch_compativel = buscar_patch_compativel(destination, patch_dest)
            if patch_compativel:
                escrever(f"\n  [INFO] Patch compativel encontrado: {patch_compativel.name}")
                stats = aplicar_patch(destination, patch_compativel)
                escrever(f"  [INFO] Patch aplicado: {stats['copiados']} copiados, {stats['removidos']} removidos")
            else:
                escrever(f"\n  [INFO] Nenhum patch compativel encontrado em {patch_dest}")
        else:
            escrever(f"\n  [INFO] Pasta de patches nao encontrada: {patch_dest}")

    # Limpa temp se foi extraido de zip
    limpar_temp()

    return report.summary()


def executar_criar_patch(config: dict) -> dict:
    """Acao de criar patch."""
    idx_out = config.get("output_ativo", 0)
    idx_nome = config.get("nome_saida_ativo", 0)
    outputs = config.get("outputs", [])
    nomes_saida = config.get("nomes_saida", [])
    patch_destino = Path(config.get("patch_destino", "."))

    if not outputs:
        return {"erro": "Nenhuma saida configurada!"}

    # Usa nome do arquivo selecionado
    nome_arquivo = nomes_saida[idx_nome]["nome"] if nomes_saida else None
    caminho_base = outputs[idx_out]["caminho"] if outputs else ""
    datapack_path = Path(caminho_base) / nome_arquivo if nome_arquivo else Path(caminho_base)
    if not datapack_path.exists():
        return {"erro": f"Datapack nao encontrado: {datapack_path}"}

    manifest = ler_manifest(datapack_path)
    if not manifest:
        return {"erro": f"Sem manifest em {datapack_path}. Migre o datapack primeiro."}

    if not verificar_integridade(datapack_path, manifest):
        return {"erro": "Manifest foi alterado manualmente. Migre novamente para criar um patch valido."}

    nome_base = manifest.get("datapack", datapack_path.name)
    patch_path, stats = criar_patch(datapack_path, patch_destino, nome_base)

    return {
        "patch_path": str(patch_path),
        "modificados": stats["modificados"],
        "adicionados": stats["adicionados"],
        "removidos": stats["removidos"],
    }


def executar_aplicar_patch(config: dict) -> dict:
    """Acao de aplicar patch."""
    idx_out = config.get("output_ativo", 0)
    idx_nome = config.get("nome_saida_ativo", 0)
    outputs = config.get("outputs", [])
    nomes_saida = config.get("nomes_saida", [])
    patch_destino = Path(config.get("patch_destino", "."))

    if not outputs:
        return {"erro": "Nenhuma saida configurada!"}

    # Usa nome do arquivo selecionado
    nome_arquivo = nomes_saida[idx_nome]["nome"] if nomes_saida else None
    caminho_base = outputs[idx_out]["caminho"] if outputs else ""
    datapack_path = Path(caminho_base) / nome_arquivo if nome_arquivo else Path(caminho_base)
    if not datapack_path.exists():
        return {"erro": f"Datapack nao encontrado: {datapack_path}"}

    if not patch_destino.exists():
        return {"erro": f"Pasta de patches nao encontrada: {patch_destino}"}

    # Lista patches disponiveis
    patches = [d for d in patch_destino.iterdir() if d.is_dir()]
    if not patches:
        return {"erro": f"Nenhum patch em {patch_destino}"}

    # Por enquanto, usa o mais recente
    patches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    patch_path = patches[0]

    stats = aplicar_patch(datapack_path, patch_path)
    # Atualiza manifest para o estado atual (pos-patch)
    nome_base = datapack_path.name
    criar_manifest(datapack_path, nome_base)
    return {
        "patch_path": str(patch_path),
        "copiados": stats["copiados"],
        "removidos": stats["removidos"],
    }


# ========== HELPERS ==========

def _selecionar_versao(config: dict):
    """Abre menu de selecao de versao."""
    versoes = obter_versoes()
    atual = config.get("versao", "snapshot7")
    idx_atual = [v[1] for v in versoes].index(atual) if atual in [v[1] for v in versoes] else 0
    menu = MenuSelecao("Selecionar Versao", versoes, cursor_inicial=idx_atual)
    resultado = menu.executar()
    if resultado:
        config["versao"] = resultado
        salvar_config(config)


def _pedir_caminho_dialog(mensagem: str) -> str | None:
    """Abre dialogo de selecao de pasta via tkinter."""
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.lift()
        root.attributes("-topmost", True)
        root.focus_force()

        caminho = filedialog.askdirectory(title=mensagem, parent=root)
        root.destroy()
        return caminho if caminho else None
    except Exception:
        return None


def _mostrar_mensagem(msg: str):
    """Mostra mensagem e espera Enter."""
    limpar_tela()
    escrever(f"\n  {Cor.ALERTA}{msg}{Cor.RESET}\n\n  Pressione Enter...\n")
    sys.stdout.flush()
    while True:
        from migrator.ui.terminal.input import read_key
        if read_key() == "enter":
            break


def escrever_relatorio(resumo: str, post_count: int, post_files: list[str]):
    """Escreve relatorio em arquivo UTF-8."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        f"Relatorio de Migracao - {timestamp}",
        "=" * 60,
        "",
        resumo,
        "",
        f"Pos-migracao: {post_count} arquivo(s) copiado(s)",
    ]
    if post_files:
        lines.append("Arquivos copiados:")
        for f in post_files:
            lines.append(f"  + {f}")

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


# ========== MAIN ==========

def main():
    while True:
        limpar_tela()
        escrever(f"{Cor.NEGRITO}MIGRADOR DE DATAPACK{Cor.RESET}\n  Carregando...\n")
        config = carregar_config()

        # UI - menu principal
        acao = menu_principal(config)
        if not acao:
            limpar_tela()
            escrever("Cancelado.\n")
            return 0

        # Executa acao
        limpar_tela()

        if acao == "migrar":
            escrever(f"{Cor.NEGRITO}MIGRANDO...{Cor.RESET}\n\n")
            try:
                resumo = executar_migracao(config)
                escrever(resumo)
            except Exception as e:
                escrever(f"\n{Cor.ERRO}[ERRO] {e}{Cor.RESET}\n")
                import traceback
                traceback.print_exc()
                escrever(f"\n  {Cor.DESABILITADO}Pressione qualquer tecla para voltar...{Cor.RESET}")
                read_key()
                continue

            escrever_relatorio(resumo, 0, [])
            escrever(f"\n  Relatorio salvo em: {REPORT_PATH}\n")

        elif acao == "criar_patch":
            escrever(f"{Cor.NEGRITO}CRIANDO PATCH...{Cor.RESET}\n\n")
            resultado = executar_criar_patch(config)
            if "erro" in resultado:
                escrever(f"\n{Cor.ERRO}[ERRO] {resultado['erro']}{Cor.RESET}\n")
                escrever(f"\n  {Cor.DESABILITADO}Pressione qualquer tecla para voltar...{Cor.RESET}")
                read_key()
                continue
            escrever(f"  Patch criado: {resultado['patch_path']}\n")
            escrever(f"  Modificados: {resultado['modificados']}\n")
            escrever(f"  Adicionados: {resultado['adicionados']}\n")
            escrever(f"  Removidos: {resultado['removidos']}\n")

        elif acao == "aplicar_patch":
            escrever(f"{Cor.NEGRITO}APLICANDO PATCH...{Cor.RESET}\n\n")
            resultado = executar_aplicar_patch(config)
            if "erro" in resultado:
                escrever(f"\n{Cor.ERRO}[ERRO] {resultado['erro']}{Cor.RESET}\n")
                escrever(f"\n  {Cor.DESABILITADO}Pressione qualquer tecla para voltar...{Cor.RESET}")
                read_key()
                continue
            escrever(f"  Patch aplicado: {resultado['patch_path']}\n")
            escrever(f"  Copiados: {resultado['copiados']}\n")
            escrever(f"  Removidos: {resultado['removidos']}\n")

        escrever(f"\n  {Cor.SELECAO} CONCLUIDO! {Cor.RESET}\n")
        escrever(f"\n  {Cor.DESABILITADO}Pressione qualquer tecla para voltar ao menu...{Cor.RESET}")
        read_key()


if __name__ == "__main__":
    sys.exit(main())
