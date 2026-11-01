# CLAUDE.md

Guia para o Claude Code (e para quem mais contribuir) trabalhar neste repositório.

## O projeto
**AGS Media Chrono** (`ags-media-chrono`): app desktop Windows/Linux que mostra todas as datas de
fotos e vídeos (EXIF, XMP, QuickTime, GPS, notas do fabricante, sistema de arquivos, nome do
arquivo), deixa escolher a correta, grava em todos os campos e renomeia em lote com máscaras.
Origens típicas do usuário: iPhone/iCloud (HEIC, MOV HEVC), WhatsApp, câmera Nikon (JPG/NEF).

Stack: Python 3.13 · PySide6 (Qt 6) · ExifTool (processo `-stay_open`) · FFmpeg · PyInstaller.

## Comandos
```bash
pip install -e ".[dev]"                 # dependências (venv em .venv/)
python tools/baixar_ferramentas.py      # ExifTool + FFmpeg em tools/bin/ (fora do Git)
python -m ags_media_chrono              # abre o app
pytest -q                               # testes (~1 min; precisam de ExifTool/FFmpeg)
ruff check . && ruff format --check .   # lint (linha de 100 colunas)
python tools/empacotar.py               # pacote em dist/ (zip no Windows; tar.gz/AppImage no Linux)
python tools/capturar_telas.py          # recria os prints do README a partir da demonstração
python -m ags_media_chrono.core.datas ARQUIVO...   # lista as datas de arquivos (diagnóstico)
```
Teste com NEF real (não versionado): defina `AGS_AMOSTRA_NEF=<caminho .NEF>` antes do pytest.

## Estrutura
- `src/ags_media_chrono/core/` — lógica sem Qt: `exiftool.py` (wrapper), `datas.py` (leitura,
  fusos), `nome_arquivo.py`, `escolhas.py` (status/escolha), `regras.py` (escolha em lote),
  `gravacao.py` (gravar/desfazer), `historico.py`, `mascaras.py` e `renomear.py`, `miniaturas.py`,
  `midias.py`, `ferramentas.py` (localiza ExifTool/FFmpeg).
- `src/ags_media_chrono/ui/` — interface Qt: `main_window.py` liga tudo; um arquivo por
  painel/diálogo; trabalho pesado em `QThreadPool` (carregador, gerador de miniaturas, leitor
  de datas, gravação).
- `tests/` — pytest; `amostras.py` gera mídias de cada origem na hora (sem binários no repo).
- `tools/` — scripts (ferramentas, empacotar, demonstração, prints). `empacotamento/` — spec do
  PyInstaller. `docs/` — requisitos, tarefas, como publicar versão.

## Convenções
- **Português** em identificadores, comentários, mensagens e interface (ex.: `ler_datas`,
  `DataCandidata`). Siga o estilo do arquivo que estiver editando.
- Lógica nova vai em `core/` (testável sem Qt); `ui/` só apresenta e orquestra.
- Threads de trabalho emitem sinais via `ui.threads.emitir()` (seguro se a janela já fechou).
- Datas internas sempre com fuso quando conhecido; exibição via `DatasArquivo.hora_local()`.
  QuickTime `CreateDate` é UTC por padrão (`OpcoesFuso.quicktime_utc`).
- Toda gravação/renomeação vira uma `Operacao` no histórico e precisa poder ser desfeita.
- Ao escrever arquivos de texto por script no Windows, use `newline="\n"` (o repo é LF).

## Fluxo de trabalho (GitHub)
- Repositório público `adnerscarpelini/ags-media-chrono`. **`main` protegida**: só via PR;
  CI obrigatório (`testes (windows-latest)` e `testes (ubuntu-latest)`); merge por squash.
- Cada entrega é uma **Issue**; branch `feat/<nº>-descricao` (ou `docs/…`, `fix/…`); PR com
  `Closes #N`. O usuário revisa e faz o merge.
- Commits e PRs em português, explicando o porquê.
- Versão: só em `src/ags_media_chrono/__init__.py`; publicar seguindo `docs/RELEASE.md`
  (tag `vX.Y.Z` dispara a release com os pacotes).

## Cuidados importantes
- **`C:\MidiasAjustar` contém mídias reais do usuário: somente leitura.** Nunca gravar,
  renomear ou desfazer nada lá. Para testar gravação use cópias ou `tools/criar_demo.py`.
- Testes nunca tocam no perfil real: `tests/conftest.py` isola cache, histórico e configurações
  (QSettings) em pastas temporárias e transforma `QMessageBox` modal em falha (evita travar).
- **Prints da interface: só da janela do app (`widget.grab()`), nunca captura de tela** — já
  capturou conteúdo pessoal de outras janelas. Antes de publicar um print, confira que não há
  caminhos com o nome do usuário nem pastas/fotos pessoais (o repo é público).
- Vídeos do iPhone são HEVC 10 bits/HDR: miniaturas e reprodução podem ter cores lavadas
  (ainda não tratado).
