"""Pacote compartilhado entre projetos Python (pereiras-common).

Contém funções reutilizáveis por vários scripts Python:

- :mod:`pereiras_common.metadados`: datas e GPS de fotos, vídeos e áudios
  (+ coleta unificada obter_datas e sufixos de pasta).
- :mod:`pereiras_common.nomeacao`: nomes padrão de mídia e pastas de
  destino (formato YYYY_MM_DD_HHhMMmSSs-...-cidade-hash6-titulo.ext).
- :mod:`pereiras_common.ia`: análise de fotos com IA (Gemini/OpenAI).
- :mod:`pereiras_common.geolocalizacao`: cidade por GPS (Nominatim).
- :mod:`pereiras_common.locais`: onde guardar dados, logs e cache.
- :mod:`pereiras_common.uteis`: texto (snake_case), SHA-256, hash curto,
  título normalizado, cache JSONL e chaves de API.
"""

from .geolocalizacao import (
    carregar_cache_gps,
    cidade_ou_coordenadas,
    cidade_por_gps,
    salvar_cache_gps,
)
from .ia import AnaliseFoto, ErroAnaliseIA, analisar_foto
from .locais import (
    NOME_PASTA_DADOS,
    pasta_cache,
    pasta_dados_colecao,
    pasta_logs,
    resolver_pasta_dados,
)
from .metadados import (
    ALL_EXTENSIONS,
    EXTS_AUDIO,
    EXTS_IMAGEM,
    EXTS_OFFICE,
    EXTS_OUTROS,
    EXTS_VIDEO,
    Metadados,
    classificar_sufixo,
    classificar_tipo,
    data_filesystem,
    extrair_metadados,
    gms_para_decimal,
    ler_gps_exif,
    metadados_audio,
    metadados_exiftool,
    metadados_imagem,
    metadados_video,
    obter_datas,
    obter_gps,
    parsear_data_iso,
    parsear_iso6709,
    registrar_heif,
)
from .nomeacao import (
    ANO_MINIMO_PADRAO,
    MAX_COMPRIMENTO_NOME,
    dentro_do_periodo,
    extrair_data_nome,
    formatar_data,
    montar_dt,
    montar_nome_midia,
    montar_pasta_destino,
    parsear_data_exif,
    titulo_valido,
)
from .uteis import (
    CHAVE_GEMINI_PADRAO,
    CHAVE_OPENAI_PADRAO,
    DIR_CHAVES_PADRAO,
    MAX_PALAVRAS_TITULO,
    carregar_cache_jsonl,
    gravar_cache_jsonl,
    hash_curto_6,
    ler_chave,
    normalizar_titulo,
    para_snake_case,
    sha256_arquivo,
)

__all__ = [
    "ALL_EXTENSIONS",
    "ANO_MINIMO_PADRAO",
    "AnaliseFoto",
    "CHAVE_GEMINI_PADRAO",
    "CHAVE_OPENAI_PADRAO",
    "DIR_CHAVES_PADRAO",
    "EXTS_AUDIO",
    "EXTS_IMAGEM",
    "EXTS_OFFICE",
    "EXTS_OUTROS",
    "EXTS_VIDEO",
    "ErroAnaliseIA",
    "MAX_COMPRIMENTO_NOME",
    "MAX_PALAVRAS_TITULO",
    "NOME_PASTA_DADOS",
    "Metadados",
    "analisar_foto",
    "carregar_cache_gps",
    "carregar_cache_jsonl",
    "cidade_ou_coordenadas",
    "cidade_por_gps",
    "classificar_sufixo",
    "classificar_tipo",
    "data_filesystem",
    "dentro_do_periodo",
    "extrair_data_nome",
    "extrair_metadados",
    "formatar_data",
    "gms_para_decimal",
    "gravar_cache_jsonl",
    "hash_curto_6",
    "ler_chave",
    "ler_gps_exif",
    "metadados_audio",
    "metadados_exiftool",
    "metadados_imagem",
    "metadados_video",
    "montar_dt",
    "montar_nome_midia",
    "montar_pasta_destino",
    "normalizar_titulo",
    "obter_datas",
    "obter_gps",
    "para_snake_case",
    "pasta_cache",
    "pasta_dados_colecao",
    "pasta_logs",
    "parsear_data_exif",
    "parsear_data_iso",
    "parsear_iso6709",
    "registrar_heif",
    "resolver_pasta_dados",
    "salvar_cache_gps",
    "sha256_arquivo",
    "titulo_valido",
]
