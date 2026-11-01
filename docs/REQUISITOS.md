# Requisitos — App de Datas e Renomeação de Mídias

> Status: aprovado para início (2026-11-01)

## 0. Fluxo de trabalho

- Repositório público `ags-media-chrono` no GitHub.
- Branch `main` protegida: alterações somente via Pull Request.
- Cada entrega é uma **Issue**; as fases são **Milestones**.
- Branches no padrão `feat/<nº-issue>-descricao`, e o PR fecha a issue (`Closes #N`).

## 1. Objetivo

Corrigir as datas de fotos e vídeos baixados do iCloud, WhatsApp, etc., onde a data
correta está "espalhada" em campos diferentes (EXIF, QuickTime, XMP, sistema de
arquivos, nome do arquivo). O app mostra todas as datas encontradas em cada arquivo,
o usuário escolhe qual é a correta, e o app grava essa data em todos os campos.
Também permite renomear em lote com máscaras.

## 2. Plataforma e stack (proposta)

| Item | Escolha | Motivo |
|---|---|---|
| Linguagem | Python 3.13 | Já instalado na máquina; rápido de desenvolver |
| Interface | PySide6 (Qt 6) | Roda igual no Windows e Linux; tema dark fácil; grade de miniaturas performática |
| Metadados | ExifTool (Phil Harvey) | Lê/grava EXIF, XMP, QuickTime, HEIC, MP4, MOV, PNG... referência do mercado |
| Miniaturas de vídeo | FFmpeg | Extrai um frame do vídeo |
| HEIC | pillow-heif | Miniatura de fotos do iPhone |
| Empacotamento | PyInstaller | Gera `.exe` no Windows e binário/AppImage no Linux |

Ferramentas de terceiros ficam em `tools/` (ExifTool e FFmpeg por plataforma), com
script para baixá-las — não vão versionadas no Git.

## 3. Requisitos funcionais

### RF01 — Navegação e galeria
- Abrir uma pasta (com opção de incluir subpastas).
- Exibir fotos e vídeos em grade de miniaturas, estilo XnView MP / Adobe Bridge.
- Zoom das miniaturas (slider + Ctrl+roda do mouse).
- Ícone indicando vídeo e duração.
- Seleção simples, múltipla (Ctrl/Shift) e "selecionar tudo".
- Ordenar por nome, data escolhida, data de captura, tipo.
- Filtrar: só fotos, só vídeos, só "pendentes" (sem data escolhida), só "com divergência".
- Miniaturas geradas em segundo plano, com cache em disco.
- Formatos: JPG, JPEG, HEIC, PNG, GIF, WEBP, NEF (Nikon), DNG/RAW comuns, MOV, MP4, M4V, 3GP, AVI.
- RAW (NEF): miniatura a partir do preview JPEG embutido (extraído pelo ExifTool).

### RF02 — Painel de datas do arquivo selecionado
Lista todas as datas encontradas no arquivo, cada uma com a origem:

| Origem | Exemplos de campos |
|---|---|
| EXIF | DateTimeOriginal, CreateDate, ModifyDate (+ OffsetTime*) |
| XMP | xmp:CreateDate, photoshop:DateCreated, exif:DateTimeOriginal |
| QuickTime (vídeos) | CreationDate (Apple, com fuso), CreateDate, MediaCreateDate, TrackCreateDate |
| Fabricante (MakerNotes) | Ex.: Nikon — datas internas da câmera, fuso/horário de verão configurado |
| GPS | GPSDateStamp + GPSTimeStamp (UTC) |
| Sistema de arquivos | Data de criação, data de modificação |
| Nome do arquivo | Ex.: `IMG-20230512-WA0001.jpg`, `VID_20230512_143000.mp4`, `Screenshot_2023-05-12...` |

- Origens previstas: iPhone/iCloud (HEIC, JPG, MOV), WhatsApp (JPG, MP4 sem EXIF, data no
  nome), câmera Nikon (JPG `DSC_xxxx`, RAW `.NEF`, MOV/MP4). O princípio é o mesmo para
  qualquer origem: mostrar **todas** as datas encontradas para o usuário escolher.
- O usuário marca qual data é a correta (botão de rádio por linha).
- Opções extras: **data específica** (seletor de data/hora) e **data atual**.
- Mostrar a data mais antiga encontrada em destaque (geralmente é a correta).
- Indicar fuso horário quando existir; tratar `QuickTime:CreateDate` como UTC (padrão
  da especificação) e converter para hora local na exibição.

