# ags-media-chrono

Aplicativo desktop (Windows e Linux) para organizar fotos e vídeos: mostra todas as datas
encontradas em cada arquivo (EXIF, XMP, QuickTime, sistema de arquivos, nome do arquivo),
permite escolher a data correta, gravá-la em todos os campos e renomear em lote com máscaras.

Feito para corrigir mídias baixadas do iCloud, recebidas pelo WhatsApp ou vindas de câmeras
(ex.: Nikon), onde a data correta fica em lugares diferentes.

## Documentação

- [Requisitos](docs/REQUISITOS.md)
- [Tarefas / roadmap](docs/TAREFAS.md)

## Tecnologias

Python 3.13 · PySide6 (Qt 6) · ExifTool · FFmpeg · PyInstaller

## Ambiente de desenvolvimento

Requer Python 3.11+ (recomendado 3.13).

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux
source .venv/bin/activate

pip install -e ".[dev]"
python tools/baixar_ferramentas.py   # ExifTool e FFmpeg em tools/bin/
```

O app procura ExifTool/FFmpeg nesta ordem: variáveis `AGS_EXIFTOOL` / `AGS_FFMPEG` /
`AGS_FFPROBE`, `tools/bin/` e o PATH do sistema. No Linux, em vez do script, também dá para
usar os pacotes do sistema (`sudo apt install libimage-exiftool-perl ffmpeg`). A versão Linux
do ExifTool é um script Perl, então o `perl` precisa estar instalado.

Comandos:

```bash
python -m ags_media_chrono   # abre o app
pytest                       # testes
ruff check . && ruff format --check .   # lint
```

No Linux, o Qt pode precisar de bibliotecas do sistema (ex.: Ubuntu:
`sudo apt install libxcb-cursor0 libegl1`).

## Contribuição

A branch `main` é protegida. Toda alteração entra por Pull Request vinculado a uma Issue.
