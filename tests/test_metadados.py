#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Testes da extração de metadados de fotos, vídeos e áudios."""

import json
import subprocess
from datetime import datetime

import pytest
from PIL import Image

import pereiras_common.metadados as mod
from pereiras_common.metadados import (
    ALL_EXTENSIONS,
    EXTS_AUDIO,
    EXTS_IMAGEM,
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
    normalizar_ref,
    parsear_data_iso,
    parsear_iso6709,
    racional_para_float,
    validar_coordenada,
)


def _ffmpeg():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def _criar_imagem_com_exif(caminho, datetime_original="2021:03:15 10:20:30", gps=None):
    img = Image.new("RGB", (64, 64), (255, 0, 0))
    exif = Image.Exif()
    exif[36867] = datetime_original
    if gps:
        ifd = exif.get_ifd(0x8825)
        ifd[1] = gps["lat_ref"]
        ifd[2] = gps["lat"]
        ifd[3] = gps["lon_ref"]
        ifd[4] = gps["lon"]
        exif[0x8825] = ifd
    img.save(caminho, exif=exif)


# ---------------------------------------------------------------- extensões

def test_extensoes_suportadas():
    assert ".jpg" in EXTS_IMAGEM
    assert ".heic" in EXTS_IMAGEM
    assert ".mp4" in EXTS_VIDEO
    assert ".mp3" in EXTS_AUDIO
    assert ".flac" in EXTS_AUDIO
    assert ".m4a" in EXTS_AUDIO
    assert ".pdf" in mod.EXTS_OUTROS
    assert EXTS_IMAGEM | EXTS_VIDEO | EXTS_AUDIO <= ALL_EXTENSIONS


@pytest.mark.parametrize("ext,esperado", [
    (".jpg", "imagem"), (".heic", "imagem"),
    (".mp4", "video"), (".mkv", "video"),
    (".mp3", "audio"), (".opus", "audio"),
    (".docx", "office"), (".pdf", "outro"),
    (".xyz", "desconhecido"),
])
def test_classificar_tipo(ext, esperado):
    assert classificar_tipo(f"arquivo{ext}") == esperado


# -------------------------------------------------------------------- datas

@pytest.mark.parametrize("texto,esperado", [
    ("2021-06-15T12:34:56Z", datetime(2021, 6, 15, 12, 34, 56)),
    ("2021-06-15T12:34:56-03:00", datetime(2021, 6, 15, 12, 34, 56)),
    ("2021:06:15 12:34:56", datetime(2021, 6, 15, 12, 34, 56)),
    ("2021-06-15T12:34:56.123", datetime(2021, 6, 15, 12, 34, 56)),
    ("2021-03-15", datetime(2021, 3, 15)),
    ("2021-03-15T12:34:56.123+02:00", datetime(2021, 3, 15, 12, 34, 56)),
    ("sem data", None),
    ("1900-01-01", None),
])
def test_parsear_data_iso(texto, esperado):
    assert parsear_data_iso(texto) == esperado


def test_parsear_data_iso_ano_minimo():
    assert parsear_data_iso("2005-01-01", ano_minimo=2010) is None
    assert parsear_data_iso("2005-01-01", ano_minimo=2000) == datetime(2005, 1, 1)


# ---------------------------------------------------------------------- GPS

def test_gms_para_decimal():
    assert gms_para_decimal((23, 33, 0), "S") == pytest.approx(-23.55)
    assert gms_para_decimal((46, 38, 0), "W") == pytest.approx(-46.63333333)
    assert gms_para_decimal((0, 0), "N") == 0.0
    assert gms_para_decimal(("a", "b"), "N") is None
    assert gms_para_decimal((23.5, 0), "N") == pytest.approx(23.5)


def test_gms_para_decimal_racionais():
    assert gms_para_decimal(((23, 1), (33, 1), (0, 1)), "S") == pytest.approx(-23.55)
    assert gms_para_decimal(("23/1", "33/1", "0/1"), "S") == pytest.approx(-23.55)
    assert gms_para_decimal(((23, 1), (33, 1), (0, 1)), b"S") == pytest.approx(-23.55)


def test_racional_para_float():
    assert racional_para_float((1, 2)) == 0.5
    assert racional_para_float("1/2") == 0.5
    assert racional_para_float(2.5) == 2.5
    assert racional_para_float((1, 0)) is None
    assert racional_para_float("abc") is None


