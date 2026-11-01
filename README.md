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
```

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
