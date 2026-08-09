"""Sistema de UI terminal para o Migrador de Datapack."""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Any, Callable

# DPI awareness ANTES de qualquer import tkinter
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass

from .input import read_key


class Cor:
    """Cores semânticas — nomes descrevem função, não aparência visual."""
    RESET = "\033[0m"
    NEGRITO = "\033[1m"
    SELECAO = "\033[42m\033[97m\033[1m"   # fundo verde + texto branco + negrito
    DESABILITADO = "\033[90m"              # item inativo/cinza
    SEPARADOR = "\033[38;5;240m"           # linhas divisórias
    ALERTA = "\033[33m"                    # mensagens de aviso
    ERRO = "\033[31m"                      # mensagens de erro

    @staticmethod
    def init_windows():
        if sys.platform == "win32":
            try:
                import ctypes
                kernel32 = ctypes.windll.kernel32
                kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
            except Exception:
                pass


Cor.init_windows()


def limpar_tela():
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()


def escrever(texto: str):
    sys.stdout.write(texto)
    sys.stdout.flush()


@dataclass
class ItemMenu:
    """Item de menu."""
    tipo: str  # "toggle", "submenu", "acao", "botao", "exibir", "separador"
    rotulo: str
    valor: Any = None
    habilitado: bool = True
    referencia: str = ""  # chave no config
    sufixo: str = ""       # texto discreto em cinza (ex: "não afeta modo flat")
    acao: Callable | None = None


class Menu:
    """Menu interativo com navegação por setas."""

    def __init__(self, titulo: str, items: list[ItemMenu], cursor_inicial: int = 0, config: dict = None, salvar_fn=None):
        self.titulo = titulo
        self.items = items
        self.cursor = cursor_inicial
        self.config = config or {}
        self.salvar_fn = salvar_fn
        self._mover_cursor_valido(0)

    def _salvar_toggle(self, item: ItemMenu):
        """Salva valor do toggle no config e persiste."""
        if item.referencia and item.tipo == "toggle":
            self.config[item.referencia] = item.valor
            if self.salvar_fn:
                self.salvar_fn()

    def _mover_cursor_valido(self, direcao: int):
        """Move cursor ignorando itens desabilitados e separadores."""
        n = len(self.items)
        for _ in range(n):
            self.cursor = (self.cursor + direcao) % n
            item = self.items[self.cursor]
            if item.habilitado and item.tipo != "separador":
                return

    def renderizar(self):
        """Desenha o menu na tela."""
        limpar_tela()
        escrever(f"{Cor.NEGRITO}{self.titulo}{Cor.RESET}\n\n")
        for i, item in enumerate(self.items):
            if item.tipo == "separador":
                escrever(f"  {Cor.SEPARADOR}────────────────────────────────────{Cor.RESET}\n")
                continue

            prefixo = "▶ " if i == self.cursor else "  "
            if i == self.cursor:
                cor_inicio = Cor.SELECAO
                sufixo = Cor.RESET
            elif not item.habilitado:
                cor_inicio = Cor.DESABILITADO
                sufixo = Cor.RESET
            else:
                cor_inicio = ""
                sufixo = ""

            texto = self._formatar_item(item)
            # Sufixo (texto discreto em cinza)
            texto_sufixo = f"  {Cor.DESABILITADO}{item.sufixo}{Cor.RESET}" if item.sufixo and i != self.cursor else ""
            escrever(f"  {cor_inicio}{prefixo}{texto}{sufixo}{texto_sufixo}\n")
        escrever(f"\n  {Cor.DESABILITADO}↑↓ Enter | Q Voltar{Cor.RESET}\n")

    def _formatar_item(self, item: ItemMenu) -> str:
        if item.tipo == "toggle":
            if item.referencia == "modo_flat":
                val = "flat" if item.valor else "novo overlay"
                return f"{item.rotulo}: [{val}]"
            val = "sim" if item.valor else "não"
            return f"{item.rotulo}: [{val}]"
        if item.tipo == "exibir":
            val = str(item.valor) if item.valor else "(não definido)"
            return f"{item.rotulo}: {val}"
        return item.rotulo

    def executar(self) -> tuple[str, Any]:
        """Loop do menu. Retorna (acao, valor) quando usuário confirma."""
        while True:
            self.renderizar()
            tecla = read_key()
            if tecla == "up":
                self._mover_cursor_valido(-1)
            elif tecla == "down":
                self._mover_cursor_valido(1)
            elif tecla == "enter":
                item = self.items[self.cursor]
                if item.tipo == "toggle":
                    item.valor = not item.valor
                    self._salvar_toggle(item)
                elif item.tipo in ("submenu", "acao", "botao"):
                    return (item.tipo, item.referencia, self.cursor)
            elif tecla == "q":
                return ("sair", None, self.cursor)


