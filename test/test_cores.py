"""Teste de preto no fundo verde."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

print("\033[2J\033[H")
print("Qual preto fica certo no fundo verde?\n")
print("Digite o numero da opcao que parece PRETO (nao cinza):\n")

opcoes = [
    ("1", "\033[42m\033[30m\033[1m  Texto com \\033[30m (ANSI black)  \033[0m"),
    ("2", "\033[102m\033[30m\033[1m  Texto com \\033[102m + \\033[30m  \033[0m"),
    ("3", "\033[42m\033[38;5;232m\033[1m  Texto com \\033[38;5;232m (256 black)  \033[0m"),
    ("4", "\033[42m\033[38;2;0;0;0m\033[1m  Texto com RGB(0,0,0) true color  \033[0m"),
    ("5", "\033[42m\033[38;5;0m\033[1m  Texto com \\033[38;5;0m (256 color 0)  \033[0m"),
    ("6", "\033[42m\033[97m\033[1m  Texto BRANCO \\033[97m (teste contraste)  \033[0m"),
]

for cod, texto in opcoes:
    print(f"  {cod}. {texto}")

print(f"\n  \033[0mFundo verde padrao: \033[42m\033[0m")
print(f"  \033[0mTexto preto padrao do terminal: \033[30mTexto\033[0m")
print(f"  \033[0mTexto branco padrao do terminal: \033[37mTexto\033[0m")
print(f"\n  \033[90mEscolha: 1-6 ou Q sair\033[0m")
