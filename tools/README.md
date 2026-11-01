# tools/

Ferramentas de terceiros. Os binários ficam em `tools/bin/`, que não é versionado.

```bash
python tools/baixar_ferramentas.py              # baixa o que estiver faltando
python tools/baixar_ferramentas.py --forcar     # baixa de novo (atualiza)
python tools/baixar_ferramentas.py --somente exiftool
```

| Ferramenta | Origem | Licença |
|---|---|---|
| ExifTool (versão mais recente) | exiftool.org / SourceForge | Perl Artistic / GPL |
| FFmpeg 8.1 (build LGPL) | github.com/BtbN/FFmpeg-Builds | LGPL 2.1+ |

Todos os pacotes são conferidos por SHA-256 antes de serem extraídos. As versões instaladas
ficam em `tools/bin/versoes.json`.
