#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Testes das utilidades compartilhadas: texto, hash curto e chaves."""

import re
from pathlib import Path

import pytest

from pereiras_common.uteis import (
    DIR_CHAVES_PADRAO,
    carregar_cache_jsonl,
    gravar_cache_jsonl,
    hash_curto_6,
    ler_chave,
    normalizar_titulo,
    para_snake_case,
    sha256_arquivo,
)


# ------------------------------------------------------------- para_snake_case

def test_para_snake_case_acentos():
    assert para_snake_case("São Paulo") == "sao_paulo"
    assert para_snake_case("Foto 01 - Praia!") == "foto_01_praia"
    assert para_snake_case("çamarões") == "camaroes"
    assert para_snake_case("!!!") == "sem_nome"


def test_para_snake_case_nao_alfanumericos():
    assert para_snake_case("a@b#c$d%e") == "a_b_c_d_e"
    assert para_snake_case("  espaços  extras  ") == "espacos_extras"
    assert para_snake_case("CamelCase") == "camelcase"


# ---------------------------------------------------------------- hash_curto_6

def test_hash_curto_6_formato(tmp_path):
    arquivo = tmp_path / "foto.jpg"
    arquivo.write_bytes(b"conteudo qualquer")
    h = hash_curto_6(arquivo)
    assert isinstance(h, str)
    assert len(h) == 6
    assert re.fullmatch(r"[0-9a-z]{6}", h), "deve ser alfanumérico sem especiais"


def test_hash_curto_6_deterministico(tmp_path):
    arquivo = tmp_path / "foto.jpg"
    arquivo.write_bytes(b"mesmo conteudo")
    assert hash_curto_6(arquivo) == hash_curto_6(arquivo)


def test_hash_curto_6_conteudo_diferente(tmp_path):
    a = tmp_path / "a.bin"
    b = tmp_path / "b.bin"
    a.write_bytes(b"conteudo A")
    b.write_bytes(b"conteudo B")
    assert hash_curto_6(a) != hash_curto_6(b)


def test_hash_curto_6_arquivo_inexistente(tmp_path):
    assert hash_curto_6(tmp_path / "nao_existe.bin") is None


def test_hash_curto_6_arquivo_vazio(tmp_path):
    vazio = tmp_path / "vazio.bin"
    vazio.write_bytes(b"")
    h = hash_curto_6(vazio)
    assert len(h) == 6
    assert h == hash_curto_6(vazio)


# -------------------------------------------------------------------- ler_chave

def test_ler_chave(tmp_path):
    chave = tmp_path / "chave.key"
    chave.write_text("  MINHA-CHAVE-SECRETA-123  \n", encoding="utf-8")
    assert ler_chave(chave) == "MINHA-CHAVE-SECRETA-123"


def test_ler_chave_inexistente(tmp_path):
    assert ler_chave(tmp_path / "nao_existe.key") is None


def test_ler_chave_muito_curta(tmp_path):
    chave = tmp_path / "chave.key"
    chave.write_text("abc", encoding="utf-8")
    assert ler_chave(chave) is None


def test_dir_chaves_padrao_no_home():
    assert DIR_CHAVES_PADRAO == Path.home() / ".chaves_ia"


# ------------------------------------------------- sha256 e hash a partir dele

def test_sha256_arquivo_deterministico(tmp_path):
    """Mesmo conteúdo -> mesmo SHA-256; conteúdo diferente -> hash diferente."""
    a = tmp_path / "a.bin"
    b = tmp_path / "b.bin"
    c = tmp_path / "c.bin"
    a.write_bytes(b"conteudo identico")
    b.write_bytes(b"conteudo identico")
    c.write_bytes(b"outro conteudo")
    assert sha256_arquivo(a) == sha256_arquivo(b)
    assert sha256_arquivo(a) != sha256_arquivo(c)
    assert len(sha256_arquivo(a)) == 64


def test_sha256_arquivo_inexistente(tmp_path):
    assert sha256_arquivo(tmp_path / "nao_existe.bin") is None


def test_hash_curto_6_aceita_digest_pronto(tmp_path):
    """Com o SHA-256 já calculado, hash_curto_6 não lê o arquivo de novo."""
    p = tmp_path / "foto.jpg"
    p.write_bytes(b"conteudo de teste")
    digest = sha256_arquivo(p)
    assert hash_curto_6(p, digest=digest) == hash_curto_6(p)
    # O caminho nem precisa existir quando o digest é informado.
    assert hash_curto_6(tmp_path / "sumiu.jpg", digest=digest) == hash_curto_6(p)


# ------------------------------------------------------------ cache JSONL

def test_cache_jsonl_grava_e_carrega(tmp_path):
    """O cache append-only devolve um dict indexado pela chave escolhida."""
    cache_path = tmp_path / "cache.jsonl"
    gravar_cache_jsonl({"sha256": "abc", "titulo": "praia_ao_por_do_sol"}, cache_path)
    gravar_cache_jsonl({"sha256": "def", "titulo": "festa_de_aniversario"}, cache_path)
    cache = carregar_cache_jsonl(cache_path)
    assert cache["abc"]["titulo"] == "praia_ao_por_do_sol"
    assert cache["def"]["titulo"] == "festa_de_aniversario"


def test_cache_jsonl_ignora_linhas_corrompidas(tmp_path):
    """Linha inválida não derruba a leitura: o cache é atalho, não fonte de verdade."""
    cache_path = tmp_path / "cache.jsonl"
    cache_path.write_text(
        '{"sha256": "ok", "titulo": "valido"}\n'
        "{ isto nao e json }\n"
        "\n"
        '{"sem_chave": 1}\n',
        encoding="utf-8",
    )
    cache = carregar_cache_jsonl(cache_path)
    assert list(cache) == ["ok"]


def test_cache_jsonl_inexistente_devolve_vazio(tmp_path):
    assert carregar_cache_jsonl(tmp_path / "nunca_gravado.jsonl") == {}


# ------------------------------------------------------------- normalizar_titulo

@pytest.mark.parametrize("entrada,esperado", [
    ("Festa de Aniversário", "festa_de_aniversario"),
    ('  "Praia ao Pôr do Sol"  ', "praia_ao_por_do_sol"),
    ("uma frase bem longa com mais de cinco palavras", "uma_frase_bem_longa_com"),
    ("", ""),
    ("!!!", ""),
    (None, ""),
])
def test_normalizar_titulo(entrada, esperado):
    """Título da IA vira snake_case de no máximo 5 palavras (vazio se não sobrar nada)."""
    assert normalizar_titulo(entrada) == esperado
