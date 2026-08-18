#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extração de metadados (datas e GPS) de arquivos de foto, vídeo e áudio.

Fontes de metadados por tipo de arquivo:

- Imagens: EXIF (Pillow), XMP (GPS e datas) e texto PNG (tEXt/iTXt:
  "Creation Time", "date:create" etc.). Fallbacks: piexif e exifread,
  para EXIF parcialmente corrompido ou em formatos não padronizados.
- Vídeos: ffmpeg (creation_time e localização ISO 6709 / ©xyz do
  QuickTime, comum em vídeos de iPhone/Android). Fallback: tags
  MP4/MOV lidas com mutagen.
- Áudios: mutagen (ID3 do MP3, ©day/©xyz do MP4/M4A e comentários
  Vorbis do OGG/Opus/FLAC).
- Fallback global opcional: binário exiftool (Phil Harvey), se instalado.
- Sistema de arquivos: data de criação/modificação (última alternativa).

API principal::

    from pathlib import Path
    from pereiras_common.metadados import extrair_metadados

    md = extrair_metadados(Path("foto.jpg"))
    print(md.tipo, md.data_mais_antiga(), md.gps)
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import exifread
import imageio_ffmpeg
import mutagen
import piexif
import pillow_heif
from mutagen.id3 import ID3
from mutagen.mp4 import MP4
from PIL import Image

# Funções de data do módulo de nomeação (re-exportadas aqui por
# compatibilidade: montar_dt, dentro_do_periodo, parsear_data_exif).
from .nomeacao import dentro_do_periodo, extrair_data_nome, montar_dt, parsear_data_exif  # noqa: F401

logger = logging.getLogger(__name__)

ANO_MINIMO_PADRAO = 1980

EXTS_IMAGEM = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tif", ".tiff", ".heic", ".heif"}
EXTS_VIDEO = {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".webm", ".mpg", ".mpeg", ".3gp", ".m4v", ".flv", ".ts"}
EXTS_AUDIO = {".mp3", ".m4a", ".aac", ".ogg", ".opus", ".flac", ".wav", ".wma", ".amr", ".aiff", ".aif"}
EXTS_OFFICE = {".doc", ".docx", ".xls", ".xlsx", ".ods", ".rtf"}
EXTS_OUTROS = {".pdf", ".txt", ".url", ".lnk", ".zip", ".htm", ".html", ".js"}
ALL_EXTENSIONS = EXTS_IMAGEM | EXTS_VIDEO | EXTS_AUDIO | EXTS_OFFICE | EXTS_OUTROS

# Tags EXIF IFD0 que guardam datas (números fixos do padrão EXIF):
#   36867 = DateTimeOriginal (quando a foto foi tirada)
#   36868 = DateTimeDigitized (quando foi digitalizada)
#   306   = DateTime (quando o arquivo foi alterado pela última vez)
TAG_DATETIME_ORIGINAL = 36867
TAG_CREATE_DATE = 36868
TAG_MODIFY_DATE = 306
# 0x8769 = ponteiro para o sub-IFD EXIF, onde ficam 36867/36868. Ler apenas
# o IFD0 (o que Image.getexif() devolve) NÃO encontra a data de captura.
IFD_EXIF = 0x8769
# 0x8825 = ponteiro para o bloco GPS dentro do EXIF.
IFD_GPS = 0x8825

try:
    FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    FFMPEG_EXE = shutil.which("ffmpeg")

EXIFTOOL_EXE = shutil.which("exiftool")

# Expressões regulares usadas para encontrar datas e GPS nos textos de
# metadados. Cada padrão é explicado ao lado de quem o usa.
RE_DATA_ISO = re.compile(
    r"^(\d{4})[-:](\d{2})[-:](\d{2})(?:[T ](\d{2})[.:](\d{2})[.:](\d{2}))?"
)
RE_ANO_ISOLADO = re.compile(r"^\d{4}$")

# "creation_time" é o campo que o ffmpeg imprime no stderr ao inspecionar
# um vídeo: creation_time   : 2021-06-15T12:34:56.000000Z
RE_CREATION_TIME = re.compile(r"creation_time\s*:\s*(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})")

