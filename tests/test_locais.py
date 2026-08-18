#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Testes de onde cada arquivo gerado deve morar (pereiras_common.locais)."""

from pathlib import Path

import pytest

from pereiras_common.locais import (
    NOME_PASTA_DADOS,
    pasta_cache,
    pasta_dados_colecao,
    pasta_logs,
    resolver_pasta_dados,
)


# ------------------------------------------------- pasta de dados da coleção

def test_pasta_dados_fica_dentro_da_colecao(tmp_path):
    """Os dados pertencem à coleção, não ao repositório nem ao usuário."""
    assert pasta_dados_colecao(tmp_path) == tmp_path / NOME_PASTA_DADOS


def test_pasta_dados_aceita_texto(tmp_path):
    assert pasta_dados_colecao(str(tmp_path)) == tmp_path / NOME_PASTA_DADOS


def test_pasta_dados_expande_notacao_do_usuario(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    esperado = tmp_path / "fotos" / NOME_PASTA_DADOS
    assert pasta_dados_colecao(r"$HOME\fotos") == esperado


# ------------------------------------------------------- logs e cache

def test_pasta_logs_e_por_usuario_e_nomeada_pelo_app():
    caminho = pasta_logs("meu_app")
    assert "meu_app" in str(caminho)
    assert caminho.is_absolute()


def test_pasta_cache_e_por_usuario_e_nomeada_pelo_app():
    caminho = pasta_cache("meu_app")
    assert "meu_app" in str(caminho)
    assert caminho.is_absolute()


def test_logs_e_cache_sao_lugares_diferentes():
    """Cache pode ser apagado por limpeza de disco; log não é cache."""
    assert pasta_logs("app") != pasta_cache("app")


# ------------------------------------------------------- resolução da pasta

def test_resolver_prefere_o_caminho_explicito(tmp_path):
    """--dados-dir sempre vence."""
    escolhido = tmp_path / "escolhido"
    colecao = tmp_path / "colecao"
    colecao.mkdir()
    assert resolver_pasta_dados(escolhido, colecao, tmp_path / "legado") == escolhido


def test_resolver_usa_a_colecao_quando_nao_ha_legado(tmp_path):
    colecao = tmp_path / "colecao"
    colecao.mkdir()
    legado = tmp_path / "projeto"
    legado.mkdir()
    assert resolver_pasta_dados(None, colecao, legado) == pasta_dados_colecao(colecao)


def test_resolver_respeita_dados_ja_existentes_na_pasta_do_projeto(tmp_path):
    """Quem já tem classificações no projeto não pode perdê-las na atualização."""
    colecao = tmp_path / "colecao"
    colecao.mkdir()
    legado = tmp_path / "projeto"
    legado.mkdir()
    (legado / "classificacao_gemini_01.csv").write_text("caminho_completo\n",
                                                        encoding="utf-8")
    assert resolver_pasta_dados(None, colecao, legado) == legado


def test_resolver_prefere_a_colecao_quando_ela_ja_tem_dados(tmp_path):
    """Migrado: existindo dados nos dois lugares, a coleção é a fonte."""
    colecao = tmp_path / "colecao"
    (colecao / NOME_PASTA_DADOS).mkdir(parents=True)
    (colecao / NOME_PASTA_DADOS / "classificacao_gemini_01.csv").write_text(
        "caminho_completo\n", encoding="utf-8")
    legado = tmp_path / "projeto"
    legado.mkdir()
    (legado / "classificacao_gemini_01.csv").write_text("caminho_completo\n",
                                                        encoding="utf-8")
    assert resolver_pasta_dados(None, colecao, legado) == pasta_dados_colecao(colecao)


def test_resolver_sem_legado_informado(tmp_path):
    colecao = tmp_path / "colecao"
    colecao.mkdir()
    assert resolver_pasta_dados(None, colecao, None) == pasta_dados_colecao(colecao)


@pytest.mark.parametrize("marcador", [
    "classificacao_gemini_01.csv",
    "classificacao_index.jsonl",
    "cache_sha256_classificacoes.jsonl",
])
def test_qualquer_dado_legado_segura_a_pasta_antiga(tmp_path, marcador):
    colecao = tmp_path / "colecao"
    colecao.mkdir()
    legado = tmp_path / "projeto"
    legado.mkdir()
    (legado / marcador).write_text("x", encoding="utf-8")
    assert resolver_pasta_dados(None, colecao, legado) == legado
