#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Nomeação: datas e nomes de arquivo padrão (pereiras-common).

Formato padrão do nome das mídias (fotos, vídeos e áudios):

    YYYY_MM_DD_HHhMMmSSs-YYYY_MM_DD_HHhMMmSSs-cidade-hash6-titulo.ext

- O primeiro bloco é a data mais antiga e o segundo a mais recente
  (repetida quando há uma só).
- ``cidade``: nome da cidade do GPS em snake_case, ``sem_gps`` ou
  coordenadas.
- ``hash6``: hash curto do conteúdo (``pereiras_common.uteis.hash_curto_6``).
  Fica ANTES do título para evitar sobrescrita de arquivos do mesmo
  horário (mídias diferentes têm hashes diferentes).
- ``titulo``: título snake_case gerado por IA. Em execuções sem IA
  (ou com falha), o bloco é simplesmente omitido.

Os blocos ``hash6`` e ``titulo`` são opcionais (parametrização do
programa de origem). Arquivos que NÃO são mídia (office, PDFs etc.)
não devem ser renomeados.

A pasta de destino por data é montada por :func:`montar_pasta_destino`
(máscara strftime parametrizável + sufixo opcional).
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path

# Ano mais antigo aceito nas datas (arquivos anteriores são ignorados).
ANO_MINIMO_PADRAO = 1980

# Limite de tamanho do nome gerado (segurança para sistemas de arquivos).
MAX_COMPRIMENTO_NOME = 240

# Quanto uma data pode estar "no futuro" e ainda ser aceita.
# Por que existe: em disco de rede (Proton Drive, NAS) e em máquinas de CI o
# carimbo de tempo do arquivo costuma ficar à frente do relógio local — às
# vezes microssegundos, às vezes horas (fuso do servidor). Sem essa folga o
# arquivo perde a data e vai parar em "sem_data". Um dia é generoso o
# bastante para o fuso e curto o bastante para barrar datas absurdas.
TOLERANCIA_FUTURO = timedelta(days=1)

# Abreviações de meses aceitas no nome do arquivo (PT e EN).
MESES = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    "fev": 2, "abr": 4, "mai": 5, "ago": 8, "set": 9, "out": 10, "dez": 12,
}

# Um título válido tem apenas letras minúsculas, números e "_".
RE_TITULO = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")


def dentro_do_periodo(dt, ano_minimo: int = ANO_MINIMO_PADRAO) -> bool:
    """Indica se a data é plausível: não nula, não antiga demais, não futura.

    "Não futura" tem uma folga de :data:`TOLERANCIA_FUTURO`: um arquivo
    gravado com o relógio segundos ou horas adiantado é jitter de relógio,
    não data inválida — e descartá-lo faria o arquivo cair em "sem_data".
    Datas muito à frente (mês que vem, 2099) continuam recusadas.
    """
    if dt is None or dt.year < ano_minimo:
        return False
    return dt <= datetime.now() + TOLERANCIA_FUTURO


def montar_dt(ano, mes, dia, hora=0, minuto=0, segundo=0,
              ano_minimo: int = ANO_MINIMO_PADRAO) -> datetime | None:
    """Monta um datetime validado; devolve None se a data for inválida."""
    try:
        dt = datetime(int(ano), int(mes), int(dia), int(hora), int(minuto), int(segundo))
    except (ValueError, TypeError):
        return None
    return dt if dentro_do_periodo(dt, ano_minimo) else None


def formatar_data(dt: datetime) -> str:
    """Formata um datetime na máscara do nome padrão: YYYY_MM_DD_HHhMMmSSs.

    Ex.: datetime(2023, 5, 10, 14, 30, 5) -> "2023_05_10_14h30m05s".
    """
    return (f"{dt.year:04d}_{dt.month:02d}_{dt.day:02d}_"
            f"{dt.hour:02d}h{dt.minute:02d}m{dt.second:02d}s")


def parsear_data_exif(texto, ano_minimo: int = ANO_MINIMO_PADRAO) -> datetime | None:
    """Parseia o formato clássico do EXIF: "YYYY:MM:DD HH:MM:SS".

    Aceita variações comuns ("YYYY-MM-DDTHH:MM:SS", underscores etc.).
    """
    s = str(texto).strip()
    s = s.replace("-", ":").replace("_", ":").replace("T", " ")
    s = re.sub(r"\s+", " ", s)
    m = re.match(r"(\d{4}):(\d{2}):(\d{2})[ T](\d{2}):(\d{2}):(\d{2})", s)
    if not m:
        return None
    return montar_dt(*m.groups(), ano_minimo=ano_minimo)


