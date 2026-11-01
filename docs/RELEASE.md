# Como publicar uma versão

As releases são geradas pelo GitHub Actions ([release.yml](../.github/workflows/release.yml))
quando uma tag `v*` é enviada. O workflow gera os pacotes de Windows e Linux, testa os
executáveis e publica a Release com os arquivos anexados.

## Passo a passo

1. **Atualize a versão** em `src/ags_media_chrono/__init__.py` (`__version__`).
   O `pyproject.toml` lê a versão de lá — não há outro lugar para mudar.
2. **Atualize o [CHANGELOG](../CHANGELOG.md):** mova os itens de *Não lançado* para uma nova
   seção `## [X.Y.Z] — AAAA-MM-DD` e ajuste os links do fim do arquivo.
3. **Abra um PR** com essas mudanças e faça o merge (o CI precisa passar).
4. **Crie e envie a tag** a partir da `main` atualizada:

   ```bash
   git checkout main && git pull
   git tag -a vX.Y.Z -m "AGS Media Chrono X.Y.Z"
   git push origin vX.Y.Z
   ```

5. Acompanhe em **Actions › Release**. Ao terminar, a Release aparece em
   [Releases](https://github.com/adnerscarpelini/ags-media-chrono/releases) com:
   - `ags-media-chrono-X.Y.Z-windows-x64.zip`
   - `ags-media-chrono-X.Y.Z-linux-x64.tar.gz`
   - `ags-media-chrono-X.Y.Z-linux-x64.AppImage`
6. Revise o texto da Release (gerado a partir dos PRs) e, se quiser, cole o trecho do CHANGELOG.

## Versões (SemVer)

- **Correção** (nada muda para o usuário além do conserto): `0.1.0` → `0.1.1`
- **Funcionalidade nova** compatível: `0.1.1` → `0.2.0`
- **Mudança incompatível** (ex.: formato do histórico ou das configurações): `0.x` → `1.0.0`

## Testar o empacotamento sem publicar

- Localmente: `python tools/empacotar.py` (gera em `dist/`).
- No GitHub: PRs que mexem em `empacotamento/`, `tools/empacotar.py`,
  `tools/baixar_ferramentas.py` ou no `release.yml` já rodam o workflow sem publicar; os pacotes
  ficam como artefatos da execução. Também dá para rodar manualmente em
  **Actions › Release › Run workflow**.