# Campos de localização que o ffmpeg imprime para vídeos QuickTime
# (iPhone/Android): "location" ou "location-eng" com coordenadas ISO 6709.
RE_LOCATION_FFMPEG = re.compile(
    r"^\s*(?:location-eng|location|com\.apple\.quicktime\.location\.ISO6709)\s*:\s*(.+?)\s*$",
    re.MULTILINE,
)

# Coordenadas no padrão ISO 6709, ex.: "+23.5500-046.6333+000/" ou
# "-23.55-046.63/". Os grupos capturam latitude, longitude e altitude.
RE_ISO6709 = re.compile(r"([+-]\d{1,3}(?:\.\d+)?)([+-]\d{1,3}(?:\.\d+)?)(?:([+-]\d+(?:\.\d+)?))?/?")

# GPS e datas dentro de blocos XMP (usados por editores de imagem).
RE_XMP_GPS_LAT = re.compile(r'<exif:GPSLatitude[^>]*>([^<]+)</exif:GPSLatitude>')
RE_XMP_GPS_LON = re.compile(r'<exif:GPSLongitude[^>]*>([^<]+)</exif:GPSLongitude>')
RE_XMP_GPS_LAT_ATTR = re.compile(r'exif:GPSLatitude="([^"]+)"')
RE_XMP_GPS_LON_ATTR = re.compile(r'exif:GPSLongitude="([^"]+)"')
RE_XMP_DATA = re.compile(
    r'<(?:xmp:CreateDate|photoshop:DateCreated|exif:DateTimeOriginal)[^>]*>([^<]+)</'
    r'(?:xmp:CreateDate|photoshop:DateCreated|exif:DateTimeOriginal)>'
)
RE_XMP_DATA_ATTR = re.compile(
    r'(?:xmp:CreateDate|photoshop:DateCreated|exif:DateTimeOriginal)="([^"]+)"'
)

# Chaves de texto PNG que costumam guardar datas (tEXt/iTXt).
PNG_CHAVES_DATA = {"creation time", "creationtime", "date:create", "date:modify"}

# Nomes de campos de data que o exiftool imprime com a opção -G (grupos).
CHAVES_DATA_EXIFTOOL = (
    "EXIF:DateTimeOriginal", "EXIF:CreateDate", "EXIF:ModifyDate",
    "QuickTime:CreateDate", "QuickTime:CreationDate", "XMP:CreateDate",
    "PNG:CreationTime", "IPTC:DateCreated",
    "ID3:RecordingTime", "ID3:OriginalReleaseTime", "ID3:ReleaseTime",
)


def registrar_heif() -> bool:
    """Registra o opener de HEIC/HEIF no Pillow; retorna True se funcionou."""
    try:
        pillow_heif.register_heif_opener()
        return True
    except Exception:
        return False


def parsear_data_iso(texto: object, ano_minimo: int = ANO_MINIMO_PADRAO) -> datetime | None:
    """Parseia datas ISO/EXIF flexíveis (com ou sem hora, ignora fuso/fração).

    Ex.: "2021-06-15T12:34:56Z", "2021-06-15T12:34:56-03:00",
    "2021:06:15 12:34:56", "2021-06-15T12:34:56.123", "2021-03-15".
    """
    s = re.sub(r"\s+", " ", str(texto).strip())
    m = RE_DATA_ISO.match(s)
    if not m:
        return None
    return montar_dt(m.group(1), m.group(2), m.group(3),
                     m.group(4) or 0, m.group(5) or 0, m.group(6) or 0,
                     ano_minimo=ano_minimo)


def _parsear_data_tag(valor: object, ano_minimo: int = ANO_MINIMO_PADRAO) -> datetime | None:
    """Parseia valores de tags de mídia; aceita também ano isolado ("2021")."""
    texto = _valor_tag(valor).strip()
    dt = parsear_data_iso(texto, ano_minimo)
    if dt is None and RE_ANO_ISOLADO.fullmatch(texto):
        dt = montar_dt(texto, 1, 1, ano_minimo=ano_minimo)
    return dt


