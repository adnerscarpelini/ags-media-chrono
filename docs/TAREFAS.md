# Tarefas — Roadmap

> Cada fase entrega algo utilizável. Os IDs podem virar Issues/Milestones no GitHub.

## Fase 0 — Fundação
- [ ] T01 Criar repositório no GitHub (`ags-...`), `.gitignore`, README, licença
- [ ] T02 Estrutura do projeto Python (`src/`, `tests/`, `tools/`, `pyproject.toml`)
- [ ] T03 Script `tools/baixar_ferramentas` que baixa ExifTool e FFmpeg (Windows e Linux)
- [ ] T04 Wrapper do ExifTool em modo `-stay_open` (leitura em JSON, escrita em lote)
- [ ] T05 Janela principal PySide6 com tema dark (QSS) e layout: pastas | galeria | painel

## Fase 1 — Galeria (RF01)
- [ ] T06 Abrir pasta (com/sem subpastas) e listar mídias suportadas
- [ ] T07 Grade de miniaturas (QListView em modo ícone + model/delegate)
- [ ] T08 Geração de miniaturas em background + cache em disco (fotos, HEIC, vídeo via FFmpeg)
- [ ] T09 Zoom (slider + Ctrl+roda), seleção múltipla, ordenação e filtros
- [ ] T10 Visualização ampliada (duplo clique) com player simples para vídeo

## Fase 2 — Leitura e escolha de datas (RF02, RF03)
- [ ] T11 Ler todas as datas de cada arquivo (EXIF, XMP, QuickTime, GPS, sistema de arquivos)
- [ ] T12 Extrair data do nome do arquivo (padrões WhatsApp, Android, iPhone, screenshots)
- [ ] T13 Normalizar fusos (QuickTime UTC → local; OffsetTime)
- [ ] T14 Painel de datas com escolha por rádio + data específica + data atual
- [ ] T15 Escolha em lote por regra de prioridade + predefinições
- [ ] T16 Deslocamento de data/hora
- [ ] T17 Selos de status nas miniaturas (pendente / escolhido / aplicado)

## Fase 3 — Gravação de datas (RF04)
- [ ] T18 Montar comandos ExifTool por tipo (foto/vídeo) com campos selecionáveis
- [ ] T19 Gravar datas do sistema de arquivos (criação no Windows; modificação em ambos)
- [ ] T20 Backup opcional + log de alterações
- [ ] T21 Desfazer a partir do log
- [ ] T22 Progresso, cancelamento e relatório de erros
- [ ] T23 Testes com arquivos de exemplo (JPG, HEIC, MOV iPhone, MP4 WhatsApp, PNG, NEF/JPG Nikon)

## Fase 4 — Renomear em lote (RF05)
- [ ] T24 Motor de máscaras (`{Data[...]}`, `{Nome}`, `#` sequencial, etc.) + testes
- [ ] T25 Diálogo de renomeação com pré-visualização em tempo real
- [ ] T26 Opções: início/etapa, reiniciar por dia, extensão, maiúsculas, substituir/regex, remover acentos
- [ ] T27 Detecção de conflitos e ordenação manual
- [ ] T28 Predefinições salvas + log para desfazer

## Fase 5 — Acabamento e distribuição
- [ ] T29 Fluxo combinado "Aplicar datas e renomear" (RF06)
- [ ] T30 Configurações persistentes
- [ ] T31 Empacotar com PyInstaller (Windows `.exe`, Linux AppImage)
- [ ] T32 GitHub Actions: testes + build para as duas plataformas
- [ ] T33 Ícone, tela "Sobre", documentação de uso
