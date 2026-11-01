# Tarefas — Roadmap

> Cada fase entrega algo utilizável. Cada tarefa é uma Issue no GitHub (T01 = #1 … T33 = #33).
> Todas concluídas na versão 0.1.0.

## Fase 0 — Fundação
- [x] T01 Criar repositório no GitHub (`ags-...`), `.gitignore`, README, licença
- [x] T02 Estrutura do projeto Python (`src/`, `tests/`, `tools/`, `pyproject.toml`)
- [x] T03 Script `tools/baixar_ferramentas` que baixa ExifTool e FFmpeg (Windows e Linux)
- [x] T04 Wrapper do ExifTool em modo `-stay_open` (leitura em JSON, escrita em lote)
- [x] T05 Janela principal PySide6 com tema dark (QSS) e layout: pastas | galeria | painel

## Fase 1 — Galeria (RF01)
- [x] T06 Abrir pasta (com/sem subpastas) e listar mídias suportadas
- [x] T07 Grade de miniaturas (QListView em modo ícone + model/delegate)
- [x] T08 Geração de miniaturas em background + cache em disco (fotos, HEIC, vídeo via FFmpeg)
- [x] T09 Zoom (slider + Ctrl+roda), seleção múltipla, ordenação e filtros
- [x] T10 Visualização ampliada (duplo clique) com player simples para vídeo

## Fase 2 — Leitura e escolha de datas (RF02, RF03)
- [x] T11 Ler todas as datas de cada arquivo (EXIF, XMP, QuickTime, GPS, sistema de arquivos)
- [x] T12 Extrair data do nome do arquivo (padrões WhatsApp, Android, iPhone, screenshots)
- [x] T13 Normalizar fusos (QuickTime UTC → local; OffsetTime)
- [x] T14 Painel de datas com escolha por rádio + data específica + data atual
- [x] T15 Escolha em lote por regra de prioridade + predefinições
- [x] T16 Deslocamento de data/hora
- [x] T17 Selos de status nas miniaturas (pendente / escolhido / aplicado)

## Fase 3 — Gravação de datas (RF04)
- [x] T18 Montar comandos ExifTool por tipo (foto/vídeo) com campos selecionáveis
- [x] T19 Gravar datas do sistema de arquivos (criação no Windows; modificação em ambos)
- [x] T20 Backup opcional + log de alterações
- [x] T21 Desfazer a partir do log
- [x] T22 Progresso, cancelamento e relatório de erros
- [x] T23 Testes com arquivos de exemplo (JPG, HEIC, MOV iPhone, MP4 WhatsApp, PNG, NEF/JPG Nikon)
      — amostras geradas na hora pelos testes; NEF real opcional (`AGS_AMOSTRA_NEF`)

## Fase 4 — Renomear em lote (RF05)
- [x] T24 Motor de máscaras (`{Data[...]}`, `{Nome}`, `#` sequencial, etc.) + testes
- [x] T25 Diálogo de renomeação com pré-visualização em tempo real
- [x] T26 Opções: início/etapa, reiniciar por dia, extensão, maiúsculas, substituir/regex, remover acentos
- [x] T27 Detecção de conflitos e ordenação manual
- [x] T28 Predefinições salvas + log para desfazer

## Fase 5 — Acabamento e distribuição
- [x] T29 Fluxo combinado "Aplicar datas e renomear" (RF06)
- [x] T30 Configurações persistentes
- [x] T31 Empacotar com PyInstaller (Windows `.exe`, Linux AppImage)
- [x] T32 GitHub Actions: testes + build para as duas plataformas
- [x] T33 Ícone, tela "Sobre", documentação de uso