# Tabela de máscaras de data aceitas no NOME do arquivo.
# Cada entrada: (regex, ordem dos grupos em (ano, mes, dia, hora, minuto,
# segundo); grupos ausentes recebem 0 (ex.: máscaras só com data).
_MASCARAS_DATA_NOME = [
    (r"(?<!\d)(\d{4})_(\d{2})_(\d{2})_(\d{2})h(\d{2})m(\d{2})s", (1, 2, 3, 4, 5, 6)),
    (r"(?<!\d)(\d{4})_(\d{2})_(\d{2})_(\d{2})_(\d{2})_(\d{2})(?!\d)", (1, 2, 3, 4, 5, 6)),
    (r"(?<!\d)(\d{4})(\d{2})(\d{2})\D?([0-1]\d|2[0-4])([0-5]\d)([0-5]\d)(?!\d)", (1, 2, 3, 4, 5, 6)),
    (r"(?<!\d)(\d{4})-(\d{2})-(\d{2})[ T_-](\d{2})[.:-](\d{2})(?:[.:-](\d{2}))?(?!\d)", (1, 2, 3, 4, 5, 6)),
    (r"(?<!\d)(0[1-9]|[1-2]\d|3[0-1])\D(0[1-9]|1[0-2])\D(19[7-9]\d|20[0-2]\d)\D([0-1]\d|2[0-4])\D([0-5]\d)\D([0-5]\d)(?!\d)", (3, 2, 1, 4, 5, 6)),
    (r"(?<!\d)(0[1-9]|[1-2]\d|3[0-1])(0[1-9]|1[0-2])(19[7-9]\d|20[0-2]\d)\D?([0-1]\d|2[0-4])([0-5]\d)([0-5]\d)(?!\d)", (3, 2, 1, 4, 5, 6)),
    (r"(?<!\d)(0[1-9]|1[0-2])\D(0[1-9]|[1-2]\d|3[0-1])\D(19[7-9]\d|20[0-2]\d)\D([0-1]\d|2[0-4])\D([0-5]\d)\D([0-5]\d)(?!\d)", (3, 1, 2, 4, 5, 6)),
    (r"(?<!\d)(0[1-9]|1[0-2])(0[1-9]|[1-2]\d|3[0-1])(19[7-9]\d|20[0-2]\d)\D?([0-1]\d|2[0-4])([0-5]\d)([0-5]\d)(?!\d)", (3, 1, 2, 4, 5, 6)),
    (r"(?<!\d)(\d{4})_(\d{2})_(\d{2})(?!\d)", (1, 2, 3, 0, 0, 0)),
    (r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)", (1, 2, 3, 0, 0, 0)),
    (r"(?<!\d)(\d{4})(\d{2})(\d{2})(?!\d)", (1, 2, 3, 0, 0, 0)),
]


def _datas_nome_mascaras_numericas(nome, ano_minimo, candidatos):
    """Aplica as máscaras numéricas e adiciona os candidatos válidos."""
    for padrao, ordem in _MASCARAS_DATA_NOME:
        for m in re.finditer(padrao, nome):
            args = [int(m.group(i)) if i and m.group(i) else 0 for i in ordem]
            dt = montar_dt(*args, ano_minimo=ano_minimo)
            if dt is not None:
                candidatos.append(dt)


def _datas_nome_meses(nome, ano_minimo, candidatos):
    """Aplica as máscaras com mês por extenso (jan_02_2020, 02 jan 2020)."""
    for m in re.finditer(r"\b([A-Za-z]{3})[ _.\-](\d{1,2})[ _.\-](\d{4})\b", nome):
        mes = MESES.get(m.group(1).lower())
        if mes:
            dt = montar_dt(m.group(3), mes, m.group(2), ano_minimo=ano_minimo)
            if dt is not None:
                candidatos.append(dt)
    for m in re.finditer(r"\b(\d{1,2})[ _.\-]([A-Za-z]{3})[ _.\-](\d{4})\b", nome):
        mes = MESES.get(m.group(2).lower())
        if mes:
            dt = montar_dt(m.group(3), mes, m.group(1), ano_minimo=ano_minimo)
            if dt is not None:
                candidatos.append(dt)


def extrair_data_nome(nome: str, ano_minimo: int = ANO_MINIMO_PADRAO) -> datetime | None:
    """Extrai a data mais provável do nome do arquivo.

    Várias máscaras são tentadas (YYYY_MM_DD_HHhMMmSSs, YYYYMMDDhhmmss,
    DDMMYYYY, MMDDYYYY, ISO, MMM_DD_YYYY etc.). Entre os candidatos
    válidos, prefere-se o mais antigo que tenha horário real (evita
    00:00:00, comum em nomes de câmeras).
    """
    candidatos = []
    _datas_nome_mascaras_numericas(str(nome), ano_minimo, candidatos)
    _datas_nome_meses(str(nome), ano_minimo, candidatos)
    if not candidatos:
        return None
    # Prefere datas com horário real; entre elas, a mais antiga.
    precisos = [dt for dt in candidatos if not (dt.hour == 0 and dt.minute == 0 and dt.second == 0)]
    return min(precisos or candidatos)