def racional_para_float(valor: object) -> float | None:
    """Converte valores racionais (tupla num/den, IFDRational, Ratio, str 'n/d') em float."""
    if isinstance(valor, (tuple, list)) and len(valor) == 2:
        a, b = valor
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            try:
                return float(a) / float(b)
            except ZeroDivisionError:
                return None
    if hasattr(valor, "num") and hasattr(valor, "den"):
        try:
            return float(valor.num) / float(valor.den)
        except (ZeroDivisionError, TypeError, ValueError):
            return None
    if isinstance(valor, str) and "/" in valor:
        num, den = valor.split("/", 1)
        try:
            return float(num) / float(den)
        except (ValueError, ZeroDivisionError):
            return None
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def normalizar_ref(valor: object) -> str:
    """Normaliza a referência (N/S/E/W), aceitando bytes do piexif ("b'S'")."""
    s = str(valor).strip().upper()
    if len(s) >= 3 and s.startswith("B'") and s.endswith("'"):
        s = s[2:-1]
    return s


def gms_para_decimal(partes: object, ref: object) -> float | None:
    """Converte graus/minutos/segundos (ou graus/minutos) para decimal."""
    if not isinstance(partes, (list, tuple)) or len(partes) < 2:
        return None
    valores = [racional_para_float(p) for p in partes[:3]]
    if any(v is None for v in valores):
        return None
    dec = valores[0] + valores[1] / 60.0 + (valores[2] if len(valores) > 2 else 0.0) / 3600.0
    if normalizar_ref(ref) in ("S", "W"):
        dec = -dec
    return dec


def validar_coordenada(lat: float | None, lon: float | None) -> tuple[float, float] | None:
    """Valida latitude/longitude; (0, 0) é tratado como ausente."""
    if lat is None or lon is None:
        return None
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return None
    if lat == 0.0 and lon == 0.0:
        return None
    return lat, lon


def parsear_iso6709(texto: object) -> tuple[float, float] | None:
    """Parseia coordenadas ISO 6709 (padrão ©xyz do QuickTime).

    Formatos aceitos: "+23.5500-046.6333+000/", "-23.55-046.63/", "+23.5500-046.6333/".
    Retorna (lat, lon) ou None (0,0 é tratado como ausente).
    """
    m = RE_ISO6709.search(str(texto).strip())
    if not m:
        return None
    try:
        lat = float(m.group(1))
        lon = float(m.group(2))
    except ValueError:
        return None
    return validar_coordenada(lat, lon)


def datas_exif(exif, ano_minimo: int = ANO_MINIMO_PADRAO) -> list[datetime]:
    """Datas de um objeto Exif do Pillow, do IFD0 E do sub-IFD EXIF (0x8769).

    Por que os dois? O padrão EXIF guarda a data de CAPTURA
    (36867 DateTimeOriginal) e a de digitalização (36868) dentro do
    sub-IFD 0x8769; só a tag 306 (DateTime, última alteração) fica no
    IFD0. ``Image.getexif()`` devolve apenas o IFD0 — quem lê só ele
    perde a data de captura e acaba usando a data de edição ou a do
    sistema de arquivos.
    """
    datas: list[datetime] = []
    if exif is None:
        return datas
    # Fontes na ordem de confiança: sub-IFD (captura) e depois IFD0 (edição).
    try:
        sub_ifd = exif.get_ifd(IFD_EXIF) or {}
    except Exception:
        sub_ifd = {}
    fontes = (
        (sub_ifd, (TAG_DATETIME_ORIGINAL, TAG_CREATE_DATE)),
        (exif, (TAG_DATETIME_ORIGINAL, TAG_CREATE_DATE, TAG_MODIFY_DATE)),
    )
    for origem, tags in fontes:
        for tag in tags:
            try:
                valor = origem.get(tag)
            except Exception:
                continue
            if not valor:
                continue
            dt = parsear_data_exif(valor, ano_minimo)
            if dt and dt not in datas:
                datas.append(dt)
    return datas


def ler_gps_exif(exif) -> tuple[float, float] | None:
    """GPS do IFD GPS (0x8825) de um objeto Exif do Pillow.

    Dentro do IFD GPS, as tags 2 e 4 são latitude/longitude em graus,
    minutos e segundos, e as tags 1 e 3 são as referências N/S e E/W.
    """
    try:
        ifd = exif.get_ifd(IFD_GPS)
        if not ifd:
            return None
        return validar_coordenada(
            gms_para_decimal(ifd.get(2), ifd.get(1)),
            gms_para_decimal(ifd.get(4), ifd.get(3)),
        )
    except Exception:
        return None


