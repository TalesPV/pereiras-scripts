#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Utilidades gerais compartilhadas entre os projetos (pereiras-common).

Aqui vivem funções pequenas e independentes que vários scripts usam:

- :func:`para_snake_case`: converte texto para o formato ``snake_case``
  (usado em títulos e nomes de arquivo).
- :func:`hash_curto_6`: calcula um hash alfanumérico de 6 caracteres do
  conteúdo de um arquivo (usado para identificar arquivos no nome).
- :func:`ler_chave`: lê uma chave de API de um arquivo, com segurança
  (as chaves NUNCA devem ser escritas no código-fonte).

Exemplos de uso::

    from pereiras_common.uteis import hash_curto_6, para_snake_case

    print(para_snake_case("São Paulo"))   # -> "sao_paulo"
    print(hash_curto_6("foto.jpg"))       # -> algo como "k3x9ab"
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path

# ------------------------------------------------------------- constantes

# Pasta padrão onde as chaves de IA ficam, na pasta pessoal do usuário.
# Ex.: C:\\Users\\fulano\\.chaves_ia\\ (no Windows) ou ~/.chaves_ia/ (Linux).
# As chaves ficam FORA do repositório: nunca versionar chaves no git.
DIR_CHAVES_PADRAO = Path.home() / ".chaves_ia"

# Nomes padrão dos arquivos de chave dentro de DIR_CHAVES_PADRAO.
NOME_CHAVE_GEMINI = "chave_gemini.key"
NOME_CHAVE_OPENAI = "chave_openai_chatgpt.key"

# Caminhos completos padrão (os programas podem sobrescrever via linha de comando).
CHAVE_GEMINI_PADRAO = DIR_CHAVES_PADRAO / NOME_CHAVE_GEMINI
CHAVE_OPENAI_PADRAO = DIR_CHAVES_PADRAO / NOME_CHAVE_OPENAI

# Tamanho mínimo aceitável para uma chave (evita ler arquivos vazios/ruins).
COMPRIMENTO_MINIMO_CHAVE = 10

# Regex que guarda apenas letras e números (o resto vira "_").
_RE_NAO_ALFANUMERICO = re.compile(r"[^a-zA-Z0-9]+")

# Base do hash curto: 36 símbolos (0-9 e a-z), sem caracteres especiais.
_BASE36 = "0123456789abcdefghijklmnopqrstuvwxyz"
_TAMANHO_HASH = 6


# ------------------------------------------------------------- funções

def para_snake_case(texto: object) -> str:
    """Converte um texto em ``snake_case``: letras minúsculas e ``_``.

    - Remove acentos ("São Paulo" -> "sao_paulo").
    - Troca qualquer caractere não alfanumérico por "_".
    - Se nada sobrar, devolve "sem_nome" (nunca devolve vazio).

    Exemplos::

        para_snake_case("São Paulo")        -> "sao_paulo"
        para_snake_case("Foto 01 - Praia!") -> "foto_01_praia"
        para_snake_case("!!!")              -> "sem_nome"
    """
    # Normaliza a string separando letras de acentos (NFKD), depois
    # remove os caracteres de acentuação que ficaram "sozinhos".
    texto = unicodedata.normalize("NFKD", str(texto))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    # Troca grupos de caracteres não alfanuméricos por um único "_".
    texto = _RE_NAO_ALFANUMERICO.sub("_", texto).strip("_").lower()
    return texto or "sem_nome"


def _base36(valor: int, tamanho: int) -> str:
    """Converte um número inteiro em texto na base 36, com zeros à esquerda.

    Base 36 usa apenas dígitos e letras minúsculas (0-9, a-z) — perfeito
    para nomes de arquivo, pois não contém caracteres especiais.
    """
    digitos = []
    while valor > 0:
        valor, resto = divmod(valor, 36)
        digitos.append(_BASE36[resto])
    return "".join(reversed(digitos)).rjust(tamanho, "0")[-tamanho:]


def hash_curto_6(caminho: str | Path) -> str | None:
    """Calcula um hash alfanumérico de 6 caracteres do CONTEÚDO do arquivo.

    O que é este hash?

    - Um "resumo" do conteúdo: arquivos idênticos geram o MESMO hash
      (útil para evitar duplicatas no nome do arquivo).
    - Mudou 1 byte que seja, o hash muda.
    - 6 caracteres minúsculos (0-9 e a-z), sem nenhum caractere especial:
      seguro para usar em nomes de arquivo em qualquer sistema operacional.

    Como funciona por dentro:

    1. Lê o arquivo em blocos de 1 MB e calcula o SHA-256 (não carrega o
       arquivo inteiro na memória).
    2. Converte o resultado para a base 36 e pega os últimos 6 dígitos.

    Observação: com 6 caracteres (~2 bilhões de combinações), colisões são
    raras em coleções domésticas (dezenas de milhares de arquivos), mas
    possíveis. Para garantir unicidade absoluta, use o SHA-256 completo.

    Retorna ``None`` se o arquivo não puder ser lido.

    Exemplos::

        hash_curto_6("foto.jpg")  # -> algo como "k3x9ab"
    """
    h = hashlib.sha256()
    try:
        # Lê o arquivo em blocos de 1 MB: funciona até com arquivos grandes.
        with open(caminho, "rb") as f:
            for bloco in iter(lambda: f.read(1024 * 1024), b""):
                h.update(bloco)
    except OSError:
        # Arquivo inexistente, sem permissão ou travado por outro programa.
        return None
    # O SHA-256 é um número de 256 bits; convertemos para base 36 e
    # guardamos apenas os últimos 6 caracteres (o "módulo" garante
    # distribuição uniforme sobre todo o conteúdo).
    valor = int(h.hexdigest(), 16) % (36 ** _TAMANHO_HASH)
    return _base36(valor, _TAMANHO_HASH)


def ler_chave(caminho_arquivo: str | Path) -> str | None:
    """Lê uma chave de API de um arquivo de texto e devolve limpa.

    Regras de segurança (importante!):

    - A chave fica em um arquivo FORA do repositório git (padrão:
      ``~/.chaves_ia/``) — nunca escreva chaves no código.
    - O arquivo deve conter apenas a chave (espaços e quebras de linha
      nas bordas são removidos automaticamente).

    Retorna ``None`` se o arquivo não existir ou se o conteúdo for curto
    demais para ser uma chave real (menos de 10 caracteres).

    Exemplos::

        ler_chave(Path.home() / ".chaves_ia" / "chave_gemini.key")
    """
    caminho = Path(caminho_arquivo)
    if not caminho.is_file():
        # Arquivo não existe: o chamador decide o que fazer (ignorar IA etc.).
        return None
    try:
        chave = caminho.read_text(encoding="utf-8").strip()
    except OSError:
        # Sem permissão de leitura ou erro de I/O.
        return None
    # Conteúdo curto demais não é uma chave válida.
    return chave if len(chave) >= COMPRIMENTO_MINIMO_CHAVE else None


__all__ = [
    "CHAVE_GEMINI_PADRAO",
    "CHAVE_OPENAI_PADRAO",
    "DIR_CHAVES_PADRAO",
    "NOME_CHAVE_GEMINI",
    "NOME_CHAVE_OPENAI",
    "hash_curto_6",
    "ler_chave",
    "para_snake_case",
]
