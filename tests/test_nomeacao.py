#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Testes do módulo de nomeação (datas, nome padrão e pastas de destino).

Formato padrão do nome das mídias (fotos, vídeos e áudios):

    YYYY_MM_DD_HHhMMmSSs-YYYY_MM_DD_HHhMMmSSs-cidade-hash6-titulo.ext
"""

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from pereiras_common.nomeacao import (
    MAX_COMPRIMENTO_NOME,
    dentro_do_periodo,
    extrair_data_nome,
    formatar_data,
    montar_dt,
    montar_nome_midia,
    montar_pasta_destino,
    preservar_nome_original,
    parsear_data_exif,
    titulo_valido,
)


# ------------------------------------------------------------------ datas

def test_formatar_data():
    dt = datetime(2023, 5, 10, 14, 30, 5)
    assert formatar_data(dt) == "2023_05_10_14h30m05s"


def test_montar_dt_invalido():
    assert montar_dt(2023, 2, 30) is None
    assert montar_dt(1970, 1, 1) is None
    assert montar_dt(3000, 1, 1) is None


def test_dentro_do_periodo():
    assert dentro_do_periodo(datetime(2023, 1, 1))
    assert not dentro_do_periodo(datetime(1970, 1, 1))
    assert not dentro_do_periodo(datetime(3000, 1, 1))
    assert not dentro_do_periodo(None)


def test_parsear_data_exif():
    assert parsear_data_exif("2021:03:15 10:20:30") == datetime(2021, 3, 15, 10, 20, 30)
    assert parsear_data_exif("2021-03-15T10:20:30") == datetime(2021, 3, 15, 10, 20, 30)
    assert parsear_data_exif("data qualquer") is None


@pytest.mark.parametrize("nome,esperado", [
    ("foto_2019_07_04_08h09m10s.jpg", datetime(2019, 7, 4, 8, 9, 10)),
    ("IMG_20190315102030.jpg", datetime(2019, 3, 15, 10, 20, 30)),
    ("video-2018-12-25_23-59-58.mp4", datetime(2018, 12, 25, 23, 59, 58)),
    ("antiga_2021_01_02.jpg", datetime(2021, 1, 2)),
    ("foto_2021_03_15.jpg", datetime(2021, 3, 15)),
    ("jan_02_2020.jpg", datetime(2020, 1, 2)),
    ("02 jan 2020.jpg", datetime(2020, 1, 2)),
])
def test_extrair_data_nome_mascaras(nome, esperado):
    assert extrair_data_nome(nome) == esperado


def test_extrair_data_nome_prefere_precisa():
    nome = "2019_07_04_08h09m10s_2019_07_05_00h00m00s.jpg"
    assert extrair_data_nome(nome) == datetime(2019, 7, 4, 8, 9, 10)


def test_extrair_data_nome_sem_data():
    assert extrair_data_nome("foto_da_praia.jpg") is None


def test_extrair_data_nome_ano_minimo():
    assert extrair_data_nome("foto_1950_01_01.jpg", ano_minimo=1980) is None


# ------------------------------------------------------------------ títulos

def test_titulo_valido():
    assert titulo_valido("festa_de_aniversario")
    assert not titulo_valido("Festa Aniversário")
    assert not titulo_valido("")
    assert not titulo_valido("com espaço")


# --------------------------------------------------------- montar_nome_midia

def test_montar_nome_midia_completo():
    d1 = datetime(2020, 1, 2, 3, 4, 5)
    d2 = datetime(2021, 6, 7, 8, 9, 10)
    nome = montar_nome_midia(d1, d2, "rio_de_janeiro",
                             hash6="k3x9ab", titulo="festa_de_aniversario",
                             extensao=".jpg")
    assert nome == ("2020_01_02_03h04m05s-2021_06_07_08h09m10s-"
                    "rio_de_janeiro-k3x9ab-festa_de_aniversario.jpg")


def test_montar_nome_midia_sem_titulo():
    # Execução sem IA: o bloco {titulo} é omitido, mas o hash permanece.
    d1 = datetime(2020, 1, 2, 3, 4, 5)
    d2 = datetime(2021, 6, 7, 8, 9, 10)
    nome = montar_nome_midia(d1, d2, "sao_paulo", hash6="k3x9ab", extensao=".mp4")
    assert nome == "2020_01_02_03h04m05s-2021_06_07_08h09m10s-sao_paulo-k3x9ab.mp4"


def test_montar_nome_midia_sem_hash():
    # Parametrização: o cliente pode optar por não usar o hash.
    d1 = datetime(2020, 1, 2, 3, 4, 5)
    d2 = datetime(2021, 6, 7, 8, 9, 10)
    nome = montar_nome_midia(d1, d2, "sao_paulo", titulo="festa", extensao=".jpg")
    assert nome == "2020_01_02_03h04m05s-2021_06_07_08h09m10s-sao_paulo-festa.jpg"


def test_montar_nome_midia_data_unica():
    d = datetime(2020, 1, 2, 3, 4, 5)
    nome = montar_nome_midia(d, d, "sem_gps", hash6="k3x9ab", titulo="foto",
                             extensao=".jpg")
    assert nome == ("2020_01_02_03h04m05s-2020_01_02_03h04m05s-"
                    "sem_gps-k3x9ab-foto.jpg")


def test_montar_nome_midia_ordem_dos_blocos():
    # O hash vem SEMPRE antes do título (evita sobrescrita de arquivos
    # do mesmo horário mesmo quando os títulos coincidem).
    d = datetime(2020, 1, 2, 3, 4, 5)
    nome = montar_nome_midia(d, d, "cidade", hash6="abc123", titulo="titulo",
                             extensao=".jpg")
    assert nome == ("2020_01_02_03h04m05s-2020_01_02_03h04m05s-"
                    "cidade-abc123-titulo.jpg")


def test_montar_nome_midia_muito_longo():
    d = datetime(2020, 1, 2, 3, 4, 5)
    titulo = "_".join(["palavra"] * 60)
    assert montar_nome_midia(d, d, "cidade", titulo=titulo, extensao=".jpg") is None
    assert MAX_COMPRIMENTO_NOME == 240


# ------------------------------------------------------ montar_pasta_destino

def test_montar_pasta_destino():
    destino = Path("E:/out")
    assert montar_pasta_destino(destino, datetime(2023, 5, 1), "%Y_%m") == destino / "2023_05"
    assert (montar_pasta_destino(destino, datetime(2023, 5, 1), "%Y_%m", sufixo="videos")
            == destino / "2023_05-videos")
    assert montar_pasta_destino(destino, None, "%Y_%m") == destino / "sem_data"


# ------------------------------- preservar o nome que já carrega um título

DT_A = datetime(1997, 6, 10, 21, 17, 16)


@pytest.mark.parametrize("nome_atual,motivo", [
    ("1997_06_10_21h17m16s-1997_06_10_21h17m16s-sem_gps-retrato_de_jovem.BMP",
     "formato antigo (sem hash6) com título gerado por IA"),
    ("1997_06_10_21h17m16s-1997_06_10_21h17m16s-sem_gps-og12s3-retrato_de_jovem.BMP",
     "formato atual com hash6 e título"),
])
def test_preservar_nome_original_quando_ha_titulo(nome_atual, motivo):
    """Renomear apagaria um título que só uma chamada de IA saberia recriar."""
    assert preservar_nome_original(nome_atual, DT_A, DT_A, "sem_gps",
                                   hash6="og12s3") is True, motivo


@pytest.mark.parametrize("nome_atual,motivo", [
    ("1997_06_10_21h17m16s-1997_06_10_21h17m16s-sem_gps.BMP",
     "sem título: renomear só acrescenta o hash6"),
    ("1997_06_10_21h17m16s-1997_06_10_21h17m16s-sem_gps-og12s3.BMP",
     "só o hash6, nenhum título a perder"),
    ("2020_01_01_00h00m00s-2020_01_01_00h00m00s-sem_gps-titulo.BMP",
     "datas diferentes: é outro arquivo, não há o que preservar"),
    ("1997_06_10_21h17m16s-1997_06_10_21h17m16s-fortaleza-titulo.BMP",
     "cidade diferente: o nome alvo carrega informação nova"),
    ("foto_qualquer_sem_formato.BMP",
     "fora do formato padrão"),
])
def test_nao_preservar_quando_nao_ha_titulo_a_perder(nome_atual, motivo):
    assert preservar_nome_original(nome_atual, DT_A, DT_A, "sem_gps",
                                   hash6="og12s3") is False, motivo


def test_preservar_nome_original_sem_hash6():
    """Clientes que não usam hash6 também preservam o título."""
    assert preservar_nome_original(
        "1997_06_10_21h17m16s-1997_06_10_21h17m16s-sem_gps-praia.jpg",
        DT_A, DT_A, "sem_gps") is True


def test_preservar_nome_original_sem_data():
    """Sem data não há nome alvo: nada a comparar."""
    assert preservar_nome_original("qualquer.jpg", None, None, "sem_gps") is False


# --------------------------- tolerância a relógio adiantado (skew)

def test_dentro_do_periodo_tolera_pequeno_adiantamento():
    """Arquivo gravado 2 s "no futuro" é jitter de relógio, não data inválida.

    Acontece de verdade em disco de rede (Proton Drive, NAS) e em runners de
    CI: o carimbo do arquivo fica microssegundos à frente do relógio local.
    Sem tolerância, o arquivo perde a data e cai em "sem_data".
    """
    assert dentro_do_periodo(datetime.now() + timedelta(seconds=2)) is True
    assert dentro_do_periodo(datetime.now() + timedelta(hours=3)) is True


def test_dentro_do_periodo_ainda_rejeita_futuro_absurdo():
    """Tolerar jitter não pode virar aceitar qualquer data futura."""
    assert dentro_do_periodo(datetime.now() + timedelta(days=30)) is False
    assert dentro_do_periodo(datetime(2099, 1, 1)) is False


def test_dentro_do_periodo_ainda_rejeita_antes_do_ano_minimo():
    assert dentro_do_periodo(datetime(1970, 1, 1)) is False
    assert dentro_do_periodo(datetime(1970, 1, 1), ano_minimo=1960) is True