def ler_gps_piexif(caminho: str | Path) -> tuple[float, float] | None:
    """GPS lido com piexif (leitura direta das seções EXIF)."""
    try:
        dados = piexif.load(str(caminho))
    except Exception:
        return None
    gps = dados.get("GPS") or {}
    if not gps:
        return None
    return validar_coordenada(
        gms_para_decimal(gps.get(2), gps.get(1, b"N")),
        gms_para_decimal(gps.get(4), gps.get(3, b"E")),
    )


def _partes_exifread(valor: object) -> list | None:
    if valor is None:
        return None
    if isinstance(valor, (list, tuple)):
        return list(valor)
    s = str(valor).strip().strip("[]()")
    if not s:
        return None
    return [tok.strip() for tok in s.split(",") if tok.strip()]


def ler_gps_exifread(caminho: str | Path) -> tuple[float, float] | None:
    """GPS lido com exifread (tags 'GPS GPSLatitude' etc.)."""
    try:
        with open(caminho, "rb") as f:
            tags = exifread.process_file(f, details=True)
    except Exception:
        return None
    lat = _partes_exifread(tags.get("GPS GPSLatitude"))
    lon = _partes_exifread(tags.get("GPS GPSLongitude"))
    if not lat or not lon:
        return None
    return validar_coordenada(
        gms_para_decimal(lat, str(tags.get("GPS GPSLatitudeRef", "N"))),
        gms_para_decimal(lon, str(tags.get("GPS GPSLongitudeRef", "E"))),
    )


def obter_gps(
    caminho: str | Path, exif: object = None,
) -> tuple[float, float] | None:
    """Obtém (lat, lon) tentando Pillow -> piexif -> exifread, na primeira que funcionar."""
    if exif is not None:
        gps = ler_gps_exif(exif)
        if gps:
            return gps
    else:
        try:
            with Image.open(caminho) as img:
                gps = ler_gps_exif(img.getexif())
        except Exception:
            gps = None
        if gps:
            return gps
    gps = ler_gps_piexif(caminho)
    if gps:
        return gps
    return ler_gps_exifread(caminho)


def _decimal_xmp(valor: object) -> float | None:
    """Converte latitude/longitude XMP ("23,33.5S" ou "23.55833S") para decimal."""
    s = str(valor).strip().upper()
    m = re.match(
        r"^([0-9]+(?:[.,][0-9]+)?)(?:,([0-9]+(?:[.,][0-9]+)?))?"
        r"(?:,([0-9]+(?:[.,][0-9]+)?))?\s*([NSEW])$", s,
    )
    if not m:
        return None
    gr = float(m.group(1).replace(",", "."))
    mi = float(m.group(2).replace(",", ".")) if m.group(2) else 0.0
    se = float(m.group(3).replace(",", ".")) if m.group(3) else 0.0
    dec = gr + mi / 60.0 + se / 3600.0
    if m.group(4) in ("S", "W"):
        dec = -dec
    return dec


def _xmp_como_dict(img):
    try:
        xmp = img.getxmp()
    except Exception:
        return None
    return xmp or None


def _descriptions_xmp(xmp_dict) -> list[dict]:
    try:
        rdf = (xmp_dict.get("xmpmeta", xmp_dict) or {}).get("RDF", {})
    except AttributeError:
        return []
    descs = rdf.get("Description", [])
    if isinstance(descs, dict):
        descs = [descs]
    return [d for d in descs if isinstance(d, dict)]


def gps_xmp(img) -> tuple[float, float] | None:
    """GPS lido do bloco XMP (comum em PNGs e em arquivos processados por editores)."""
    xmp = _xmp_como_dict(img)
    if not xmp:
        return None
    if isinstance(xmp, dict):
        for desc in _descriptions_xmp(xmp):
            lat = _decimal_xmp(desc.get("GPSLatitude"))
            lon = _decimal_xmp(desc.get("GPSLongitude"))
            if lat is not None and lon is not None:
                return lat, lon
        return None
    lat = RE_XMP_GPS_LAT.search(xmp) or RE_XMP_GPS_LAT_ATTR.search(xmp)
    lon = RE_XMP_GPS_LON.search(xmp) or RE_XMP_GPS_LON_ATTR.search(xmp)
    if not lat or not lon:
        return None
    return validar_coordenada(_decimal_xmp(lat.group(1)), _decimal_xmp(lon.group(1)))


