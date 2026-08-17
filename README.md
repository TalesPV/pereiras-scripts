# pereiras-common

Pacote Python que centraliza funções reutilizáveis por vários projetos
de scripts (atualmente, extração de metadados de fotos, vídeos e áudios).

## Estrutura

- `src/pereiras_common/`: código compartilhado
- `tests/`: testes automatizados
- `pyproject.toml`: metadados e build do pacote

## Desenvolvimento

```bash
uv sync
uv run pytest
```

## Instalação em outros projetos

Adicione a dependência via git no `pyproject.toml` (com `uv`):

```toml
dependencies = [
    "pereiras-common @ git+https://github.com/TalesPV/pereiras-scripts.git@main",
]
```

ou em `requirements.txt`:

```
pereiras-common @ git+https://github.com/TalesPV/pereiras-scripts.git@main
```

## Uso

```python
from pathlib import Path
from pereiras_common.metadados import extrair_metadados

md = extrair_metadados(Path("foto.jpg"))
print(md.tipo)              # "imagem" | "video" | "audio" | ...
print(md.data_mais_antiga())  # datetime mais antigo encontrado (ou None)
print(md.data_mais_recente()) # datetime mais recente encontrado (ou None)
print(md.gps)               # (latitude, longitude) ou None
```

Fontes de metadados por tipo de arquivo:

- **Imagens**: EXIF (Pillow), XMP, texto PNG; fallbacks piexif e exifread.
- **Vídeos**: ffmpeg (`creation_time` e localização ISO 6709/©xyz); fallback mutagen (MP4/MOV).
- **Áudios**: mutagen (ID3 do MP3, ©day/©xyz do MP4/M4A, comentários Vorbis do OGG/Opus/FLAC).
- **Fallback opcional**: binário `exiftool`, se instalado.
- **Última alternativa**: data de criação/modificação do sistema de arquivos.

Funções de baixo nível também estão disponíveis em
`pereiras_common.metadados` (`metadados_imagem`, `metadados_video`,
`metadados_audio`, `metadados_exiftool`, `obter_gps`,
`parsear_data_iso`, `parsear_iso6709`, `registrar_heif` etc.).

## Bibliotecas de metadados

Escolhas baseadas em manutenção ativa, reputação na comunidade, histórico
de segurança e menor superfície de dependências:

| Biblioteca | Uso |
| --- | --- |
| **Pillow** (+ pillow-heif) | padrão de fato para imagens (EXIF + XMP) |
| **ffmpeg** (via imageio-ffmpeg) | padrão de fato para vídeo/áudio; binário empacotado |
| **mutagen** | padrão para metadados de áudio (ID3, MP4, comentários Vorbis) |
| **defusedxml** | parser XML protegido contra XXE/billion laughs (leitura segura de XMP) |
| **piexif** / **exifread** | fallbacks para EXIF parcialmente corrompido ou não padronizado |
| **exiftool** (binário externo, opcional) | padrão-ouro em perícia forense; usado apenas se instalado |

Evitadas: `fragments` (abandonada), wrappers de exiftool que injetam nomes de
arquivo em linha de comando (superfície de injeção), e bibliotecas
redundantes (Pillow já cobre o essencial de imagens).

