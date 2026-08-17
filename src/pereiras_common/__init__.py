"""Pacote compartilhado entre projetos Python (pereiras-common).

Contém funções reutilizáveis por vários scripts Python; atualmente,
extração unificada de metadados (datas e GPS) de fotos, vídeos e
áudios. Ver :mod:`pereiras_common.metadados`.
"""

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

__all__ = [
    "ALL_EXTENSIONS",
    "EXTS_AUDIO",
    "EXTS_IMAGEM",
    "EXTS_OFFICE",
    "EXTS_OUTROS",
    "EXTS_VIDEO",
    "Metadados",
    "classificar_tipo",
    "data_filesystem",
    "extrair_metadados",
    "gms_para_decimal",
    "ler_gps_exif",
    "metadados_audio",
    "metadados_exiftool",
    "metadados_imagem",
    "metadados_video",
    "obter_gps",
    "parsear_data_iso",
    "parsear_iso6709",
    "registrar_heif",
]