def datas_xmp(img, ano_minimo: int = ANO_MINIMO_PADRAO) -> list[datetime]:
    """Datas do bloco XMP (CreateDate, DateCreated, DateTimeOriginal)."""
    xmp = _xmp_como_dict(img)
    if not xmp:
        return []
    if isinstance(xmp, dict):
        datas = []
        for desc in _descriptions_xmp(xmp):
            for chave in ("DateTimeOriginal", "CreateDate", "DateCreated"):
                valor = desc.get(chave)
                if not valor:
                    continue
                if isinstance(valor, list):
                    valor = valor[0] if valor else None
                if not valor:
                    continue
                dt = parsear_data_iso(valor, ano_minimo)
                if dt:
                    datas.append(dt)
        return datas
    datas = []
    for m in RE_XMP_DATA.finditer(xmp):
        dt = parsear_data_iso(m.group(1), ano_minimo)
        if dt:
            datas.append(dt)
    for m in RE_XMP_DATA_ATTR.finditer(xmp):
        dt = parsear_data_iso(m.group(1), ano_minimo)
        if dt:
            datas.append(dt)
    return datas


def datas_png_text(img, ano_minimo: int = ANO_MINIMO_PADRAO) -> list[datetime]:
    """Datas dos metadados de texto PNG (tEXt/iTXt: "Creation Time", "date:create"...)."""
    try:
        texto = img.text or {}
    except Exception:
        return []
    datas = []
    for chave, valor in texto.items():
        if str(chave).strip().lower() not in PNG_CHAVES_DATA:
            continue
        dt = parsear_data_iso(valor, ano_minimo)
        if dt is None:
            try:
                dt = datetime.strptime(str(valor).strip(), "%a %b %d %H:%M:%S %Y")
                if not dentro_do_periodo(dt, ano_minimo):
                    dt = None
            except ValueError:
                dt = None
        if dt:
            datas.append(dt)
    return datas


def metadados_imagem(
    caminho: str | Path,
) -> tuple[list[datetime] | None, tuple[float, float] | None]:
    """Retorna (datas, gps) lidos dos metadados da imagem (EXIF, XMP, PNG e fallbacks)."""
    datas: list[datetime] = []
    gps = None
    try:
        with Image.open(caminho) as img:
            exif = img.getexif()
            datas.extend(datas_exif(exif))
            gps = ler_gps_exif(exif)
            if gps is None:
                gps = gps_xmp(img)
            datas.extend(datas_xmp(img))
            if img.format == "PNG":
                datas.extend(datas_png_text(img))
    except Exception as e:
        logger.debug("Falha ao ler metadados da imagem %s: %s", caminho, e)
    if gps is None:
        gps = ler_gps_piexif(caminho) or ler_gps_exifread(caminho)
    return (datas or None), gps


def _tags_mp4(arquivo: MP4) -> tuple[list[datetime], tuple[float, float] | None]:
    """Datas (©day/©date) e GPS (©xyz, ISO 6709) das tags MP4/M4A/MOV."""
    datas: list[datetime] = []
    gps = None
    tags = getattr(arquivo, "tags", None)
    if not tags:
        return datas, gps
    for chave in ("©day", "©date"):
        for valor in tags.get(chave, []):
            dt = _parsear_data_tag(valor)
            if dt:
                datas.append(dt)
    for valor in tags.get("©xyz", []):
        gps = parsear_iso6709(valor)
        if gps:
            break
    return datas, gps


def _tags_id3(tags: ID3) -> list[datetime]:
    """Datas de quadros ID3 (TDRC: recording time; TDOR; TYER)."""
    datas = []
    for nome in ("TDRC", "TDOR", "TYER"):
        for quadro in tags.getall(nome):
            valor = quadro.text
            if isinstance(valor, (list, tuple)):
                valor = valor[0] if valor else None
            dt = _parsear_data_tag(valor)
            if dt:
                datas.append(dt)
    return datas


def _tags_vorbis(tags) -> list[datetime]:
    """Datas de comentários Vorbis (OGG/Opus/FLAC: DATE, ORIGINALDATE, YEAR).

    Aceita dict e DictProxy do mutagen (VCommentDict/VCFLACDict).
    """
    datas = []
    for chave in ("date", "originaldate", "year"):
        for valor in tags.get(chave, []):
            dt = _parsear_data_tag(valor)
            if dt:
                datas.append(dt)
    return datas