### RF03 — Escolha em lote
- Aplicar a mesma regra para vários arquivos selecionados, ex.:
  "usar EXIF DateTimeOriginal; se não existir, QuickTime CreationDate; se não existir,
  data do nome do arquivo; senão, a mais antiga".
- Regras salvas como predefinições.
- Ajuste de deslocamento (ex.: +3h, −1 dia) para câmeras com relógio errado.
- Miniatura mostra um selo de status: pendente / data escolhida / aplicado.

### RF04 — Aplicar datas
- Botão **Aplicar** grava a data escolhida em todos os campos relevantes:
  - Fotos: EXIF DateTimeOriginal, CreateDate, ModifyDate, XMP equivalentes.
  - Vídeos: QuickTime CreateDate/ModifyDate/MediaCreateDate/TrackCreateDate (UTC),
    Keys:CreationDate (com fuso).
  - Sistema de arquivos: data de modificação e data de criação.
- O usuário pode desmarcar campos que não quer alterar.
- Barra de progresso, cancelamento e relatório final (sucesso / erro por arquivo).
- **Segurança**: opção de backup (cópia `_original` do ExifTool ou pasta de backup) e
  log de alterações (CSV/JSON) que permite **desfazer**.

> Limitação conhecida: no Linux a maioria dos sistemas de arquivos não permite alterar a
> data de criação (birth time). Nesse caso só a data de modificação e os metadados internos
> são alterados — o app deve avisar isso.

### RF05 — Renomear em lote
Tela parecida com o "Renomear lote" do XnView:
- Campo de **modelo de nome** com máscaras:

| Máscara | Resultado |
|---|---|
| `{Data}` | `2026-11-01` (formato configurável) |
| `{Data[YYYY]}` `{Data[YY]}` | Ano |
| `{Data[MM]}` `{Data[DD]}` | Mês, dia |
| `{Data[HH]}` `{Data[mm]}` `{Data[ss]}` | Hora, minuto, segundo |
| `{Nome}` | Nome original sem extensão |
| `{Ext}` | Extensão |
| `{Pasta}` | Nome da pasta atual |
| `{Tipo}` | `foto` / `video` |
| `#`, `##`, `####` | Sequencial com zeros à esquerda |

- `{Data...}` usa a **data escolhida** no RF02 (ou a data já gravada).
- Sequencial: início, etapa (incremento), opção de reiniciar a contagem por dia.
- Botão com menu para inserir máscaras no modelo.
- Extensão: manter, maiúsculas, minúsculas.
- Maiúsculas/minúsculas no nome.
- Substituir texto (com opção de expressão regular e sensível a maiúsculas).
- Remover acentos (diacríticos).
- **Pré-visualização** em tabela: nome antigo | nome novo | diretório, atualizada em tempo real.
- Detectar conflitos (nomes repetidos ou já existentes) e destacá-los em vermelho.
- Ordem dos arquivos ajustável (subir/descer, ordenar por data).
- Predefinições salvas (ex.: `{Data[YYYY]}_ministerio_{Data[YYYY]}{Data[MM]}{Data[DD]}_####`).
- Log para desfazer a renomeação.

### RF06 — Fluxo combinado
- Opção de "Aplicar datas e renomear" em uma só ação.

## 4. Requisitos não funcionais

- **RNF01** Visual dark profissional (tons de cinza grafite, destaque discreto, estilo Lightroom/Bridge).
- **RNF02** Interface em português (estrutura pronta para tradução).
- **RNF03** Pasta com 5.000+ arquivos sem travar (leitura e miniaturas em threads; ExifTool em modo `-stay_open`).
- **RNF04** Nunca perder dados: escrita só após confirmação, backup opcional, log de desfazer.
- **RNF05** Windows 10/11 e Linux (Ubuntu/Fedora) com o mesmo código.
- **RNF06** Configurações persistidas (última pasta, tamanho das miniaturas, predefinições).
- **RNF07** Testes automatizados para leitura/gravação de datas e para o motor de máscaras.

## 5. Fora do escopo (versão 1)

- Edição de imagem (corte, cor, etc.).
- Edição de outros metadados (GPS, palavras-chave, rosto).
- Sincronização direta com iCloud.
