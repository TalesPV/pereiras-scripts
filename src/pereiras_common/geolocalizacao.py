#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Geolocalização: cidade mais próxima do GPS (pereiras-common).

Consulta o Nominatim (OpenStreetMap), serviço gratuito de geocodificação
reversa, com cache local em JSON para não repetir consultas.

Regras de uso do serviço (importante):

- Máximo ~1 requisição por segundo (NOMINATIM_DELAY) — respeitar para
  não ser bloqueado.
- User-Agent identificado (exigência do OSM).
- Falhas NÃO são gravadas no cache: uma execução futura pode tentar de
  novo (útil quando a internet volta).
"""

from __future__ import annotations

import json
import logging
import time
import urllib.request
from pathlib import Path

from .uteis import para_snake_case

logger = logging.getLogger(__name__)

# Pausa entre consultas ao Nominatim (política de uso do serviço).
NOMINATIM_DELAY = 1.1

# Identificação do aplicativo nas requisições HTTP (exigido pelo OSM).
USER_AGENT = "pereiras-scripts/1.0 (uso pessoal)"


def carregar_cache_gps(cache_path: str | Path | None = None) -> dict:
    """Lê o cache de cidades do disco; devolve {} se não existir/corrompido.

    ``cache_path`` None = sem persistência (cache apenas em memória).
    """
    if cache_path is None:
        return {}
    try:
        return json.loads(Path(cache_path).read_text(encoding="utf-8"))
    except Exception:
        return {}


def salvar_cache_gps(cache: dict, cache_path: str | Path | None = None) -> None:
    """Grava o cache de cidades no disco (falhas de I/O são ignoradas)."""
    if cache_path is None:
        return
    try:
        Path(cache_path).write_text(json.dumps(cache, ensure_ascii=False, indent=1),
                                    encoding="utf-8")
    except OSError:
        pass


def cidade_por_gps(
    lat: float,
    lon: float,
    cache: dict | None = None,
    cache_path: str | Path | None = None,
    user_agent: str = USER_AGENT,
) -> str | None:
    """Devolve o nome da cidade mais próxima das coordenadas.

    - Se as coordenadas já estão no cache, devolve direto (sem internet).
    - Senão, consulta o Nominatim, salva no cache e devolve o nome.
    - Em caso de falha (sem internet etc.), devolve None e NÃO polui o
      cache (uma execução futura pode tentar de novo).
    """
    cache = cache if cache is not None else carregar_cache_gps(cache_path)
    # Chave com 5 casas decimais: mesma rua = mesma chave = mesma consulta.
    chave = f"{lat:.5f},{lon:.5f}"
    if chave in cache:
        return cache[chave]
    try:
        # Consulta reversa: coordenadas -> endereço (zoom 10 ~ nível de cidade).
        url = ("https://nominatim.openstreetmap.org/reverse?format=jsonv2"
               f"&lat={lat:.6f}&lon={lon:.6f}&zoom=10&accept-language=pt-BR,pt")
        req = urllib.request.Request(url, headers={"User-Agent": user_agent})
        with urllib.request.urlopen(req, timeout=20) as resp:
            dados = json.loads(resp.read().decode("utf-8"))
        end = dados.get("address", {}) or {}
        # Tenta os campos de cidade do mais específico ao mais genérico.
        cidade = (end.get("city") or end.get("town") or end.get("village")
                  or end.get("municipality") or end.get("county") or end.get("state") or "")
        if not cidade:
            cidade = dados.get("name") or ""
        cache[chave] = cidade
        salvar_cache_gps(cache, cache_path)
        # Respeita a política de uso do Nominatim: no máximo ~1 req/s.
        time.sleep(NOMINATIM_DELAY)
        return cidade
    except Exception as e:
        logger.warning("Falha na consulta Nominatim (%s): %s", chave, e)
        return None


def cidade_ou_coordenadas(
    lat: float,
    lon: float,
    cache: dict | None = None,
    cache_path: str | Path | None = None,
) -> str:
    """Devolve o nome da cidade em snake_case ou as coordenadas formatadas.

    - Com cidade: "sao_paulo" (pronta para compor o nome do arquivo).
    - Sem cidade (falha/offline): "-23_5500_-46_6333" (coordenadas com
      "_" no lugar de pontos e vírgulas, sem caracteres especiais).
    """
    nome = cidade_por_gps(lat, lon, cache, cache_path)
    if nome:
        return para_snake_case(nome)
    return (f"{lat:.4f},{lon:.4f}".replace(",", "_").replace(".", "_").replace(" ", "_"))


__all__ = [
    "NOMINATIM_DELAY",
    "USER_AGENT",
    "carregar_cache_gps",
    "cidade_ou_coordenadas",
    "cidade_por_gps",
    "salvar_cache_gps",
]