def test_normalizar_ref():
    assert normalizar_ref("S") == "S"
    assert normalizar_ref(b"S") == "S"
    assert normalizar_ref(" s ") == "S"


def test_validar_coordenada():
    assert validar_coordenada(23.55, -46.63) == (23.55, -46.63)
    assert validar_coordenada(0.0, 0.0) is None
    assert validar_coordenada(91.0, 0.0) is None
    assert validar_coordenada(None, 10.0) is None


@pytest.mark.parametrize("texto,esperado", [
    ("+23.5500-046.6333+000/", (23.55, -46.6333)),
    ("+23.5500-046.6333/", (23.55, -46.6333)),
    ("-23.55-046.63/", (-23.55, -46.63)),
    ("+40.7486-073.9864+033.7/", (40.7486, -73.9864)),
    ("+00.0000+000.0000+000/", None),
    ("sem localizacao", None),
])
def test_parsear_iso6709(texto, esperado):
    if esperado is None:
        assert parsear_iso6709(texto) is None
    else:
        lat, lon = parsear_iso6709(texto)
        assert lat == pytest.approx(esperado[0])
        assert lon == pytest.approx(esperado[1])


# ---------------------------------------------------------------- imagens

def test_metadados_imagem_sem_exif(tmp_path):
    caminho = tmp_path / "sem_exif.jpg"
    Image.new("RGB", (32, 32), (0, 255, 0)).save(caminho)
    datas, gps = metadados_imagem(caminho)
    assert datas is None
    assert gps is None


def test_metadados_imagem_com_exif(tmp_path):
    caminho = tmp_path / "com_exif.jpg"
    _criar_imagem_com_exif(caminho)
    datas, gps = metadados_imagem(caminho)
    assert datas is not None
    assert min(datas) == datetime(2021, 3, 15, 10, 20, 30)
    assert gps is None


def test_metadados_imagem_com_gps(tmp_path):
    caminho = tmp_path / "com_gps.jpg"
    _criar_imagem_com_exif(caminho, gps={
        "lat_ref": "S", "lat": (23.0, 33.0, 0.0),
        "lon_ref": "W", "lon": (46.0, 38.0, 0.0),
    })
    datas, gps = metadados_imagem(caminho)
    assert gps is not None
    lat, lon = gps
    assert lat == pytest.approx(-23.55, abs=1e-6)
    assert lon == pytest.approx(-46.6333333, abs=1e-6)


def test_ler_gps_exif_sem_gps(tmp_path):
    caminho = tmp_path / "sem_gps.jpg"
    _criar_imagem_com_exif(caminho)
    with Image.open(caminho) as img:
        assert ler_gps_exif(img.getexif()) is None


_XMP_GPS = (
    '<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>'
    '<x:xmpmeta xmlns:x="adobe:ns:meta/">'
    '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
    '<rdf:Description xmlns:exif="http://ns.adobe.com/exif/1.0/" '
    'exif:GPSLatitude="23,33.5S" exif:GPSLongitude="46,38.5W" '
    'exif:DateTimeOriginal="2020:01:02 03:04:05"/>'
    '</rdf:RDF></x:xmpmeta>'
)


def test_metadados_imagem_gps_e_data_xmp(tmp_path):
    caminho = tmp_path / "com_xmp.jpg"
    img = Image.new("RGB", (32, 32), (0, 0, 255))
    img.save(caminho, xmp=_XMP_GPS.encode("utf-8"))
    datas, gps = metadados_imagem(caminho)
    assert gps is not None
    lat, lon = gps
    assert lat == pytest.approx(-23.5583333, abs=1e-6)
    assert lon == pytest.approx(-46.6416667, abs=1e-6)
    assert datetime(2020, 1, 2, 3, 4, 5) in datas


def test_metadados_imagem_png_text_date(tmp_path):
    from PIL import PngImagePlugin
    caminho = tmp_path / "captura.png"
    pnginfo = PngImagePlugin.PngInfo()
    pnginfo.add_text("Creation Time", "2021-06-15T12:34:56Z")
    pnginfo.add_text("Software", "Firefox")
    Image.new("RGB", (32, 32), (0, 0, 0)).save(caminho, pnginfo=pnginfo)
    datas, _ = metadados_imagem(caminho)
    assert datetime(2021, 6, 15, 12, 34, 56) in datas