def _valor_tag(valor: object) -> str:
    """Converte o valor bruto de uma tag de mídia em texto."""
    if isinstance(valor, (bytes, bytearray)):
        return bytes(valor).decode("utf-8", "replace")
    return str(valor)


def metadados_audio(
    caminho: str | Path,
) -> tuple[list[datetime] | None, tuple[float, float] | None]:
    """Retorna (datas, gps) lidos dos metadados de áudio (mutagen).

    - MP3 (ID3): TDRC (recording time), TDOR, TYER.
    - MP4/M4A: ©day, ©xyz (GPS em ISO 6709).
    - OGG/Opus/FLAC: comentários Vorbis DATE, ORIGINALDATE, YEAR.
    """
    try:
        arquivo = mutagen.File(str(caminho))
    except Exception as e:
        logger.debug("Falha ao ler áudio %s com mutagen: %s", caminho, e)
        return None, None
    if arquivo is None:
        return None, None
    tags = getattr(arquivo, "tags", None)
    datas: list[datetime] = []
    gps = None
    if isinstance(arquivo, MP4):
        datas, gps = _tags_mp4(arquivo)
    elif isinstance(tags, ID3):
        datas = _tags_id3(tags)
    elif hasattr(tags, "get"):
        datas = _tags_vorbis(tags)
    return (datas or None), gps


def metadados_video(
    caminho: str | Path,
) -> tuple[datetime | None, tuple[float, float] | None]:
    """Retorna (data_criacao, gps) lidos dos metadados do vídeo.

    - Data: creation_time do container (ffmpeg); fallback: ©day das tags MP4.
    - GPS: localização ISO 6709 (location / ©xyz do QuickTime).
    """
    dt, gps = None, None
    if FFMPEG_EXE:
        try:
            r = subprocess.run(
                [FFMPEG_EXE, "-hide_banner", "-i", str(caminho), "-f", "null", "-"],
                capture_output=True, text=True, timeout=180,
            )
            stderr = r.stderr or ""
            m = RE_CREATION_TIME.search(stderr)
            if m:
                dt = montar_dt(m.group(1)[:4], m.group(1)[5:7], m.group(1)[8:10],
                               m.group(2)[:2], m.group(2)[3:5], m.group(2)[6:8])
            m = RE_LOCATION_FFMPEG.search(stderr)
            if m:
                gps = parsear_iso6709(m.group(1))
        except (OSError, subprocess.TimeoutExpired) as e:
            logger.debug("Falha ao ler vídeo %s com ffmpeg: %s", caminho, e)
    if dt is None or gps is None:
        try:
            datas_mp4, gps_mp4 = _tags_mp4(MP4(str(caminho)))
        except Exception as e:
            logger.debug("Falha ao ler vídeo %s com mutagen: %s", caminho, e)
            datas_mp4, gps_mp4 = [], None
        dt = dt or (datas_mp4[0] if datas_mp4 else None)
        gps = gps or gps_mp4
    return dt, gps


def metadados_exiftool(
    caminho: str | Path,
) -> tuple[list[datetime] | None, tuple[float, float] | None]:
    """Fallback opcional: lê datas e GPS com o binário exiftool, se instalado.

    exiftool (Phil Harvey) é o padrão de referência em perícia forense;
    usado aqui apenas quando Pillow/ffmpeg/mutagen não encontraram nada.
    """
    if not EXIFTOOL_EXE:
        return None, None
    try:
        r = subprocess.run(
            [EXIFTOOL_EXE, "-j", "-G", "-n", str(caminho)],
            capture_output=True, text=True, timeout=60,
        )
        if r.returncode != 0:
            return None, None
        dados = json.loads(r.stdout or "")
    except (OSError, ValueError, json.JSONDecodeError):
        return None, None
    reg = dados[0] if isinstance(dados, list) and dados else {}
    datas = []
    for chave in CHAVES_DATA_EXIFTOOL:
        valor = reg.get(chave)
        if valor:
            dt = parsear_data_iso(valor)
            if dt:
                datas.append(dt)
    gps = None
    pos = reg.get("Composite:GPSPosition") or reg.get("EXIF:GPSPosition")
    if isinstance(pos, str):
        partes = pos.split()
        if len(partes) >= 2:
            try:
                gps = (float(partes[0]), float(partes[1]))
            except ValueError:
                gps = None
    if gps is None:
        try:
            lat = float(reg.get("EXIF:GPSLatitude", reg.get("XMP:GPSLatitude", 0)))
            lon = float(reg.get("EXIF:GPSLongitude", reg.get("XMP:GPSLongitude", 0)))
            if str(reg.get("EXIF:GPSLatitudeRef", "")).strip().upper() == "S":
                lat = -lat
            if str(reg.get("EXIF:GPSLongitudeRef", "")).strip().upper() == "W":
                lon = -lon
            gps = validar_coordenada(lat, lon)
        except (TypeError, ValueError):
            gps = None
    return (datas or None), gps


