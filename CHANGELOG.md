# Changelog

Todas as mudanças relevantes do projeto. Formato baseado em
[Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/); versões seguem
[SemVer](https://semver.org/lang/pt-BR/).

## [Não lançado]

## [0.1.0] — 2026-11-01

Primeira versão.

### Galeria
- Abrir pasta (com ou sem subpastas) e ver fotos e vídeos em grade de miniaturas com zoom.
- Miniaturas de JPG, HEIC, PNG, RAW (NEF e outros, pela prévia embutida) e vídeos, geradas em
  segundo plano e guardadas em cache.
- Filtros por tipo, status e nome; ordenação por nome, data escolhida, data de modificação,
  tipo e tamanho.
- Visualização ampliada de fotos e player de vídeo (HEVC do iPhone incluso).

### Datas
- Leitura de **todas** as datas de cada arquivo: EXIF, XMP, QuickTime/Keys, GPS, notas do
  fabricante (Nikon), sistema de arquivos e nome do arquivo (WhatsApp, Android, Pixel,
  capturas de tela, Signal, Telegram…).
- Fusos normalizados: datas QuickTime em UTC e do GPS aparecem no horário local.
- Data de captura existente pré-selecionada como **sugerida**.
- Escolha de data específica ou atual, ajuste de dias/horas/minutos e escolha em lote por regra
  de prioridade, com predefinições.
- Gravação nos metadados (EXIF/XMP das fotos, QuickTime/Keys dos vídeos) e nas datas do arquivo,
  com progresso, relatório, backup opcional, histórico e **desfazer**.

### Renomear em lote
- Máscaras `{Data[...]}`, `{Nome}`, `{Ext}`, `{Pasta}`, `{Tipo}` e `#` sequencial; início,
  etapa e reinício por dia; maiúsculas/minúsculas, substituir (com regex) e remover acentos.
- Prévia ao vivo com conflitos destacados; renomeação segura (trocas A↔B, reversão em caso de
  erro); predefinições e desfazer.
- Fluxo combinado "Aplicar datas e renomear".

### Distribuição
- Pacotes sem necessidade de Python: `.zip` (Windows), `.tar.gz` e AppImage (Linux), com
  ExifTool e FFmpeg incluídos.
- CI com testes no Windows e no Linux; release automática por tag.

[Não lançado]: https://github.com/adnerscarpelini/ags-media-chrono/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/adnerscarpelini/ags-media-chrono/releases/tag/v0.1.0