def titulo_valido(titulo) -> bool:
    """Indica se o título respeita o formato snake_case do nome padrão.

    Ex.: "festa_de_aniversario" é válido; "Festa Aniversário" não.
    """
    return bool(titulo) and bool(RE_TITULO.match(str(titulo)))


def montar_nome_midia(
    data_min: datetime,
    data_max: datetime,
    cidade: str,
    *,
    hash6: str | None = None,
    titulo: str = "",
    extensao: str = "",
) -> str | None:
    """Monta o nome padrão de mídia (fotos, vídeos e áudios).

    Formato: YYYY_MM_DD_HHhMMmSSs-YYYY_MM_DD_HHhMMmSSs-cidade-hash6-titulo.ext

    Parametrização:

    - ``hash6`` vazio/None -> o bloco de hash é omitido.
    - ``titulo`` vazio (sem IA) -> o bloco de título é omitido.
    - O hash vem ANTES do título: mesmo horário + mesmo título de mídias
      diferentes não colidem.

    Retorna None se o nome exceder MAX_COMPRIMENTO_NOME.
    """
    base = f"{formatar_data(data_min)}-{formatar_data(data_max)}-{cidade}"
    if hash6:
        base = f"{base}-{hash6}"
    if titulo:
        base = f"{base}-{titulo}"
    nome = f"{base}{extensao}"
    if len(nome) > MAX_COMPRIMENTO_NOME:
        return None
    return nome


def preservar_nome_original(
    nome_atual: str,
    data_min: datetime | None,
    data_max: datetime | None,
    cidade: str,
    hash6: str | None = None,
) -> bool:
    """Indica se o nome ATUAL já carrega um título que o nome alvo perderia.

    Cenário que isso resolve: um arquivo já foi nomeado com título de IA
    (``...-sem_gps-retrato_de_jovem.jpg``) e uma nova execução roda **sem
    IA**. O nome alvo sairia sem o bloco de título, apagando uma informação
    que só uma nova chamada de API saberia recriar. Nesse caso o certo é
    manter o nome original.

    Devolve True somente quando as duas condições valem:

    1. o nome atual começa exatamente pelo alvo sem título, isto é,
       ``{data_min}-{data_max}-{cidade}`` (o bloco ``hash6``, se houver, é
       aceito logo em seguida) — ou seja, é o MESMO arquivo já nomeado;
    2. o que sobra depois disso é um título snake_case válido.

    Qualquer divergência de data ou cidade devolve False: aí o nome alvo
    traz informação nova e a renomeação vale a pena.

    Exemplos (data 1997-06-10 21:17:16, cidade "sem_gps", hash6 "og12s3")::

        "1997_..-1997_..-sem_gps-retrato.jpg"         -> True  (tem título)
        "1997_..-1997_..-sem_gps-og12s3-retrato.jpg"  -> True  (tem título)
        "1997_..-1997_..-sem_gps-og12s3.jpg"          -> False (nada a perder)
        "1997_..-1997_..-fortaleza-retrato.jpg"       -> False (outra cidade)
    """
    if data_min is None or data_max is None:
        return False
    # Prefixo do nome alvo SEM o bloco de título: se o arquivo já foi
    # nomeado por este mesmo programa, o nome começa exatamente assim.
    prefixo = f"{formatar_data(data_min)}-{formatar_data(data_max)}-{cidade}"
    radical = Path(nome_atual).stem
    if not radical.startswith(prefixo):
        return False
    resto = radical[len(prefixo):].lstrip("-")
    # O hash6 fica ANTES do título: se estiver presente, pula para o título.
    if hash6 and resto.startswith(hash6):
        resto = resto[len(hash6):].lstrip("-")
    return titulo_valido(resto)


def montar_pasta_destino(
    destino: Path,
    dt: datetime | None,
    mask: str,
    sufixo: str | None = None,
) -> Path:
    """Monta a subpasta de destino: {data_formatada}-{sufixo} (ou "sem_data").

    - ``mask``: máscara strftime parametrizável pelo programa de origem
      (ex.: "%Y_%m", "%Y_%m_%d").
    - ``sufixo``: bloco opcional de origem (videos, social_media, ...).
    - Sem data (dt None): a pasta é "sem_data".
    """
    if dt is None:
        return destino / "sem_data"
    nome = dt.strftime(mask)
    if sufixo:
        nome = f"{nome}-{sufixo}"
    return destino / nome


__all__ = [
    "ANO_MINIMO_PADRAO",
    "MAX_COMPRIMENTO_NOME",
    "TOLERANCIA_FUTURO",
    "dentro_do_periodo",
    "extrair_data_nome",
    "formatar_data",
    "montar_dt",
    "montar_nome_midia",
    "montar_pasta_destino",
    "preservar_nome_original",
    "parsear_data_exif",
    "titulo_valido",
]