def data_filesystem(
    caminho: str | Path, ano_minimo: int = ANO_MINIMO_PADRAO,
) -> datetime | None:
    """Última alternativa: data do sistema de arquivos (min entre criação/modificação)."""
    try:
        st = Path(caminho).stat()
        timestamps = [t for t in (st.st_ctime, st.st_mtime) if t]
        if not timestamps:
            return None
        dt = datetime.fromtimestamp(min(timestamps))
    except (OSError, ValueError, OverflowError):
        return None
    return dt if dentro_do_periodo(dt, ano_minimo) else None


def classificar_tipo(caminho: str | Path) -> str:
    """Classifica o arquivo pela extensão: imagem, video, audio, office, outro ou desconhecido."""
    ext = Path(caminho).suffix.lower()
    if ext in EXTS_IMAGEM:
        return "imagem"
    if ext in EXTS_VIDEO:
        return "video"
    if ext in EXTS_AUDIO:
        return "audio"
    if ext in EXTS_OFFICE:
        return "office"
    if ext in EXTS_OUTROS:
        return "outro"
    return "desconhecido"


@dataclass(slots=True)
class Metadados:
    """Metadados extraídos de um arquivo de mídia."""

    caminho: Path
    tipo: str
    datas: list[datetime] = field(default_factory=list)
    gps: tuple[float, float] | None = None

    def data_mais_antiga(self) -> datetime | None:
        """Data mais antiga entre as encontradas (ou None)."""
        return min(self.datas) if self.datas else None

    def data_mais_recente(self) -> datetime | None:
        """Data mais recente entre as encontradas (ou None)."""
        return max(self.datas) if self.datas else None


def _datas_como_lista(resultado: object) -> list[datetime]:
    if resultado is None:
        return []
    if isinstance(resultado, datetime):
        return [resultado]
    return [d for d in resultado if isinstance(d, datetime)]


def extrair_metadados(
    caminho: str | Path,
    *,
    ano_minimo: int = ANO_MINIMO_PADRAO,
    usar_exiftool: bool = True,
    usar_filesystem: bool = True,
) -> Metadados:
    """Extrai datas e GPS de um arquivo de foto, vídeo ou áudio.

    Ordem das fontes: metadados embutidos (Pillow/ffmpeg/mutagen),
    exiftool (opcional) e, por fim, o sistema de arquivos. Datas fora do
    período válido (ano_minimo..hoje) são descartadas.
    """
    caminho = Path(caminho)
    tipo = classificar_tipo(caminho)
    gps = None
    if tipo == "imagem":
        datas, gps = metadados_imagem(caminho)
    elif tipo == "video":
        dt_video, gps = metadados_video(caminho)
        datas = [dt_video] if dt_video else []
    elif tipo == "audio":
        datas, gps = metadados_audio(caminho)
    else:
        datas = None
    datas = _datas_como_lista(datas)
    if usar_exiftool and (not datas or gps is None):
        datas_ex, gps_ex = metadados_exiftool(caminho)
        if not datas:
            datas = _datas_como_lista(datas_ex)
        gps = gps or gps_ex
    datas = [d for d in datas if dentro_do_periodo(d, ano_minimo)]
    datas.sort()
    if not datas and usar_filesystem:
        dt_fs = data_filesystem(caminho, ano_minimo)
        if dt_fs:
            datas = [dt_fs]
    return Metadados(caminho=caminho, tipo=tipo, datas=datas, gps=gps)


