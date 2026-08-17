#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Testes da análise de fotos com IA (pereiras_common.ia).

Os clientes de IA são dublês (fakes): nenhum teste chama a API real.
"""

import json

import pytest
from PIL import Image

import pereiras_common.ia as mod
from pereiras_common.ia import AnaliseFoto, ErroAnaliseIA, analisar_foto

_JSON_VALIDO = json.dumps({
    "titulo_resumo": "Festa na Praia do Norte",
    "descricao_completa": "Pessoas reunidas em uma praia durante o dia.",
    "indice_ilegalidade": 1,
    "motivo": "Conteúdo familiar comum, sem indícios de ilegalidade.",
}, ensure_ascii=False)


def _criar_imagem(caminho):
    Image.new("RGB", (64, 64), (255, 0, 0)).save(caminho)


class _RespostaGemini:
    """Dublê da resposta do Gemini: atributos usados pelo módulo."""

    def __init__(self, texto):
        self.text = texto
        self.usage_metadata = type("Uso", (), {
            "prompt_token_count": 100,
            "candidates_token_count": 50,
        })()


class _ClienteGeminiFalso:
    """Dublê do cliente Gemini: devolve sempre o mesmo texto."""

    def __init__(self, texto):
        self._texto = texto
        self.chamadas = []
        # O cliente real expõe client.models.generate_content(...).
        self.models = type("Models", (), {"generate_content": self.generate_content})()

    def generate_content(self, *args, **kwargs):
        self.chamadas.append(kwargs)
        return _RespostaGemini(self._texto)


class _CompletionsFalsas:
    def __init__(self, texto):
        self._texto = texto

    def create(self, *args, **kwargs):
        msg = type("Msg", (), {"content": self._texto})()
        choice = type("Choice", (), {"message": msg})()
        uso = type("Uso", (), {"prompt_tokens": 100, "completion_tokens": 50})()
        return type("Resp", (), {"choices": [choice], "usage": uso})()


class _ClienteOpenAIFalso:
    """Dublê do cliente OpenAI: devolve sempre o mesmo texto."""

    def __init__(self, texto):
        self._texto = texto
        self.chat = type("Chat", (), {"completions": _CompletionsFalsas(texto)})()


@pytest.fixture
def imagem_teste(tmp_path):
    caminho = tmp_path / "foto.jpg"
    _criar_imagem(caminho)
    return caminho


def _instalar_fake_gemini(monkeypatch, texto):
    def fabrica(**kwargs):
        cliente = _ClienteGeminiFalso(texto)
        cliente.api_key = kwargs.get("api_key")
        return cliente

    monkeypatch.setattr(mod.genai, "Client", fabrica)
    return fabrica


def test_analisar_foto_gemini_campos_completos(imagem_teste, monkeypatch):
    _instalar_fake_gemini(monkeypatch, _JSON_VALIDO)
    resultado = analisar_foto("MINHA-CHAVE-123456", "gemini", imagem_teste)
    assert isinstance(resultado, AnaliseFoto)
    assert resultado.titulo == "festa_na_praia_do_norte"
    assert resultado.resumo == "Pessoas reunidas em uma praia durante o dia."
    assert resultado.nivel == 1
    assert resultado.motivo == "Conteúdo familiar comum, sem indícios de ilegalidade."
    assert resultado.modelo == mod.MODELO_GEMINI
    assert resultado.tokens_entrada == 100
    assert resultado.tokens_saida == 50


def test_analisar_foto_openai_campos_completos(imagem_teste, monkeypatch):
    chaves_recebidas = {}

    def fabrica(**kwargs):
        chaves_recebidas["api_key"] = kwargs.get("api_key")
        return _ClienteOpenAIFalso(_JSON_VALIDO)

    monkeypatch.setattr(mod, "OpenAI", fabrica)
    resultado = analisar_foto("MINHA-CHAVE-123456", "openai", imagem_teste)
    assert resultado.titulo == "festa_na_praia_do_norte"
    assert resultado.nivel == 1
    assert resultado.modelo == mod.MODELO_OPENAI
    assert chaves_recebidas["api_key"] == "MINHA-CHAVE-123456"


def test_analisar_foto_tipo_ia_invalido(imagem_teste):
    with pytest.raises(ValueError):
        analisar_foto("CHAVE-123456", "xpto", imagem_teste)


def test_analisar_foto_arquivo_inexistente(tmp_path):
    with pytest.raises(ErroAnaliseIA):
        analisar_foto("CHAVE-123456", "gemini", tmp_path / "nao_existe.jpg")


def test_analisar_foto_resposta_sem_json(imagem_teste, monkeypatch):
    _instalar_fake_gemini(monkeypatch, "texto qualquer sem JSON")
    with pytest.raises(ErroAnaliseIA):
        analisar_foto("CHAVE-123456", "gemini", imagem_teste)


def test_analisar_foto_nivel_fora_da_faixa(imagem_teste, monkeypatch):
    json_ruim = json.dumps({
        "titulo_resumo": "algo",
        "descricao_completa": "algo",
        "indice_ilegalidade": 9,
        "motivo": "algo",
    })
    _instalar_fake_gemini(monkeypatch, json_ruim)
    with pytest.raises(ErroAnaliseIA):
        analisar_foto("CHAVE-123456", "gemini", imagem_teste)


def test_analisar_foto_titulo_limpo_ate_5_palavras(imagem_teste, monkeypatch):
    json_longo = json.dumps({
        "titulo_resumo": "Uma frase com mais de cinco palavras no título",
        "descricao_completa": "ok",
        "indice_ilegalidade": 1,
        "motivo": "ok",
    })
    _instalar_fake_gemini(monkeypatch, json_longo)
    resultado = analisar_foto("CHAVE-123456", "gemini", imagem_teste)
    assert resultado.titulo == "uma_frase_com_mais_de"


def test_analisar_foto_resposta_com_markdown(imagem_teste, monkeypatch):
    texto = "```json\n" + _JSON_VALIDO + "\n```"
    _instalar_fake_gemini(monkeypatch, texto)
    resultado = analisar_foto("CHAVE-123456", "gemini", imagem_teste)
    assert resultado.nivel == 1
    assert resultado.titulo == "festa_na_praia_do_norte"


def test_analisar_foto_erro_da_api(imagem_teste, monkeypatch):
    def fabrica(**kwargs):
        raise RuntimeError("falha de rede simulada")

    monkeypatch.setattr(mod.genai, "Client", fabrica)
    with pytest.raises(ErroAnaliseIA):
        analisar_foto("CHAVE-123456", "gemini", imagem_teste)