class MenuSelecao:
    """Menu de seleção única (ex: versões)."""

    def __init__(self, titulo: str, opcoes: list[tuple[str, str]], cursor_inicial: int = 0):
        self.titulo = titulo
        self.opcoes = opcoes  # [(rotulo, valor), ...]
        self.cursor = cursor_inicial

    def executar(self) -> str | None:
        """Retorna valor selecionado ou None se cancelado."""
        while True:
            limpar_tela()
            escrever(f"{Cor.NEGRITO}{self.titulo}{Cor.RESET}\n\n")
            for i, (rotulo, _) in enumerate(self.opcoes):
                prefixo = "▶ " if i == self.cursor else "  "
                cor = Cor.SELECAO if i == self.cursor else ""
                reset = Cor.RESET if i == self.cursor else ""
                escrever(f"  {cor}{prefixo}{rotulo}{reset}\n")
            escrever(f"\n  {Cor.DESABILITADO}↑↓ Enter selecionar | Q Voltar{Cor.RESET}\n")

            tecla = read_key()
            if tecla == "up":
                self.cursor = (self.cursor - 1) % len(self.opcoes)
            elif tecla == "down":
                self.cursor = (self.cursor + 1) % len(self.opcoes)
            elif tecla == "enter":
                return self.opcoes[self.cursor][1]
            elif tecla == "q":
                return None


