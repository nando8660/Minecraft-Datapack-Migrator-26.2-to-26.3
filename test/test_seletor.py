"""Testar seletor de pasta."""
import sys
sys.path.insert(0, '.')

from migrator.ui.terminal.ui import GerenciadorLista

print("Abrindo seletor de pasta...")
print("Selecione uma pasta e clique em OK.")

lista = GerenciadorLista("Teste", [])
resultado = lista._pedir_caminho("Selecione uma pasta para teste")

if resultado:
    print(f"\nCaminho selecionado: {resultado}")
else:
    print("\nNenhum caminho selecionado (cancelado ou erro)")
