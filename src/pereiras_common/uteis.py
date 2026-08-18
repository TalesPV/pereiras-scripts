#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Utilidades gerais compartilhadas entre os projetos (pereiras-common).

Aqui vivem funções pequenas e independentes que vários scripts usam:

- :func:`para_snake_case`: converte texto para o formato ``snake_case``
  (usado em títulos e nomes de arquivo).
- :func:`sha256_arquivo`: SHA-256 completo do conteúdo (chave de cache).
- :func:`hash_curto_6`: calcula um hash alfanumérico de 6 caracteres do
  conteúdo de um arquivo (usado para identificar arquivos no nome).
- :func:`normalizar_titulo`: limpa o título devolvido por uma IA.
- :func:`carregar_cache_jsonl` / :func:`gravar_cache_jsonl`: cache
  append-only em JSONL (usado para não repetir chamadas de API).
- :func:`ler_chave`: lê uma chave de API de um arquivo, com segurança
  (as chaves NUNCA devem ser escritas no código-fonte).

Exemplos de uso::

    from pereiras_common.uteis import hash_curto_6, para_snake_case

    print(para_snake_case("São Paulo"))   # -> "sao_paulo"
    print(hash_curto_6("foto.jpg"))       # -> algo como "k3x9ab"
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path

# ------------------------------------------------------------- constantes

# Pasta padrão onde as chaves de IA ficam, na pasta pessoal do usuário.
# Ex.: C:\\Users\\fulano\\.chaves_ia\\ (no Windows) ou ~/.chaves_ia/ (Linux).
# As chaves ficam FORA do repositório: nunca versionar chaves no git.
DIR_CHAVES_PADRAO = Path.home() / ".chaves_ia"

# Nomes padrão dos arquivos de chave dentro de DIR_CHAVES_PADRAO.
NOME_CHAVE_GEMINI = "chave_google_gemini.key"
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

# Blocos de 1 MB: hasheia arquivos grandes sem carregá-los na memória.
TAMANHO_BLOCO_LEITURA = 1024 * 1024

# Número máximo de palavras de um título gerado por IA (nomes curtos).
MAX_PALAVRAS_TITULO = 5


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


def sha256_arquivo(caminho: str | Path) -> str | None:
    """Calcula o SHA-256 (hexadecimal) do CONTEÚDO do arquivo.

    Serve como identidade do conteúdo: arquivos idênticos têm o mesmo
    SHA-256, o que permite reaproveitar análises de IA já feitas (cache)
    sem gastar créditos de novo.

    Lê em blocos de 1 MB, então funciona com arquivos grandes sem
    consumir memória. Retorna ``None`` se o arquivo não puder ser lido.

    Exemplos::

        sha256_arquivo("foto.jpg")  # -> "9f86d081..." (64 caracteres)
    """
    h = hashlib.sha256()
    try:
        with open(caminho, "rb") as f:
            for bloco in iter(lambda: f.read(TAMANHO_BLOCO_LEITURA), b""):
                h.update(bloco)
    except OSError:
        # Arquivo inexistente, sem permissão ou travado por outro programa.
        return None
    return h.hexdigest()


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


def hash_curto_6(caminho: str | Path, *, digest: str | None = None) -> str | None:
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

    ``digest``: SHA-256 já calculado (ex.: pelo cache). Informando-o, o
    arquivo NÃO é lido de novo — economiza uma leitura completa por mídia.

    Exemplos::

        hash_curto_6("foto.jpg")  # -> algo como "k3x9ab"
    """
    # Quem já calculou o SHA-256 (para o cache, por exemplo) passa em
    # ``digest`` e evita uma segunda leitura completa do arquivo.
    if digest is None:
        digest = sha256_arquivo(caminho)
    if digest is None:
        return None
    # O SHA-256 é um número de 256 bits; convertemos para base 36 e
    # guardamos apenas os últimos 6 caracteres (o "módulo" garante
    # distribuição uniforme sobre todo o conteúdo).
    try:
        valor = int(digest, 16) % (36 ** _TAMANHO_HASH)
    except (TypeError, ValueError):
        return None
    return _base36(valor, _TAMANHO_HASH)


def normalizar_titulo(texto: object, max_palavras: int = MAX_PALAVRAS_TITULO) -> str:
    """Limpa um título devolvido por uma IA e devolve snake_case curto.

    As IAs costumam responder com aspas, asteriscos de markdown ou frases
    longas demais para um nome de arquivo. Esta função:

    1. remove aspas/markdown das bordas;
    2. corta o excesso de palavras (padrão: 5);
    3. converte para snake_case sem acentos (:func:`para_snake_case`).

    Devolve "" (string vazia) quando não sobra texto útil — o chamador
    então gera o arquivo SEM o bloco de título.

    Exemplos::

        normalizar_titulo('"Festa de Aniversário"')  -> "festa_de_aniversario"
        normalizar_titulo("!!!")                     -> ""
    """
    t = str(texto or "").strip().strip('"`*#')
    palavras = t.split()
    if len(palavras) > max_palavras:
        t = " ".join(palavras[:max_palavras])
    t = para_snake_case(t)
    # "sem_nome" é o valor que para_snake_case usa quando não sobra nada:
    # aqui isso significa "não há título", então devolvemos vazio.
    return t if t != "sem_nome" else ""


def carregar_cache_jsonl(cache_path: str | Path, chave: str = "sha256") -> dict:
    """Lê um cache append-only em JSONL e devolve ``{valor_da_chave: registro}``.

    Formato: uma linha JSON por registro. É usado para não repetir
    chamadas de API para conteúdos já processados.

    Robusto por design: linhas em branco, linhas corrompidas e registros
    sem a chave são ignorados — o cache é um atalho, não a fonte da
    verdade. Arquivo inexistente devolve ``{}``.

    Exemplos::

        carregar_cache_jsonl("cache_titulos.jsonl")  # -> {"9f86...": {...}}
    """
    cache: dict = {}
    caminho = Path(cache_path)
    if not caminho.is_file():
        return cache
    try:
        with open(caminho, encoding="utf-8") as f:
            for linha in f:
                linha = linha.strip()
                if not linha:
                    continue
                try:
                    registro = json.loads(linha)
                except json.JSONDecodeError:
                    continue
                if isinstance(registro, dict) and registro.get(chave):
                    cache[registro[chave]] = registro
    except OSError:
        pass
    return cache


def gravar_cache_jsonl(registro: dict, cache_path: str | Path) -> None:
    """Anexa um registro ao cache JSONL (append-only, uma linha por registro).

    Falhas de gravação são silenciosas de propósito: perder o cache
    apenas custa uma chamada de API extra na próxima execução, e não
    deve interromper o processamento em andamento.
    """
    try:
        with open(cache_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(registro, ensure_ascii=False) + "\n")
    except OSError:
        pass


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

        ler_chave(Path.home() / ".chaves_ia" / "chave_google_gemini.key")
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
    "MAX_PALAVRAS_TITULO",
    "NOME_CHAVE_GEMINI",
    "NOME_CHAVE_OPENAI",
    "carregar_cache_jsonl",
    "gravar_cache_jsonl",
    "hash_curto_6",
    "ler_chave",
    "normalizar_titulo",
    "para_snake_case",
    "sha256_arquivo",
]