# ------------------------------------------------------------------ vídeos

def test_metadados_video_sem_gps(tmp_path):
    ff = _ffmpeg()
    video = tmp_path / "sem_location.mp4"
    subprocess.run([ff, "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", "testsrc=size=64x64:rate=5", "-t", "1", str(video)],
                   check=True, capture_output=True)
    dt, gps = metadados_video(video)
    assert dt is None
    assert gps is None


def test_metadados_video_com_location(tmp_path):
    ff = _ffmpeg()
    video = tmp_path / "com_location.mp4"
    subprocess.run(
        [ff, "-y", "-loglevel", "error", "-f", "lavfi",
         "-i", "testsrc=size=64x64:rate=5", "-t", "1",
         "-metadata", "location=+23.5500-046.6333+000/",
         "-metadata", "creation_time=2021-06-15T12:34:56Z",
         "-movflags", "use_metadata_tags", str(video)],
        check=True, capture_output=True,
    )
    dt, gps = metadados_video(video)
    assert dt == datetime(2021, 6, 15, 12, 34, 56)
    assert gps is not None
    lat, lon = gps
    assert lat == pytest.approx(23.55)
    assert lon == pytest.approx(-46.6333)


def test_metadados_video_tags_mp4_sem_ffmpeg(tmp_path, monkeypatch):
    ff = _ffmpeg()
    video = tmp_path / "so_tags.mp4"
    subprocess.run([ff, "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", "testsrc=size=64x64:rate=5", "-t", "1", str(video)],
                   check=True, capture_output=True)
    from mutagen.mp4 import MP4
    mp4 = MP4(str(video))
    mp4.tags["\xa9day"] = ["2021-06-15"]
    mp4.tags["\xa9xyz"] = ["+23.5500-046.6333+000/"]
    mp4.save()
    monkeypatch.setattr(mod, "FFMPEG_EXE", None)
    dt, gps = metadados_video(video)
    assert dt == datetime(2021, 6, 15)
    assert gps is not None
    assert gps[0] == pytest.approx(23.55)
    assert gps[1] == pytest.approx(-46.6333)


# ------------------------------------------------------------------- áudio

def _criar_m4a(caminho):
    ff = _ffmpeg()
    subprocess.run([ff, "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", "sine=frequency=440:duration=1",
                    "-c:a", "aac", str(caminho)],
                   check=True, capture_output=True)


def test_metadados_audio_mp4(tmp_path):
    caminho = tmp_path / "gravacao.m4a"
    _criar_m4a(caminho)
    from mutagen.mp4 import MP4
    mp4 = MP4(str(caminho))
    mp4.tags["\xa9day"] = ["2021-06-15"]
    mp4.tags["\xa9xyz"] = ["+23.5500-046.6333+000/"]
    mp4.save()
    datas, gps = metadados_audio(caminho)
    assert datetime(2021, 6, 15) in datas
    assert gps is not None
    assert gps[0] == pytest.approx(23.55)
    assert gps[1] == pytest.approx(-46.6333)


def test_metadados_audio_mp3_id3(tmp_path):
    ff = _ffmpeg()
    caminho = tmp_path / "musica.mp3"
    r = subprocess.run(
        [ff, "-y", "-loglevel", "error", "-f", "lavfi",
         "-i", "sine=frequency=440:duration=1",
         "-c:a", "libmp3lame", "-write_id3v2", "1", "-id3v2_version", "4",
         "-metadata", "date=2021-06-15T12:34:56", str(caminho)],
        capture_output=True,
    )
    if r.returncode != 0:
        pytest.skip("ffmpeg sem suporte a MP3")
    datas, gps = metadados_audio(caminho)
    assert datas is not None
    assert datetime(2021, 6, 15, 12, 34, 56) in datas
    assert gps is None


def test_metadados_audio_flac(tmp_path):
    ff = _ffmpeg()
    caminho = tmp_path / "musica.flac"
    r = subprocess.run([ff, "-y", "-loglevel", "error", "-f", "lavfi",
                        "-i", "sine=frequency=440:duration=1",
                        "-c:a", "flac", "-metadata", "date=2021-03-15",
                        str(caminho)], capture_output=True)
    if r.returncode != 0:
        pytest.skip("ffmpeg sem suporte a FLAC")
    datas, gps = metadados_audio(caminho)
    assert datas is not None
    assert datetime(2021, 3, 15) in datas
    assert gps is None


