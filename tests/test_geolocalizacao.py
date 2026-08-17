#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Testes do módulo de geolocalização (cidade por GPS, com cache local)."""

import json

import pytest

from pereiras_common.geolocalizacao import (
    carregar_cache_gps,
    cidade_ou_coordenadas,
    cidade_por_gps,
    salvar_cache_gps,
)


def test_carregar_cache_gps_inexistente(tmp_path):
    assert carregar_cache_gps(tmp_path / "nao_existe.json") == {}


def test_carregar_cache_gps_corrompido(tmp_path):
    caminho = tmp_path / "corrompido.json"
    caminho.write_text("isso não é json {", encoding="utf-8")
    assert carregar_cache_gps(caminho) == {}


def test_carregar_e_salvar_cache_gps(tmp_path):
    caminho = tmp_path / "cache.json"
    cache = {"-23.55000,-46.63333": "São Paulo"}
    salvar_cache_gps(cache, caminho)
    assert carregar_cache_gps(caminho) == cache


def test_cidade_por_gps_usa_cache_sem_rede(monkeypatch):
    def falhar(*args, **kwargs):
        raise AssertionError("não deveria acessar a rede com cache disponível")

    monkeypatch.setattr("pereiras_common.geolocalizacao.urllib.request.urlopen", falhar)
    cache = {"-23.55000,-46.63333": "São Paulo"}
    assert cidade_por_gps(-23.55, -46.633333, cache) == "São Paulo"


def test_cidade_por_gps_consulta_e_salva(tmp_path, monkeypatch):
    import pereiras_common.geolocalizacao as mod

    class _FakeResp:
        def read(self):
            return json.dumps({
                "address": {"city": "São Paulo"},
            }).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(mod.urllib.request, "urlopen", lambda *a, **k: _FakeResp())
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)
    cache = {}
    cache_path = tmp_path / "cache.json"
    assert cidade_por_gps(-23.55, -46.633333, cache, cache_path) == "São Paulo"
    assert cache["-23.55000,-46.63333"] == "São Paulo"
    assert carregar_cache_gps(cache_path) == cache


def test_cidade_por_gps_falha_de_rede(tmp_path, monkeypatch):
    import pereiras_common.geolocalizacao as mod

    def falhar(*args, **kwargs):
        raise OSError("sem internet")

    monkeypatch.setattr(mod.urllib.request, "urlopen", falhar)
    cache = {}
    assert cidade_por_gps(-23.55, -46.633333, cache, tmp_path / "cache.json") is None
    assert cache == {}, "falhas não devem poluir o cache"


def test_cidade_ou_coordenadas_com_cidade(monkeypatch):
    monkeypatch.setattr("pereiras_common.geolocalizacao.cidade_por_gps",
                        lambda lat, lon, cache=None, cache_path=None: "São Paulo")
    assert cidade_ou_coordenadas(-23.55, -46.633333, {}) == "sao_paulo"


def test_cidade_ou_coordenadas_sem_cidade(monkeypatch):
    monkeypatch.setattr("pereiras_common.geolocalizacao.cidade_por_gps",
                        lambda lat, lon, cache=None, cache_path=None: None)
    assert cidade_ou_coordenadas(-23.55, -46.633333, {}) == "-23_5500_-46_6333"
