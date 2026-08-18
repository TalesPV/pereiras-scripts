#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""Onde cada arquivo gerado deve morar.

Os programas produzem coisas de naturezas diferentes, e tratá-las igual é o
erro que este módulo evita. A regra é **a quem o arquivo pertence**:

===================================  ======================================
Pertence a...                        Vai para...
===================================  ======================================
à COLEÇÃO de fotos                   ``<raiz da coleção>/.midias-dados/``
                                     e os relatórios ao lado de cada mídia
ao USUÁRIO/máquina (logs)            :func:`pasta_logs`
ao USUÁRIO e é descartável (cache)   :func:`pasta_cache`
ao USUÁRIO e é segredo (chaves)      ``$HOME\.chaves_ia\`` (ver ``uteis``)
===================================  ======================================

Por que os dados vão para a coleção, e não para a pasta pessoal: listas de
classificação e índices descrevem **aquela** coleção. Guardá-los na ``home``
misturaria duas coleções numa base só, e mudar a coleção de máquina deixaria
o trabalho para trás. Ao lado das fotos, tudo viaja junto — inclusive no
backup.

Por que logs e cache NÃO vão para lá: eles são da máquina, não da coleção, e
o cache é descartável por definição. Os caminhos vêm do ``platformdirs``, que
resolve as convenções de cada sistema (``~/.cache`` e ``~/.local/state`` no
Linux, ``%LOCALAPPDATA%`` no Windows, ``~/Library`` no macOS).

**Atenção ao que NÃO é cache**: o cache de SHA-256 das classificações parece
cache, mas regenerá-lo custa dinheiro de API. Por isso ele fica junto dos
dados da coleção, e não em :func:`pasta_cache` — pasta que ferramentas de
limpeza de disco apagam sem avisar.
"""

from __future__ import annotations

from pathlib import Path

import platformdirs

from .uteis import expandir_caminho

# Pasta criada na raiz da coleção para guardar o que descreve aquela coleção.
# O ponto no início a esconde da listagem normal, como .git faz.
NOME_PASTA_DADOS = ".midias-dados"

# Arquivos cuja presença indica dados de uma versão anterior, quando tudo
# ficava na pasta do projeto. Serve para não abandonar o trabalho de quem
# já usava os programas antes desta mudança.
MARCADORES_LEGADO = (
    "classificacao_gemini_01.csv",
    "classificacao_gemini_02.csv",
    "classificacao_gemini_03.csv",
    "classificacao_gemini_04.csv",
    "classificacao_gemini_05.csv",
    "classificacao_index.jsonl",
    "cache_sha256_classificacoes.jsonl",
    "cache_sha256_titulos.jsonl",
)


def pasta_dados_colecao(raiz_colecao: str | Path) -> Path:
    """Pasta de dados de uma coleção: ``<raiz>/.midias-dados``.

    Aceita ``~``, ``$HOME`` e ``%USERPROFILE%`` no caminho da coleção.
    Não cria a pasta — quem grava é que garante a existência.
    """
    return expandir_caminho(raiz_colecao) / NOME_PASTA_DADOS


def pasta_logs(app: str) -> Path:
    """Pasta de logs do usuário para o programa ``app``.

    Logs registram o que aconteceu numa máquina: não pertencem à coleção
    nem devem ir para o cache (que é apagável a qualquer momento).
    """
    return Path(platformdirs.user_log_dir(app, appauthor=False))


def pasta_cache(app: str) -> Path:
    """Pasta de cache do usuário para o programa ``app``.

    Só para o que pode ser recriado **de graça** — por exemplo, consultas de
    geocodificação. Nada cuja recriação custe dinheiro de API deve vir aqui:
    ferramentas de limpeza de disco tratam esta pasta como descartável.
    """
    return Path(platformdirs.user_cache_dir(app, appauthor=False))


def _tem_dados(pasta: Path | None) -> bool:
    """True se a pasta contém dados de execução de alguma versão."""
    if pasta is None or not pasta.is_dir():
        return False
    return any((pasta / nome).exists() for nome in MARCADORES_LEGADO)


def resolver_pasta_dados(
    escolhida: str | Path | None,
    raiz_colecao: str | Path,
    legado: str | Path | None = None,
) -> Path:
    """Decide onde ler e gravar os dados desta execução.

    Ordem de preferência:

    1. ``escolhida`` (``--dados-dir``) — a palavra do usuário sempre vence.
    2. ``<raiz da coleção>/.midias-dados`` — o padrão novo. Vale também
       quando a pasta ainda não existe: ela é criada na primeira gravação.
    3. ``legado`` (a pasta do projeto) — **apenas** se ela já tiver dados e a
       coleção ainda não tiver. É o que impede que quem já usava os programas
       perca as classificações já feitas ao atualizar.

    Devolve o caminho; não cria nada.
    """
    if escolhida:
        return expandir_caminho(escolhida)
    da_colecao = pasta_dados_colecao(raiz_colecao)
    if _tem_dados(da_colecao):
        return da_colecao
    legado = expandir_caminho(legado) if legado else None
    if _tem_dados(legado):
        return legado
    return da_colecao


__all__ = [
    "MARCADORES_LEGADO",
    "NOME_PASTA_DADOS",
    "pasta_cache",
    "pasta_dados_colecao",
    "pasta_logs",
    "resolver_pasta_dados",
]
