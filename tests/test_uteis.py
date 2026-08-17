#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Testes das utilidades compartilhadas: texto, hash curto e chaves."""

import re
from pathlib import Path

from pereiras_common.uteis import (
    DIR_CHAVES_PADRAO,
    hash_curto_6,
    ler_chave,
    para_snake_case,
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
