#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Análise de fotos com Inteligência Artificial (pereiras-common).

Este módulo concentra a análise de fotos com IA generativa (Gemini ou
OpenAI). A função principal é :func:`analisar_foto`: ela recebe a chave
de API, o tipo de IA e o caminho completo do arquivo, e devolve um
objeto :class:`AnaliseFoto` com os campos que os projetos usam:

- ``titulo``: título curto em ``snake_case`` (para compor nomes de arquivo).
- ``resumo``: descrição objetiva do conteúdo da imagem.
- ``nivel``: índice de legalidade, de 1 a 5 (veja a escala abaixo).
- ``motivo``: justificativa curta do índice.
- ``modelo``: modelo de IA usado na análise.
- ``tokens_entrada``/``tokens_saida``: consumo de tokens (para custos).

Escala de legalidade (1-5):

1. Conteúdo comum e seguro.
2. Levemente sensível (ex.: conteúdo adulto legal).
3. Suspeito — revisão manual recomendada.
4. Provavelmente ilegal.
5. Ilegal/crítico (ex.: abuso de menores ou crimes graves).

Segurança: a chave de API é SEMPRE passada como parâmetro e nunca é
gravada em disco ou em log. Os programas clientes a leem de um arquivo
fora do repositório (padrão: ``~/.chaves_ia/``).

Exemplos de uso::

    from pereiras_common.ia import analisar_foto

    analise = analisar_foto("MINHA_CHAVE", "gemini", "foto.jpg")
    print(analise.titulo, analise.nivel)