def test_metadados_audio_sem_tags(tmp_path):
    caminho = tmp_path / "vazio.mp3"
    caminho.write_bytes(b"")
    assert metadados_audio(caminho) == (None, None)


# ---------------------------------------------------------------- exiftool

def test_metadados_exiftool_parse(tmp_path, monkeypatch):
    json_fake = json.dumps([{
        "SourceFile": "foto.jpg",
        "EXIF:DateTimeOriginal": "2021:03:15 10:20:30",
        "Composite:GPSPosition": "23.5500 -46.633333",
    }])
    monkeypatch.setattr(mod, "EXIFTOOL_EXE", "exiftool")
    monkeypatch.setattr(mod.subprocess, "run",
                        lambda *a, **k: subprocess.CompletedProcess(a[0], 0, stdout=json_fake))
    datas, gps = metadados_exiftool(tmp_path / "foto.jpg")
    assert min(datas) == datetime(2021, 3, 15, 10, 20, 30)
    lat, lon = gps
    assert lat == pytest.approx(23.55)
    assert lon == pytest.approx(-46.633333)


def test_metadados_exiftool_sem_binario(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "EXIFTOOL_EXE", None)
    assert metadados_exiftool(tmp_path / "foto.jpg") == (None, None)


# ------------------------------------------------------------ filesystem

def test_data_filesystem(tmp_path):
    caminho = tmp_path / "arquivo.txt"
    caminho.write_text("x", encoding="utf-8")
    dt = data_filesystem(caminho)
    assert dt is not None
    assert datetime(2020, 1, 1) <= dt <= datetime.now()


def test_data_filesystem_inexistente(tmp_path):
    assert data_filesystem(tmp_path / "nao_existe.txt") is None


# ------------------------------------------------------------- dispatcher

def test_extrair_metadados_imagem(tmp_path):
    caminho = tmp_path / "foto.jpg"
    _criar_imagem_com_exif(caminho)
    md = extrair_metadados(caminho)
    assert isinstance(md, Metadados)
    assert md.tipo == "imagem"
    assert md.data_mais_antiga() == datetime(2021, 3, 15, 10, 20, 30)
    assert md.data_mais_recente() == datetime(2021, 3, 15, 10, 20, 30)
    assert md.gps is None


def test_extrair_metadados_video(tmp_path):
    ff = _ffmpeg()
    video = tmp_path / "video.mp4"
    subprocess.run(
        [ff, "-y", "-loglevel", "error", "-f", "lavfi",
         "-i", "testsrc=size=64x64:rate=5", "-t", "1",
         "-metadata", "creation_time=2021-06-15T12:34:56Z",
         "-movflags", "use_metadata_tags", str(video)],
        check=True, capture_output=True,
    )
    md = extrair_metadados(video)
    assert md.tipo == "video"
    assert md.data_mais_antiga() == datetime(2021, 6, 15, 12, 34, 56)


def test_extrair_metadados_audio(tmp_path):
    caminho = tmp_path / "gravacao.m4a"
    _criar_m4a(caminho)
    from mutagen.mp4 import MP4
    mp4 = MP4(str(caminho))
    mp4.tags["\xa9day"] = ["2021-06-15"]
    mp4.save()
    md = extrair_metadados(caminho)
    assert md.tipo == "audio"
    assert md.data_mais_antiga() == datetime(2021, 6, 15)


def test_extrair_metadados_outro_usa_filesystem(tmp_path):
    caminho = tmp_path / "anotacoes.txt"
    caminho.write_text("texto", encoding="utf-8")
    md = extrair_metadados(caminho)
    assert md.tipo == "outro"
    assert md.datas


def test_extrair_metadados_sem_filesystem(tmp_path):
    caminho = tmp_path / "anotacoes.txt"
    caminho.write_text("texto", encoding="utf-8")
    md = extrair_metadados(caminho, usar_filesystem=False)
    assert md.datas == []
    assert md.data_mais_antiga() is None


# ----------------------------------------------------------- obter_datas

