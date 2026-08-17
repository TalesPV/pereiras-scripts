"""Pacote compartilhado entre projetos Python (pereiras-common).

Contém funções reutilizáveis por vários scripts Python:

- :mod:`pereiras_common.metadados`: datas e GPS de fotos, vídeos e áudios.
- :mod:`pereiras_common.ia`: análise de fotos com IA (Gemini/OpenAI).
- :mod:`pereiras_common.uteis`: texto (snake_case), hash curto e chaves.
"""

from .ia import AnaliseFoto, ErroAnaliseIA, analisar_foto
from .metadados import (
    ALL_EXTENSIONS,
    EXTS_AUDIO,
    EXTS_IMAGEM,
    EXTS_OFFICE,
    EXTS_OUTROS,
    EXTS_VIDEO,
    Metadados,
    classificar_tipo,
    data_filesystem,
    extrair_metadados,
    gms_para_decimal,
    ler_gps_exif,
    metadados_audio,
    metadados_exiftool,
    metadados_imagem,
    metadados_video,
    obter_gps,
    parsear_data_iso,
    parsear_iso6709,
    registrar_heif,
)
from .uteis import (
    CHAVE_GEMINI_PADRAO,
    CHAVE_OPENAI_PADRAO,
    DIR_CHAVES_PADRAO,
    hash_curto_6,
    ler_chave,
    para_snake_case,
)

__all__ = [
    "ALL_EXTENSIONS",
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
    "Metadados",
    "analisar_foto",
    "classificar_tipo",
    "data_filesystem",
    "extrair_metadados",
    "gms_para_decimal",
    "hash_curto_6",
    "ler_chave",
    "ler_gps_exif",
    "metadados_audio",
    "metadados_exiftool",
    "metadados_imagem",
    "metadados_video",
    "obter_gps",
    "para_snake_case",
    "parsear_data_iso",
    "parsear_iso6709",
    "registrar_heif",
]