def classificar_sufixo(
    caminho: str | Path,
    *,
    tamanho: int | None = None,
    min_size_low_res: int = 100000,
) -> str | None:
    """Classifica o sufixo de pasta pela extensão, nome e tamanho.

    Ex.: "video.mp4" -> "videos"; "Screenshot_1.jpg" -> "screen_capture";
    arquivos pequenos -> "low_resolution". None = sem sufixo.
    """
    caminho = Path(caminho)
    nome = caminho.name.lower()
    ext = caminho.suffix.lower()
    if ext in EXTS_VIDEO:
        return "videos"
    if ext in EXTS_AUDIO:
        return "audios"
    if ext in EXTS_OFFICE:
        return "office"
    if ext in EXTS_OUTROS:
        return "outros_tipos"
    if any(k in nome for k in ("screenshot", "screen", "capture")):
        return "screen_capture"
    if any(k in nome for k in ("insta", "facebook", "tiktok", "twitter", "social")):
        return "social_media"
    if any(k in nome for k in ("whats", "telegram", "message", "instant", "img-", "wa0")):
        return "instant_messages"
    if tamanho is not None and min_size_low_res > 0 and tamanho < min_size_low_res:
        return "low_resolution"
    return None


def obter_datas(
    caminho: str | Path,
    ano_minimo: int = ANO_MINIMO_PADRAO,
) -> tuple[datetime | None, datetime | None, tuple[float, float] | None]:
    """Coleta (data_min, data_max, gps) de um arquivo por TODAS as fontes.

    Ordem de prioridade das fontes:

    1. Metadados embutidos (imagens: EXIF/XMP/PNG; vídeos: ffmpeg/mutagen;
       áudios: ID3/©day/Vorbis), com fallback exiftool opcional.
    2. Nome do arquivo (extrair_data_nome, do módulo de nomeação).
    3. Sistema de arquivos (data_filesystem) — última alternativa.

    data_min e data_max podem ser iguais (uma única data encontrada) ou
    None (nenhuma data válida para o ano_minimo informado).
    """
    caminho = Path(caminho)
    fontes: list[tuple[str, datetime]] = []
    gps = None
    tipo = classificar_tipo(caminho)
    if tipo == "imagem":
        datas_meta, gps = metadados_imagem(caminho)
        if not datas_meta and gps is None:
            datas_meta, gps = metadados_exiftool(caminho)
    elif tipo == "video":
        dt_video, gps = metadados_video(caminho)
        datas_meta = [dt_video] if dt_video else None
        if dt_video is None and gps is None:
            datas_meta, gps = metadados_exiftool(caminho)
    elif tipo == "audio":
        datas_meta, gps = metadados_audio(caminho)
        if not datas_meta and gps is None:
            datas_meta, gps = metadados_exiftool(caminho)
    else:
        datas_meta = None
    if datas_meta:
        validas = [d for d in datas_meta if dentro_do_periodo(d, ano_minimo)]
        if validas:
            fontes.append(("metadados", min(validas)))
    dt_nome = extrair_data_nome(caminho.stem, ano_minimo)
    if dt_nome:
        fontes.append(("nome", dt_nome))
    if not fontes:
        dt_fs = data_filesystem(caminho, ano_minimo)
        if dt_fs:
            fontes.append(("sistema", dt_fs))
    if not fontes:
        return None, None, gps
    datas = [dt for _, dt in fontes]
    return min(datas), max(datas), gps


__all__ = [
    "ALL_EXTENSIONS",
    "ANO_MINIMO_PADRAO",
    "EXTS_AUDIO",
    "EXTS_IMAGEM",
    "EXTS_OFFICE",
    "EXTS_OUTROS",
    "EXTS_VIDEO",
    "Metadados",
    "classificar_sufixo",
    "classificar_tipo",
    "data_filesystem",
    "datas_exif",
    "dentro_do_periodo",
    "extrair_metadados",
    "gms_para_decimal",
    "ler_gps_exif",
    "ler_gps_exifread",
    "ler_gps_piexif",
    "metadados_audio",
    "metadados_exiftool",
    "metadados_imagem",
    "metadados_video",
    "montar_dt",
    "normalizar_ref",
    "obter_datas",
    "obter_gps",
    "parsear_data_exif",
    "parsear_data_iso",
    "parsear_iso6709",
    "racional_para_float",
    "registrar_heif",
    "validar_coordenada",
]