def test_obter_datas_imagem_exif(tmp_path):
    """A data do EXIF é a única fonte quando não há data no nome."""
    from pereiras_common.metadados import obter_datas
    caminho = tmp_path / "foto.jpg"
    _criar_imagem_com_exif(caminho)
    d_min, d_max, gps = obter_datas(caminho)
    assert d_min == d_max == datetime(2021, 3, 15, 10, 20, 30)
    assert gps is None


def test_obter_datas_exif_e_nome(tmp_path):
    """Nome e EXIF são combinados: data1 = menor, data2 = maior."""
    from pereiras_common.metadados import obter_datas
    caminho = tmp_path / "viagem_2019_07_04_08h09m10s.jpg"
    _criar_imagem_com_exif(caminho)
    d_min, d_max, _ = obter_datas(caminho)
    assert d_min == datetime(2019, 7, 4, 8, 9, 10)
    assert d_max == datetime(2021, 3, 15, 10, 20, 30)


def test_obter_datas_audio(tmp_path):
    """Áudio com tag ©day: a data vem dos metadados do áudio."""
    from mutagen.mp4 import MP4
    from pereiras_common.metadados import obter_datas
    caminho = tmp_path / "gravacao.m4a"
    _criar_m4a(caminho)
    mp4 = MP4(str(caminho))
    mp4.tags["\xa9day"] = ["2021-06-15"]
    mp4.save()
    d_min, d_max, gps = obter_datas(caminho)
    assert d_min == d_max == datetime(2021, 6, 15)
    assert gps is None


def test_obter_datas_video(tmp_path):
    """Vídeo com creation_time: a data vem do container."""
    from pereiras_common.metadados import obter_datas
    ff = _ffmpeg()
    video = tmp_path / "video.mp4"
    subprocess.run(
        [ff, "-y", "-loglevel", "error", "-f", "lavfi",
         "-i", "testsrc=size=64x64:rate=5", "-t", "1",
         "-metadata", "creation_time=2021-06-15T12:34:56Z",
         "-movflags", "use_metadata_tags", str(video)],
        check=True, capture_output=True,
    )
    d_min, d_max, _ = obter_datas(video)
    assert d_min == d_max == datetime(2021, 6, 15, 12, 34, 56)


def test_obter_datas_outro_usa_filesystem(tmp_path):
    """Arquivos sem metadados e sem data no nome usam o sistema de arquivos."""
    from pereiras_common.metadados import obter_datas
    caminho = tmp_path / "anotacoes.txt"
    caminho.write_text("x", encoding="utf-8")
    d_min, d_max, _ = obter_datas(caminho)
    assert d_min == d_max
    assert datetime(2020, 1, 1) <= d_min <= datetime.now()


def test_obter_datas_sem_nenhuma_fonte(tmp_path, monkeypatch):
    """Sem metadados, sem nome, sem filesystem: (None, None, None)."""
    from pereiras_common.metadados import obter_datas
    caminho = tmp_path / "foto.jpg"
    _criar_imagem_com_exif(caminho, datetime_original="1950:01:01 00:00:00")
    monkeypatch.setattr(mod, "data_filesystem", lambda caminho, ano_minimo=1980: None)
    d_min, d_max, gps = obter_datas(caminho, ano_minimo=1980)
    assert d_min is None and d_max is None
    assert gps is None


# ------------------------------------------------------- classificar_sufixo

@pytest.mark.parametrize("nome,ext,tamanho,min_size,esperado", [
    ("video.mp4", ".mp4", 10 ** 8, 100000, "videos"),
    ("audio.mp3", ".mp3", 10 ** 8, 100000, "audios"),
    ("doc.pdf", ".pdf", 10 ** 8, 100000, "outros_tipos"),
    ("Screenshot_1.jpg", ".jpg", 10 ** 6, 100000, "screen_capture"),
    ("insta_post.jpg", ".jpg", 10 ** 6, 100000, "social_media"),
    ("IMG-20190315-WA0000.jpg", ".jpg", 10 ** 6, 100000, "instant_messages"),
    ("pequena.jpg", ".jpg", 50000, 100000, "low_resolution"),
    ("normal.jpg", ".jpg", 10 ** 6, 100000, None),
])
def test_classificar_sufixo(nome, ext, tamanho, min_size, esperado):
    from pathlib import Path
    from pereiras_common.metadados import classificar_sufixo
    caminho = Path("x") / nome
    assert classificar_sufixo(caminho, tamanho=tamanho, min_size_low_res=min_size) == esperado
