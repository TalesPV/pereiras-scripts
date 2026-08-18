# pereiras-common

Pacote Python que centraliza as funções reutilizáveis pelos scripts do
usuário (fotos, vídeos e áudios). É consumido pelos outros projetos via
dependência git no `pyproject.toml`.

```toml
dependencies = [
    "pereiras-common @ git+https://github.com/TalesPV/pereiras-scripts.git@main",
]
```

---

## Índice

1. [Visão geral](#visão-geral)
2. [Estrutura e relacionamento entre os módulos](#estrutura-e-relacionamento-entre-os-módulos)
3. [Módulo `metadados`](#módulo-metadados)
4. [Módulo `nomeacao`](#módulo-nomeacao)
5. [Módulo `geolocalizacao`](#módulo-geolocalizacao)
6. [Módulo `uteis`](#módulo-uteis)
7. [Módulo `ia`](#módulo-ia)
8. [Chaves de API e segurança](#chaves-de-api-e-segurança)
9. [Desenvolvimento (TDD)](#desenvolvimento-tdd)
10. [Como executar os projetos que consomem este pacote](#como-executar-os-projetos-que-consomem-este-pacote)
11. [Pull Requests](#pull-requests)
12. [ToDos](#todos)

---

## Visão geral

Os projetos `pyPhotosOrganizeTPV` e `verificar_fotos_videos` precisavam
das mesmas capacidades: extrair datas/GPS de mídias, gerar títulos com
IA, montar nomes de arquivo, converter texto para snake_case, calcular
hashes, carregar chaves e geolocalizar por GPS. Este pacote concentra
essas funções para não duplicar código.

Produto atual do pacote:

| Módulo | Produto |
| --- | --- |
| `metadados` | Datas e GPS de **fotos** (EXIF/XMP/PNG), **vídeos** (ffmpeg/MP4) e **áudios** (ID3/©day/Vorbis), com fallback exiftool e sistema de arquivos; coleta unificada `obter_datas` e sufixos de pasta. |
| `nomeacao` | **Nome padrão de mídia** e pastas de destino por data (formato abaixo). |
| `geolocalizacao` | Cidade por GPS (Nominatim/OpenStreetMap, com cache local). |
| `ia` | Análise de **fotos** com IA (Gemini ou OpenAI): título snake_case, resumo, nível de legalidade 1-5, motivo, modelo e tokens. |
| `uteis` | `para_snake_case`, `sha256_arquivo`, `hash_curto_6` (hash alfanumérico de 6 dígitos), `normalizar_titulo` e cache JSONL (`carregar_cache_jsonl`/`gravar_cache_jsonl`); `ler_chave` (chaves de API fora do repositório). |

### Formato padrão do nome das mídias

```
YYYY_MM_DD_HHhMMmSSs-YYYY_MM_DD_HHhMMmSSs-cidade-hash6-titulo.ext
```

- 1º bloco = data mais antiga; 2º = mais recente (repetida se houver uma só).
- `cidade`: snake_case do GPS, `sem_gps` ou coordenadas.
- `hash6`: hash de 6 caracteres do **conteúdo** (antes do título, para
  evitar sobrescrita de arquivos do mesmo horário).
- `titulo`: gerado por IA; omitido em execuções sem IA.
- Apenas **mídias** (foto/vídeo/áudio) são renomeadas; outros arquivos
  mantêm o nome original.
- Os blocos `hash6` e `titulo` são opcionais (parametrização dos clientes).

## Estrutura e relacionamento entre os módulos

```
pereiras-scripts.github/
├── pyproject.toml          # dependências e build (hatchling + uv)
├── README.md               # este documento (toda a especificação)
├── src/pereiras_common/
│   ├── __init__.py         # re-exporta a API pública dos módulos
│   ├── metadados.py        # datas e GPS + obter_datas + classificar_sufixo
│   ├── nomeacao.py         # datas de nome, nome padrão de mídia e pastas
│   ├── geolocalizacao.py   # cidade por GPS (Nominatim, cache local)
│   ├── uteis.py            # texto, hashes, cache JSONL e chaves (sem dependências entre si)
│   └── ia.py               # análise de fotos com IA (usa uteis.normalizar_titulo)
└── tests/
    ├── test_metadados.py   # datas/GPS, obter_datas, classificar_sufixo, sub-IFD EXIF
    ├── test_nomeacao.py    # datas, nome padrão e pastas de destino
    ├── test_geolocalizacao.py  # geocodificação com rede simulada
    ├── test_uteis.py       # texto/hashes/cache JSONL/chaves
    └── test_ia.py          # análise com IA (clientes falsos)
```

Relacionamentos:

```
uteis.py  ──────────┬─── ia.py ─────────────┐
nomeacao.py ──── metadados.py ── geolocalizacao.py ── __init__.py
```

- `metadados` importa as funções de data de `nomeacao` (fonte única).
- `geolocalizacao` importa `uteis.para_snake_case`.
- `ia` importa `uteis.normalizar_titulo`.
- Os projetos clientes importam de `pereiras_common` (ou dos submódulos).

## Módulo `metadados`

Função principal: `extrair_metadados(caminho, *, ano_minimo=1980,
usar_exiftool=True, usar_filesystem=True) -> Metadados`.

`Metadados` (dataclass) tem os campos:

| Campo | Tipo | Descrição |
| --- | --- | --- |
| `caminho` | `Path` | caminho do arquivo analisado |
| `tipo` | `str` | `"imagem"`, `"video"`, `"audio"`, `"office"`, `"outro"` ou `"desconhecido"` |
| `datas` | `list[datetime]` | todas as datas encontradas (ordenadas) |
| `gps` | `tuple[float, float] \| None` | `(latitude, longitude)` ou `None` |

Métodos de conveniência: `data_mais_antiga()` e `data_mais_recente()`.

Fontes por tipo de arquivo:

| Tipo | Data | GPS |
| --- | --- | --- |
| Imagem | EXIF **IFD0 e sub-IFD 0x8769** (36867 DateTimeOriginal, 36868, 306), XMP, texto PNG | EXIF (IFD 0x8825), XMP, fallbacks piexif/exifread (só em JPEG/TIFF/HEIC) |
| Vídeo | `creation_time` (ffmpeg); fallback ©day (mutagen) | `location`/©xyz ISO 6709 (ffmpeg); fallback ©xyz (mutagen) |
| Áudio | ID3 (TDRC/TDOR/TYER), ©day, comentários Vorbis (mutagen) | ©xyz (MP4/M4A) |
| Qualquer | exiftool (opcional, se instalado) | exiftool |
| Qualquer | sistema de arquivos (min criação/modificação) | — |

Funções de baixo nível (também exportadas): `metadados_imagem`,
`metadados_video`, `metadados_audio`, `metadados_exiftool`,
`data_filesystem`, `datas_exif`, `obter_gps`, `parsear_data_iso`,
`parsear_iso6709`, `gms_para_decimal`, `ler_gps_exif`,
`registrar_heif`, `classificar_tipo`.

Funções de alto nível (usadas pelos organizadores):

| Função | Descrição |
| --- | --- |
| `obter_datas(caminho, ano_minimo=1980)` | Coleta `(data_min, data_max, gps)` por metadados -> nome do arquivo -> sistema de arquivos. |
| `classificar_sufixo(caminho, *, tamanho=None, min_size_low_res=100000)` | Sufixo de pasta: `videos`, `audios`, `office`, `outros_tipos`, `screen_capture`, `social_media`, `instant_messages`, `low_resolution` (ou None). |

## Módulo `nomeacao`

Função principal: `montar_nome_midia(data_min, data_max, cidade, *,
hash6=None, titulo="", extensao="") -> str | None` — monta o formato
padrão `YYYY_MM_DD_HHhMMmSSs-YYYY_MM_DD_HHhMMmSSs-cidade-hash6-titulo.ext`
(vide [formato padrão](#formato-padrão-do-nome-das-mídias)).

| Função | Descrição |
| --- | --- |
| `montar_nome_midia` | Nome padrão de mídia; None se > 240 caracteres. |
| `montar_pasta_destino(destino, dt, mask, sufixo=None)` | Subpasta de destino (`%Y_%m` etc., com sufixo opcional; `sem_data` sem data). |
| `formatar_data(dt)` | Máscara `YYYY_MM_DD_HHhMMmSSs`. |
| `extrair_data_nome(nome, ano_minimo=1980)` | Data mais provável no nome do arquivo (várias máscaras). |
| `parsear_data_exif(texto)` / `montar_dt(...)` / `dentro_do_periodo(dt)` | Helpers de data validada. |
| `titulo_valido(titulo)` | Valida o formato snake_case do título. |
| `preservar_nome_original(nome_atual, data_min, data_max, cidade, hash6=None)` | True quando o nome ATUAL já traz um título que o nome alvo perderia (ver abaixo). |

### Não perder o título já gravado no nome

Se um arquivo já foi nomeado com título de IA e uma nova execução roda
**sem IA**, o nome alvo sairia sem o bloco de título — apagando algo que
só uma nova chamada de API saberia recriar. `preservar_nome_original`
detecta esse caso (mesmas datas, mesma cidade, título válido no fim) e o
cliente mantém o nome original:

```
atual: 1997_..-1997_..-sem_gps-retrato_de_jovem.BMP   -> mantido
atual: 1997_..-1997_..-sem_gps.BMP                    -> renomeado (ganha o hash6)
```

## Módulo `geolocalizacao`

| Função | Descrição |
| --- | --- |
| `cidade_por_gps(lat, lon, cache=None, cache_path=None)` | Cidade via Nominatim/OpenStreetMap (gratuito), com cache em JSON e pausa de ~1 req/s (política do serviço). |
| `cidade_ou_coordenadas(lat, lon, ...)` | Cidade em snake_case ou coordenadas (`-23_5500_-46_6333`). |
| `carregar_cache_gps(cache_path=None)` / `salvar_cache_gps(cache, cache_path=None)` | Persistência do cache. |

## Módulo `uteis`

| Função | Assinatura | Descrição |
| --- | --- | --- |
| `para_snake_case` | `(texto) -> str` | "São Paulo" -> "sao_paulo"; sem caracteres especiais; nunca vazio ("sem_nome"). |
| `sha256_arquivo` | `(caminho) -> str \| None` | SHA-256 hexadecimal do conteúdo (chave dos caches de IA). Lê em blocos de 1 MB. |
| `hash_curto_6` | `(caminho, *, digest=None) -> str \| None` | Hash alfanumérico (0-9a-z) de 6 caracteres do conteúdo, para compor nomes. Com `digest` (SHA-256 já calculado) **não relê o arquivo**. |
| `normalizar_titulo` | `(texto, max_palavras=5) -> str` | Limpa o título devolvido pela IA (aspas/markdown), corta em 5 palavras e converte para snake_case; `""` se não sobrar nada. |
| `carregar_cache_jsonl` | `(cache_path, chave="sha256") -> dict` | Lê um cache append-only JSONL como `{chave: registro}`; ignora linhas corrompidas. |
| `gravar_cache_jsonl` | `(registro, cache_path) -> None` | Anexa um registro ao cache JSONL (falhas de I/O são silenciosas de propósito). |
| `expandir_caminho` | `(caminho) -> Path \| None` | Resolve `~`, `$HOME` e `%USERPROFILE%` no caminho digitado. `None` entra, `None` sai. |
| `ler_chave` | `(caminho_arquivo, tipo=None) -> str \| None` | Lê uma chave de API de arquivo (fora do repositório), limpa espaços e valida tamanho mínimo. Apontando para uma **pasta** com `tipo`, localiza o arquivo lá dentro. |
| `localizar_chave` | `(diretorio, tipo) -> Path \| None` | Acha o arquivo de chave do provedor aceitando variações de nome (ver abaixo). |

Constantes: `DIR_CHAVES_PADRAO` (`$HOME\.chaves_ia`), `CHAVE_GEMINI_PADRAO`,
`CHAVE_OPENAI_PADRAO`.

### Especificação do `hash_curto_6`

- Lê o arquivo em blocos de 1 MB e calcula o SHA-256 (não carrega tudo em memória).
- Converte o digesto para base 36 (dígitos + letras minúsculas: **sem caracteres especiais**).
- Pega exatamente **6 caracteres** (módulo `36^6 ≈ 2,2 bilhões` de combinações).
- Determinístico: mesmo conteúdo => mesmo hash; conteúdo diferente => hash diferente.
- `None` quando o arquivo não pode ser lido.
- Colisões são raras em coleções domésticas (dezenas de milhares de arquivos),
  mas possíveis; para unicidade absoluta use o SHA-256 completo.

## Módulo `ia`

Função principal:

```python
analisar_foto(chave_assinatura, tipo_ia, caminho_arquivo, *,
              modelo=None, max_dimensao=1024, qualidade_jpeg=85) -> AnaliseFoto
```

| Parâmetro | Descrição |
| --- | --- |
| `chave_assinatura` | chave de API (string; nunca é gravada em log ou disco) |
| `tipo_ia` | `"gemini"` ou `"openai"` (por enquanto, apenas estes) |
| `caminho_arquivo` | caminho completo da foto |
| `modelo` | opcional; padrão `gemini-3.6-flash` / `gpt-4o-mini` |
| `max_dimensao` / `qualidade_jpeg` | preparo da imagem enviada (economia de tokens) |

`AnaliseFoto` (dataclass):

| Campo | Tipo | Descrição |
| --- | --- | --- |
| `titulo` | `str` | título snake_case, máx. 5 palavras |
| `resumo` | `str` | descrição objetiva do conteúdo |
| `nivel` | `int` | legalidade 1-5 (veja escala abaixo) |
| `motivo` | `str` | justificativa do nível |
| `modelo` | `str` | modelo usado na análise |
| `tokens_entrada` / `tokens_saida` | `int` | consumo de tokens (custo) |

Escala de legalidade: **1** comum e seguro; **2** levemente sensível
(adulto legal); **3** suspeito (revisão manual); **4** provavelmente
ilegal; **5** ilegal/crítico.

Exceções: `ErroAnaliseIA` (análise falhou) e `ValueError` (tipo de IA
não suportado).

## Chaves de API e segurança

Política adotada (recomendada):

- As chaves NUNCA são escritas no código nem versionadas no git.
- Padrão: arquivos na pasta do usuário `$HOME\.chaves_ia\`
  (Windows; no Linux/macOS, `~/.chaves_ia/`):
  - `chave_google_gemini.key` (Gemini)
  - `chave_openai_chatgpt.key` (OpenAI)
- Cada programa cliente aceita o caminho do arquivo pela linha de
  comando (`--chave-gemini`/`--chave-openai`), sempre com o padrão acima.
- Os caminhos aceitam `~`, `$HOME` e `%USERPROFILE%` (`expandir_caminho`).
  Isso importa no PowerShell: entre **aspas simples** ele não expande
  `$HOME`, e o texto chegaria literal ao programa.
- **O nome do arquivo é flexível.** Sem `--chave-*`, os programas procuram na
  pasta um arquivo cujo nome cite o provedor. Todos estes funcionam:

  ```
  chave_google_gemini.key      CHAVE_GOOGLE_GEMINI.txt      ._CHAVE_GOOGLE_GEMINI.txt
  chave_openai_chatgpt.key     CHAVE_OPENAI_CHATGPT.txt     ._CHAVE_OPENAI_CHATGPT.txt
  ```

  Arquivos com menos de 10 caracteres são ignorados, para que um arquivo
  vazio na pasta não mascare a chave verdadeira.
- A chave em si viaja apenas como parâmetro de função (nunca aparece em logs).

> Nota de segurança: evite passar a chave como texto puro na linha de
> comando (fica visível no histórico e no gerenciador de processos).
> O padrão deste pacote é passar o **caminho do arquivo** de chave — o
> programa lê o conteúdo internamente. Alternativa equivalente:
> variáveis de ambiente.

## Desenvolvimento (TDD)

Desenvolvimento guiado por testes: primeiro o teste (vermelho), depois a
implementação (verde), depois refatoração.

```bash
uv sync          # instala dependências e o ambiente
uv run pytest    # roda todos os testes
```

### exiftool (opcional, recomendado)

O [exiftool](https://exiftool.org/) é o padrão de referência em leitura de
metadados e serve de **fallback** quando Pillow, ffmpeg e mutagen não acham
data ou GPS. Sem ele o programa funciona, apenas com menos alternativas.

```powershell
winget install --id OliverBetz.ExifTool --exact
```

O caminho é resolvido no momento do `import`: depois de instalar, abra um
terminal novo para que o programa o enxergue.


Convenções:

- Testes em `tests/test_<modulo>.py`.
- Testes de IA usam clientes falsos (nunca chamam a API real).
- Testes de vídeo/áudio geram arquivos pequenos com o ffmpeg embutido
  (`imageio-ffmpeg`).

## Como executar os projetos que consomem este pacote

```powershell
# Organizar fotos/vídeos por data (pyPhotosOrganizeTPV)
uv run python -m py_photos_organize_tpv -o D:\fotos -d E:\organizado --dry-run

# Classificar mídias por risco de ilegalidade (verificar_fotos_videos)
uv run python classificar_gemini.py --dry-run

# Renomear usando as classificações
uv run python renomear_arquivos.py --limite 100
```

Os projetos usam `uv` para dependências; o `uv.lock` é versionado.

## Pull Requests

Fluxo para contribuir:

1. Crie uma branch a partir de `main`: `git switch -c feat/nome-curto`.
2. Escreva/ajuste os testes primeiro (TDD): `uv run pytest` deve falhar
   antes da implementação e passar depois.
3. Atualize este README se a API pública mudar.
4. Abra o PR para `main` descrevendo: problema, solução, testes e impactos.
5. Requisitos de merge: testes passando e README atualizado.

## Histórico de versões

### 0.3.0

- **Novo**: `expandir_caminho` resolve `~`, `$HOME` e `%USERPROFILE%` nos
  caminhos digitados. Importa no PowerShell: entre aspas simples ele não
  expande `$HOME`, e o texto chegava literal ao programa.
- **Novo**: `localizar_chave` encontra o arquivo de chave por variação de nome
  dentro da pasta (`chave_google_gemini.key`, `CHAVE_GOOGLE_GEMINI.txt`,
  `._CHAVE_GOOGLE_GEMINI.txt`), em vez de exigir um nome exato. `ler_chave`
  passa a aceitar uma pasta mais o `tipo` do provedor.
- **Novo**: `preservar_nome_original` indica quando o nome atual já traz um
  título que o nome alvo perderia — usado para não apagar títulos de IA em
  execuções sem IA.

### 0.2.0

- **Correção**: a data de captura (`DateTimeOriginal`, tag 36867) vive no
  sub-IFD EXIF `0x8769`, e não no IFD0 devolvido por `Image.getexif()`.
  A leitura antiga só encontrava a tag 306 (`DateTime`, última alteração).
  Quando a câmera grava as duas iguais nada mudava, mas em fotos editadas
  (306 = data da edição) ou sem a tag 306 a data de captura era perdida e
  o arquivo caía na data do **sistema de arquivos**. Nova função pública:
  `datas_exif(exif, ano_minimo)`.
- **Correção**: os fallbacks piexif/exifread só são acionados em formatos
  que carregam EXIF (`EXTS_COM_EXIF`). Antes, cada BMP/GIF/PNG era relido
  duas vezes à toa e o log enchia de "File format not recognized".
- **Novo**: `sha256_arquivo`, `normalizar_titulo`, `carregar_cache_jsonl` e
  `gravar_cache_jsonl` (migrados dos dois projetos clientes).
- **Novo**: `hash_curto_6(caminho, *, digest=...)` reaproveita um SHA-256 já
  calculado — uma leitura por arquivo em vez de duas.
- **Novo**: `expandir_caminho` resolve `~`, `$HOME` e `%USERPROFILE%` nos
  caminhos digitados (o PowerShell não expande `$HOME` entre aspas simples).
- **Novo**: `preservar_nome_original` evita apagar o título já gravado no
  nome quando a execução roda sem IA.
- **Novo**: `localizar_chave` encontra a chave por variação de nome dentro da
  pasta, em vez de exigir um nome exato de arquivo.

## ToDos

- [x] Migrar funções duplicadas restantes dos clientes (`sha256_arquivo`,
      cache JSONL, `normalizar_titulo`) para este pacote. **Feito na 0.2.0.**
- [ ] `analisar_foto` para **vídeos** (frames) e **áudios**.
- [ ] Suporte a mais tipos de IA (`tipo_ia`) no futuro.
- [ ] Publicar no PyPI quando estabilizar (hoje: instalação via git).
- [ ] CI (GitHub Actions) para rodar os testes a cada PR.
