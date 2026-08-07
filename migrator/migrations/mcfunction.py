"""Migrações de mcfunction (Snapshot 7)."""
from __future__ import annotations

import re

from ..core.scanner import FileType
from ..core.engine import register, MigrationResult


_BLOCK_STATE_TEXT_RE = re.compile(
    r'\{\s*"Name"\s*:\s*"([^"]+)"\s*,\s*"Properties"\s*:'
)
_BLOCK_STATE_SIMPLE_TEXT_RE = re.compile(
    r'\{\s*"Name"\s*:\s*"(minecraft:[^"]+)"\s*\}'
)


@register("snapshot7", [FileType.MCFUNCTION])
def rename_block_state_in_text(content: str, result: MigrationResult) -> str:
    """Renomear Name → id e Properties → properties em block states no texto (S7-01)."""
    changes: list[str] = []

    def repl_with_properties(match: re.Match) -> str:
        changes.append(match.group(1))
        return f'{{"id": "{match.group(1)}", "properties":'

    def repl_simple(match: re.Match) -> str:
        changes.append(match.group(1))
        return f'{{"id": "{match.group(1)}"}}'

    new_content = _BLOCK_STATE_TEXT_RE.sub(repl_with_properties, content)
    new_content = _BLOCK_STATE_SIMPLE_TEXT_RE.sub(repl_simple, new_content)

    if changes:
        result.add_change(
            f"Renomeado 'Name' → 'id' e 'Properties' → 'properties' "
            f"em block state ({len(changes)}x)"
        )
    return new_content


@register("snapshot7", [FileType.MCFUNCTION])
def convert_function_to_type_in_commands(content: str, result: MigrationResult) -> str:
    """Converter 'function' → 'type' em JSONs de comandos (S7-function).

    Em 26.3, loot functions e command arguments usam 'type' em vez de 'function'.
    Converte tanto chaves quoted ("function") quanto unquoted (function).
    """
    changes = 0

    # Chave quoted: "function": → "type":
    new_content, n = re.subn(
        r'([{,])\s*"function"\s*:',
        r'\1"type":',
        content
    )
    changes += n

    # Chave unquoted: function: → type:
    new_content, n = re.subn(
        r'([{,])\s*function\s*:',
        r'\1type:',
        new_content
    )
    changes += n

    if changes:
        result.add_change(f"Convertido 'function' → 'type' em comandos ({changes}x)")
    return new_content


@register("snapshot7", [FileType.MCFUNCTION])
def convert_condition_to_type_in_commands(content: str, result: MigrationResult) -> str:
    """Converter 'condition' → 'type' em JSONs de comandos (S7-condition).

    Em 26.3, condições em execute usam 'type' em vez de 'condition'.
    Converte tanto chaves quoted ("condition") quanto unquoted (condition).
    """
    changes = 0

    # Chave quoted: "condition": → "type":
    new_content, n = re.subn(
        r'([{,])\s*"condition"\s*:',
        r'\1"type":',
        content
    )
    changes += n

    # Chave unquoted: condition: → type:
    new_content, n = re.subn(
        r'([{,])\s*condition\s*:',
        r'\1type:',
        new_content
    )
    changes += n

    if changes:
        result.add_change(f"Convertido 'condition' → 'type' em comandos ({changes}x)")
    return new_content


@register("snapshot7", [FileType.MCFUNCTION])
def convert_particle_name_to_id(content: str, result: MigrationResult) -> str:
    """Converter 'Name' → 'id' em partículas (S7-particle).

    Partículas usam {Name:"value"} em vez de {id:"value"}.
    """
    changes = 0

    # Name: → id: (unquoted key, como em partículas)
    new_content, n = re.subn(
        r'([{,])\s*Name\s*:',
        r'\1id:',
        content
    )
    changes += n

    if changes:
        result.add_change(f"Convertido 'Name' → 'id' em partículas ({changes}x)")
    return new_content


@register("snapshot4", [FileType.MCFUNCTION])
def add_uniform_type_to_number_providers_in_commands(content: str, result: MigrationResult) -> str:
    """Adicionar 'type':'minecraft:uniform' a number providers em comandos.

    Em 26.3, {min:X,max:Y} em comandos precisa de type explicito.
    """
    changes = 0

    # Match {min:X,max:Y} or {max:X,min:Y} without type
    pattern = r'\{\s*(min|max)\s*:\s*[^,}]+\s*,\s*(min|max)\s*:\s*[^,}]+\s*\}'

    def replacer(match: re.Match) -> str:
        text = match.group(0)
        if 'type:' in text or '"type"' in text:
            return text
        # Insert type as first key
        inner = text[1:-1].strip()
        return '{"type":"minecraft:uniform",' + inner + '}'

    new_content, n = re.subn(pattern, replacer, content)
    changes = n

    if changes:
        result.add_change(f"Adicionado 'type':'minecraft:uniform' em number providers ({changes}x)")
    return new_content


@register("snapshot3", [FileType.MCFUNCTION])
def fix_potion_contents_predicate_in_commands(content: str, result: MigrationResult) -> str:
    """Corrigir minecraft:potion_contents em comandos (S3-command).

    potion_contents~"string" → potion_contents~{effects:{contains:[{string:{}}]}
    potion_contents:"string" → potion_contents:{"potions":["string"]}
    """
    changes = 0

    # potion_contents~"string" → potion_contents~{effects:{contains:[{effect:{}}]}}
    # Remove namespace from effect name (minecraft:infested → infested)
    pattern_tilde = r'(minecraft:potion_contents|potion_contents)\s*~\s*"([^"]+)"'

    def replacer_tilde(match: re.Match) -> str:
        key = match.group(1)
        value = match.group(2)
        # Remove namespace (minecraft:infested → infested)
        effect = value.split(":")[-1] if ":" in value else value
        return f'{key}~{{effects:{{contains:[{{{effect}:{{}}}}]}}}}'

    new_content, n = re.subn(pattern_tilde, replacer_tilde, content)
    changes += n

    # potion_contents:"string" → potion_contents:{"potions":["string"]}
    pattern_colon = r'(minecraft:potion_contents|potion_contents)\s*:\s*"([^"]+)"'

    def replacer_colon(match: re.Match) -> str:
        key = match.group(1)
        value = match.group(2)
        return f'{key}:{{"potions":["{value}"]}}'

    new_content, n = re.subn(pattern_colon, replacer_colon, new_content)
    changes += n

    if changes:
        result.add_change(f"Corrigido minecraft:potion_contents em comandos ({changes}x)")
    return new_content