class GerenciadorLista:
    """Lista com adicionar/remover/editar (ex: datapacks, saídas, nomes)."""

    def __init__(self, titulo: str, itens: list[dict], cursor_inicial: int = 0, ultimo_caminho: str = "", modo_nome: bool = False):
        self.titulo = titulo
        self.itens = itens
        self.cursor = cursor_inicial
        self._ultimo_caminho = ultimo_caminho
        self.modo_nome = modo_nome

    def _adicionar_item(self) -> bool:
        """Permite usuario escolher entre pasta ou arquivo. Returns True se adicionou."""
        import sys

        while True:
            limpar_tela()
            escrever(f"{Cor.NEGRITO}Tipo de item:{Cor.RESET}\n\n")
            escrever(f"  {Cor.SELECAO}> Pasta (diretorio){Cor.RESET}\n")
            escrever(f"    Arquivo (.zip)\n")
            escrever(f"\n  {Cor.DESABILITADO}↑↓ Enter selecionar | Q Voltar{Cor.RESET}\n")

            tecla = read_key()
            if tecla == "q":
                return False
            elif tecla == "enter":
                return self._pedir_caminho("Selecionar pasta")
            elif tecla == "down":
                # Swap selection - show zip option selected
                while True:
                    limpar_tela()
                    escrever(f"{Cor.NEGRITO}Tipo de item:{Cor.RESET}\n\n")
                    escrever(f"    Pasta (diretorio)\n")
                    escrever(f"  {Cor.SELECAO}> Arquivo (.zip){Cor.RESET}\n")
                    escrever(f"\n  {Cor.DESABILITADO}↑↓ Enter selecionar | Q Voltar{Cor.RESET}\n")

                    tecla2 = read_key()
                    if tecla2 == "q":
                        return False
                    elif tecla2 == "enter":
                        return self._pedir_arquivo("Selecionar arquivo .zip")
                    elif tecla2 == "up":
                        break

    def executar(self) -> tuple[list[dict], int]:
        """Retorna (lista_atualizada, cursor_final)."""
        if self.itens:
            self._ultimo_caminho = self.itens[-1].get("caminho", self._ultimo_caminho)

        total_linhas = len(self.itens) + 1

        while True:
            limpar_tela()
            escrever(f"{Cor.NEGRITO}{self.titulo}{Cor.RESET}\n\n")

            for i, item in enumerate(self.itens):
                prefixo = "▶ " if i == self.cursor else "  "
                cor = Cor.SELECAO if i == self.cursor else ""
                reset = Cor.RESET if i == self.cursor else ""
                nome = item.get("nome", "(sem nome)")
                caminho = item.get("caminho", "")
                if self.modo_nome:
                    escrever(f"  {cor}{prefixo}{nome}{reset}\n")
                else:
                    if len(caminho) > 60:
                        caminho = "..." + caminho[-57:]
                    escrever(f"  {cor}{prefixo}{nome}{reset}\n")
                    escrever(f"  {Cor.SEPARADOR}     {caminho}{Cor.RESET}\n")

            idx_adicionar = len(self.itens)
            cor_add = Cor.SELECAO if self.cursor == idx_adicionar else ""
            reset_add = Cor.RESET if self.cursor == idx_adicionar else ""
            escrever(f"\n  {cor_add}+ Adicionar novo{reset_add}")

            if self.itens:
                escrever(f"  {Cor.ERRO}R Remover{Cor.RESET}")
                if self.modo_nome:
                    escrever(f"  D Editar")
            escrever(f"\n  {Cor.DESABILITADO}Enter Selecionar | Q Voltar{Cor.RESET}\n")

            tecla = read_key()
            if tecla == "up":
                self.cursor = max(0, self.cursor - 1)
            elif tecla == "down":
                self.cursor = min(total_linhas - 1, self.cursor + 1)
            elif tecla == "a" or tecla == "+":
                if self.modo_nome:
                    novo_nome = self._pedir_texto("Nome do arquivo")
                    if novo_nome:
                        self.itens.append({"nome": novo_nome})
                        self.cursor = len(self.itens) - 1
                        total_linhas = len(self.itens) + 1
                else:
                    novo_caminho = self._adicionar_item()
                    if novo_caminho:
                        from pathlib import Path
                        nome = Path(novo_caminho).name
                        self.itens.append({"nome": nome, "caminho": novo_caminho})
                        self.cursor = len(self.itens) - 1
                        total_linhas = len(self.itens) + 1
            elif tecla.lower() == "r" and self.itens and self.cursor < len(self.itens):
                self.itens.pop(self.cursor)
                if self.cursor >= len(self.itens):
                    self.cursor = max(0, len(self.itens) - 1)
                total_linhas = len(self.itens) + 1
            elif tecla.lower() == "d" and self.modo_nome and self.itens and self.cursor < len(self.itens):
                item = self.itens[self.cursor]
                novo_nome = self._pedir_texto("Editar nome", padrao=item.get("nome", ""))
                if novo_nome:
                    self.itens[self.cursor] = {"nome": novo_nome}
            elif tecla == "enter":
                if self.cursor == idx_adicionar:
                    if self.modo_nome:
                        novo_nome = self._pedir_texto("Nome do arquivo")
                        if novo_nome:
                            self.itens.append({"nome": novo_nome})
                            self.cursor = len(self.itens) - 1
                            total_linhas = len(self.itens) + 1
                    else:
                        novo_caminho = self._adicionar_item()
                        if novo_caminho:
                            from pathlib import Path
                            nome = Path(novo_caminho).name
                            self.itens.append({"nome": nome, "caminho": novo_caminho})
                            self.cursor = len(self.itens) - 1
                            total_linhas = len(self.itens) + 1
                elif self.itens:
                    return (self.itens, self.cursor)
            elif tecla == "q":
                return (self.itens, self.cursor)

    def _pedir_caminho(self, mensagem: str) -> str | None:
        """Abre seletor de pasta do Windows Explorer."""
        try:
            import tkinter as tk
            from tkinter import filedialog

            root = tk.Tk()
            root.withdraw()
            root.lift()
            root.attributes("-topmost", True)
            root.focus_force()

            initialdir = self._ultimo_caminho if hasattr(self, '_ultimo_caminho') and self._ultimo_caminho else None

            caminho = filedialog.askdirectory(
                title=mensagem,
                initialdir=initialdir,
            )
            root.destroy()

            if not caminho:
                return None
            return str(caminho)
        except Exception as e:
            limpar_tela()
            escrever(f"  Erro ao abrir seletor: {e}\n")
            escrever("  Pressione Enter para continuar...")
            sys.stdout.flush()
            from .input import read_key
            while True:
                if read_key() == "enter":
                    break
            return None

    def _pedir_arquivo(self, mensagem: str, tipos: list[tuple[str, str]] = None) -> str | None:
        """Abre seletor de arquivo do Windows Explorer (para zip etc)."""
        if tipos is None:
            tipos = [("Arquivos zip", "*.zip"), ("Todos os arquivos", "*.*")]
        try:
            import tkinter as tk
            from tkinter import filedialog

            root = tk.Tk()
            root.withdraw()
            root.lift()
            root.attributes("-topmost", True)
            root.focus_force()

            initialdir = self._ultimo_caminho if hasattr(self, '_ultimo_caminho') and self._ultimo_caminho else None

            caminho = filedialog.askopenfilename(
                title=mensagem,
                filetypes=tipos,
                initialdir=initialdir,
            )
            root.destroy()

            if not caminho:
                return None
            return str(caminho)
        except Exception as e:
            limpar_tela()
            escrever(f"  Erro ao abrir seletor: {e}\n")
            escrever("  Pressione Enter para continuar...")
            sys.stdout.flush()
            from .input import read_key
            while True:
                if read_key() == "enter":
                    break
            return None

    def _pedir_texto(self, mensagem: str, padrao: str = "") -> str | None:
        """Input de texto via terminal."""
        limpar_tela()
        escrever(f"{Cor.NEGRITO}{mensagem}:{Cor.RESET}\n\n")
        escrever(f"  Valor atual: {padrao}\n")
        escrever("  Digite o novo valor e pressione Enter:\n  > ")
        sys.stdout.flush()

        if sys.platform == "win32":
            import msvcrt
            chars = []
            while True:
                ch = msvcrt.getwch()
                if ch == "\r":
                    break
                if ch == "\x03":
                    return None
                if ch == "\x1b":
                    return None
                if ch == "\x08" and chars:
                    chars.pop()
                    sys.stdout.write("\b \b")
                    sys.stdout.flush()
                elif ch.isprintable():
                    chars.append(ch)
                    sys.stdout.write(ch)
                    sys.stdout.flush()
        else:
            try:
                linha = input()
                return linha.strip() if linha.strip() else None
            except (EOFError, KeyboardInterrupt):
                return None

        texto = "".join(chars).strip()
        return texto if texto else None