"""

from __future__ import annotations

import base64
import json
import logging
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from google import genai
from google.genai import types
from openai import OpenAI
from PIL import Image

from .uteis import para_snake_case

logger = logging.getLogger(__name__)

# ------------------------------------------------------------- constantes

# Modelos padrão de cada tipo de IA (podem ser sobrescritos via parâmetro).
MODELO_GEMINI = "gemini-3.6-flash"
MODELO_OPENAI = "gpt-4o-mini"

# Tipos de IA aceitos atualmente por analisar_foto().
TIPOS_IA_SUPORTADOS = ("gemini", "openai")

# Limites da imagem enviada à API: reduz custo e acelera a resposta.
MAX_DIMENSAO_PADRAO = 1024
QUALIDADE_JPEG_PADRAO = 85

# Tempo máximo de espera pela resposta da API (em milissegundos).
TIMEOUT_MS = 120000

# Instrução enviada junto com a imagem: pede um JSON com os campos do
# produto. O texto define também a escala 1-5 de legalidade.
PROMPT_ANALISE_FOTO = (
    "Você é um auditor de segurança de conteúdo. Analise a imagem e responda "
    "APENAS com um único objeto JSON válido, sem markdown e sem texto adicional, "
    "contendo exatamente estas chaves:\n"
    '- "titulo_resumo": título curto de até 5 palavras em português;\n'
    '- "descricao_completa": descrição objetiva e neutra do conteúdo da imagem;\n'
    '- "indice_ilegalidade": número inteiro de 1 a 5, onde 1 = conteúdo comum '
    'e seguro, 2 = levemente sensível (adulto legal), 3 = suspeito (revisão '
    'manual), 4 = provavelmente ilegal, 5 = ilegal/crítico (abuso de menores '
    'ou crimes graves);\n'
    '- "motivo": justificativa curta para o índice informado.'
)

# Padrão para remover cercas de markdown (```json ... ```) da resposta.
_RE_CERCA_MARKDOWN = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)

# Número máximo de palavras do título (mantém nomes de arquivo curtos).
MAX_PALAVRAS_TITULO = 5


# ------------------------------------------------------------- tipos

class ErroAnaliseIA(Exception):
    """Erro ao analisar um arquivo com IA (rede, imagem ilegível, resposta inválida)."""


@dataclass(slots=True)
class AnaliseFoto:
    """Resultado da análise de uma foto por IA (ver docstring do módulo)."""

    titulo: str
    """Título curto em snake_case (ex.: "festa_na_praia")."""

    resumo: str
    """Descrição objetiva do conteúdo da imagem."""

    nivel: int
    """Índice de legalidade de 1 (seguro) a 5 (crítico)."""

    motivo: str
    """Justificativa curta do índice."""

    modelo: str
    """Modelo de IA usado (ex.: "gemini-3.6-flash")."""

    tokens_entrada: int = 0
    """Tokens de entrada consumidos (para cálculo de custo)."""

    tokens_saida: int = 0
    """Tokens de saída consumidos (para cálculo de custo)."""


# ------------------------------------------------------- funções internas

def _preparar_imagem_bytes(
    caminho: str | Path,
    *,
    max_dimensao: int = MAX_DIMENSAO_PADRAO,
    qualidade_jpeg: int = QUALIDADE_JPEG_PADRAO,
) -> bytes:
    """Lê a imagem do disco e devolve bytes JPEG prontos para a API.

    - Converte qualquer formato (PNG, HEIC, etc.) para JPEG.
    - Reduz o tamanho máximo para ``max_dimensao`` pixels (economia de tokens).
    - Usa um arquivo temporário em memória: nada é gravado em disco.
    """
    try:
        # Abre sem carregar a imagem inteira na memória ainda.
        img = Image.open(caminho)
        # Garante 3 canais de cor (RGB): alguns formatos são P, RGBA, etc.
        img = img.convert("RGB")
        # Mantém a proporção e limita o maior lado a max_dimensao pixels.
        img.thumbnail((max_dimensao, max_dimensao), Image.Resampling.LANCZOS)
        # Salva em JPEG num buffer temporário (em memória até 8 MB).
        buf = tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024)
        img.save(buf, format="JPEG", quality=qualidade_jpeg)
        buf.seek(0)
        return buf.read()
    except Exception as e:
        # Arquivo corrompido, inexistente ou sem permissão de leitura.
        raise ErroAnaliseIA(f"não foi possível ler a imagem {caminho}: {e}") from e


def _normalizar_titulo(texto: object) -> str:
    """Limpa o título devolvido pela IA e limita a 5 palavras em snake_case."""
    t = str(texto or "").strip().strip('"`*#')
    palavras = t.split()
    if len(palavras) > MAX_PALAVRAS_TITULO:
        t = " ".join(palavras[:MAX_PALAVRAS_TITULO])
    t = para_snake_case(t)
    # "sem_nome" significa que não sobrou texto útil: devolvemos vazio.
    return t if t != "sem_nome" else ""


def _extrair_json_resposta(texto: object) -> dict:
    """Extrai o primeiro objeto JSON válido da resposta da IA.

    As IAs costumam envolver o JSON em markdown (```json ... ```) ou
    adicionar texto antes/depois. Esta função procura o primeiro ``{...}``
    balanceado e devolve como dict; se não encontrar, lança ValueError.
    """
    s = str(texto or "").strip()
    if not s:
        raise ValueError("resposta vazia")
    # Remove cercas de markdown do começo e do fim da resposta.
    s = _RE_CERCA_MARKDOWN.sub("", s)
    # Caso mais comum: a resposta inteira já é o objeto JSON.
    try:
        dados = json.loads(s)
        if isinstance(dados, dict):
            return dados
    except json.JSONDecodeError:
        pass
    # Plano B: procura o primeiro { ... } balanceado dentro do texto.
    for inicio, ch in enumerate(s):
        if ch != "{":
            continue
        profundidade = 0
        for i in range(inicio, len(s)):
            if s[i] == "{":
                profundidade += 1
            elif s[i] == "}":
                profundidade -= 1
                if profundidade == 0:
                    try:
                        return json.loads(s[inicio:i + 1])
                    except json.JSONDecodeError:
                        break
    raise ValueError("JSON não encontrado na resposta")


def _montar_analise(dados: dict, modelo: str) -> AnaliseFoto:
    """Converte o JSON da IA em um objeto AnaliseFoto validado."""
    try:
        nivel = int(dados.get("indice_ilegalidade", 0))
    except (TypeError, ValueError):
        nivel = 0
    if not 1 <= nivel <= 5:
        raise ErroAnaliseIA(f"índice de legalidade fora da faixa 1-5: {nivel!r}")
    return AnaliseFoto(
        titulo=_normalizar_titulo(dados.get("titulo_resumo")),
        resumo=str(dados.get("descricao_completa") or "").strip(),
        nivel=nivel,
        motivo=str(dados.get("motivo") or "").strip(),
        modelo=modelo,
    )


def _analisar_com_gemini(
    chave: str, imagem_bytes: bytes, modelo: str,
) -> AnaliseFoto:
    """Chama o Gemini com a imagem e o prompt; devolve AnaliseFoto."""
    # Cria o cliente com timeout estendido (imagens demoram mais que texto).
    try:
        client = genai.Client(
            api_key=chave,
            http_options=types.HttpOptions(timeout=TIMEOUT_MS),
        )
    except Exception:
        # Fallback: cria o cliente sem opções extras (SDKs mais antigos).
        client = genai.Client(api_key=chave)
    # Conteúdo multimídia: primeiro o texto, depois a imagem.
    partes = [
        types.Part.from_text(text=PROMPT_ANALISE_FOTO),
        types.Part.from_bytes(data=imagem_bytes, mime_type="image/jpeg"),
    ]
    resp = client.models.generate_content(
        model=modelo,
        contents=partes,
        config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=1000,
        ),
    )
    texto = resp.text or ""
    dados = _extrair_json_resposta(texto)
    analise = _montar_analise(dados, modelo)
    # Contabiliza tokens para cálculo de custo (0 se a API não informar).
    uso = getattr(resp, "usage_metadata", None)
    analise.tokens_entrada = int(getattr(uso, "prompt_token_count", 0) or 0)
    analise.tokens_saida = int(getattr(uso, "candidates_token_count", 0) or 0)
    return analise


def _analisar_com_openai(
    chave: str, imagem_bytes: bytes, modelo: str,
) -> AnaliseFoto:
    """Chama o GPT (OpenAI) com a imagem e o prompt; devolve AnaliseFoto."""
    client = OpenAI(api_key=chave, timeout=120.0)
    # A API OpenAI recebe a imagem como data-URI em base64.
    data_uri = f"data:image/jpeg;base64,{base64.b64encode(imagem_bytes).decode('ascii')}"
    resp = client.chat.completions.create(
        model=modelo,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": PROMPT_ANALISE_FOTO},
                {"type": "image_url", "image_url": {"url": data_uri}},
            ],
        }],
        temperature=0.2,
        max_tokens=1000,
    )
    texto = ""
    if resp.choices:
        texto = getattr(resp.choices[0].message, "content", "") or ""
    dados = _extrair_json_resposta(texto)
    analise = _montar_analise(dados, modelo)
    # Contabiliza tokens para cálculo de custo (0 se a API não informar).
    uso = getattr(resp, "usage", None)
    analise.tokens_entrada = int(getattr(uso, "prompt_tokens", 0) or 0)
    analise.tokens_saida = int(getattr(uso, "completion_tokens", 0) or 0)
    return analise


# --------------------------------------------------------- função principal

def analisar_foto(
    chave_assinatura: str,
    tipo_ia: str,
    caminho_arquivo: str | Path,
    *,
    modelo: str | None = None,
    max_dimensao: int = MAX_DIMENSAO_PADRAO,
    qualidade_jpeg: int = QUALIDADE_JPEG_PADRAO,
) -> AnaliseFoto:
    """Analisa uma foto com IA e devolve os campos do produto.

    Parâmetros:

    - ``chave_assinatura``: chave de API (nunca é gravada em log/disco).
    - ``tipo_ia``: qual IA usar — por enquanto ``"gemini"`` ou ``"openai"``.
    - ``caminho_arquivo``: caminho COMPLETO do arquivo de imagem.
    - ``modelo``: opcional; sobrescreve o modelo padrão do tipo de IA.
    - ``max_dimensao``/``qualidade_jpeg``: ajustam a imagem enviada.

    Retorna :class:`AnaliseFoto` (título snake_case, resumo, nível 1-5,
    motivo, modelo e tokens). Lança :class:`ErroAnaliseIA` se a análise
    falhar por qualquer motivo (imagem ilegível, erro de rede, resposta
    inválida etc.) e ``ValueError`` se ``tipo_ia`` não for suportado.
    """
    tipo_ia = str(tipo_ia).strip().lower()
    if tipo_ia not in TIPOS_IA_SUPORTADOS:
        raise ValueError(
            f"tipo_ia {tipo_ia!r} não suportado; use: {', '.join(TIPOS_IA_SUPORTADOS)}"
        )
    if modelo is None:
        modelo = MODELO_GEMINI if tipo_ia == "gemini" else MODELO_OPENAI
    # Prepara a imagem ANTES de criar o cliente: falha cedo se o arquivo
    # não existir ou estiver corrompido (sem gastar chamadas de API).
    imagem_bytes = _preparar_imagem_bytes(
        caminho_arquivo, max_dimensao=max_dimensao, qualidade_jpeg=qualidade_jpeg
    )
    try:
        if tipo_ia == "gemini":
            return _analisar_com_gemini(chave_assinatura, imagem_bytes, modelo)
        return _analisar_com_openai(chave_assinatura, imagem_bytes, modelo)
    except ErroAnaliseIA:
        # Erros nossos (validação) já têm mensagem boa: repassa como veio.
        raise
    except Exception as e:
        # Erros de rede, autenticação (chave inválida), cota etc.
        logger.debug("Falha na análise com %s: %s", tipo_ia, e)
        raise ErroAnaliseIA(f"falha na análise com {tipo_ia} ({e})") from e


__all__ = [
    "AnaliseFoto",
    "ErroAnaliseIA",
    "MODELO_GEMINI",
    "MODELO_OPENAI",
    "PROMPT_ANALISE_FOTO",
    "TIPOS_IA_SUPORTADOS",
    "analisar_foto",
]
