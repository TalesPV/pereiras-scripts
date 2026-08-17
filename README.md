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
| `uteis` | `para_snake_case`, `hash_curto_6` (hash alfanumérico de 6 dígitos) e `ler_chave` (chaves de API fora do repositório). |

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
│   ├── uteis.py            # texto, hash curto e chaves (sem dependências entre si)
│   └── ia.py               # análise de fotos com IA (usa uteis.para_snake_case)
└── tests/
    ├── test_metadados.py   # 40+ testes (inclusive obter_datas/classificar_sufixo)
    ├── test_nomeacao.py    # datas, nome padrão e pastas de destino
    ├── test_geolocalizacao.py  # geocodificação com rede simulada
    ├── test_uteis.py       # texto/hash/chaves
    └── test_ia.py          # análise com IA (clientes falsos)
```

Relacionamentos:

```
uteis.py  ──────────┬─── ia.py ─────────────┐
nomeacao.py ──── metadados.py ── geolocalizacao.py ── __init__.py
```

- `metadados` importa as funções de data de `nomeacao` (fonte única).
- `geolocalizacao` importa `uteis.para_snake_case`.
- `ia` importa `uteis.para_snake_case`.
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
| Imagem | EXIF (36867/36868/306), XMP, texto PNG | EXIF (IFD 0x8825), XMP, fallbacks piexif/exifread |
| Vídeo | `creation_time` (ffmpeg); fallback ©day (mutagen) | `location`/©xyz ISO 6709 (ffmpeg); fallback ©xyz (mutagen) |
| Áudio | ID3 (TDRC/TDOR/TYER), ©day, comentários Vorbis (mutagen) | ©xyz (MP4/M4A) |
| Qualquer | exiftool (opcional, se instalado) | exiftool |
| Qualquer | sistema de arquivos (min criação/modificação) | — |

Funções de baixo nível (também exportadas): `metadados_imagem`,
`metadados_video`, `metadados_audio`, `metadados_exiftool`,
`data_filesystem`, `obter_gps`, `parsear_data_iso`,
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
| `hash_curto_6` | `(caminho) -> str \| None` | Hash alfanumérico (0-9a-z) de 6 caracteres do conteúdo do arquivo, para compor nomes. |
| `ler_chave` | `(caminho_arquivo) -> str \| None` | Lê uma chave de API de arquivo (fora do repositório), limpa espaços e valida tamanho mínimo. |

Constantes: `DIR_CHAVES_PADRAO` (`~/.chaves_ia`), `CHAVE_GEMINI_PADRAO`,
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
- Padrão: arquivos na pasta do usuário `~/.chaves_ia/`:
  - `chave_gemini.key` (Gemini)
  - `chave_openai_chatgpt.key` (OpenAI)
- Cada programa cliente aceita o caminho do arquivo pela linha de
  comando (`--chave-gemini`/`--chave-openai`), sempre com o padrão acima.
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

## ToDos

- [ ] Migrar funções duplicadas restantes dos clientes (sha256_arquivo,
      cache de títulos) para este pacote.
- [ ] `analisar_foto` para **vídeos** (frames) e **áudios**.
- [ ] Suporte a mais tipos de IA (`tipo_ia`) no futuro.
- [ ] Publicar no PyPI quando estabilizar (hoje: instalação via git).
- [ ] CI (GitHub Actions) para rodar os testes a cada PR.
