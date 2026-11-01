"""Wrapper do ExifTool em modo -stay_open.

Um único processo ExifTool fica aberto e recebe comandos pelo stdin (`-@ -`). Cada comando
termina com `-execute<N>`; o ExifTool responde no stdout e finaliza com `{ready<N>}`. Para o
stderr usamos `-echo4 {ready<N>}`, assim sabemos onde termina a saída de erro de cada comando.

stdout e stderr são lidos por threads próprias para evitar travamento quando um dos pipes enche.
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from ags_media_chrono.core.ferramentas import localizar

TIMEOUT_PADRAO = 120.0
# Argumentos aplicados a todos os comandos: nomes de arquivo em UTF-8 (necessário no Windows
# para caminhos com acentos).
ARGS_COMUNS = ("-charset", "filename=utf8")


class ErroExifTool(Exception):
    pass


@dataclass
class Saida:
    stdout: str
    stderr: str


@dataclass
class ResultadoLeitura:
    arquivo: Path
    tags: dict[str, object] = field(default_factory=dict)
    erro: str | None = None

    @property
    def ok(self) -> bool:
        return self.erro is None


@dataclass
class ResultadoEscrita:
    arquivo: Path
    ok: bool
    alterado: bool
    erros: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)


def _chave(caminho: str | Path) -> str:
    return os.path.normcase(os.path.abspath(caminho))


def _ler_stream(stream, fila: queue.Queue) -> None:
    for linha in iter(stream.readline, b""):
        fila.put(linha)
    fila.put(None)  # EOF: processo terminou


class ExifTool:
    """Processo ExifTool persistente. Use como context manager ou chame iniciar()/fechar()."""

    def __init__(self, executavel: Path | None = None) -> None:
        self.executavel = Path(executavel) if executavel else localizar("exiftool")
        self._processo: subprocess.Popen | None = None
        self._fila_out: queue.Queue = queue.Queue()
        self._fila_err: queue.Queue = queue.Queue()
        self._contador = 0
        self._lock = threading.Lock()

    # --- ciclo de vida -------------------------------------------------------------------

    @property
    def ativo(self) -> bool:
        return self._processo is not None and self._processo.poll() is None

    @property
    def pid(self) -> int | None:
        return self._processo.pid if self._processo else None

    def iniciar(self) -> None:
        if self.ativo:
            return
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        self._processo = subprocess.Popen(
            [str(self.executavel), "-stay_open", "True", "-@", "-"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=flags,
        )
        self._fila_out = queue.Queue()
        self._fila_err = queue.Queue()
        for stream, fila in (
            (self._processo.stdout, self._fila_out),
            (self._processo.stderr, self._fila_err),
        ):
            threading.Thread(target=_ler_stream, args=(stream, fila), daemon=True).start()

    def fechar(self) -> None:
        if not self._processo:
            return
        try:
            if self.ativo:
                self._processo.stdin.write(b"-stay_open\nFalse\n")
                self._processo.stdin.flush()
                self._processo.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            self._processo.kill()
        finally:
            self._processo = None

    def __enter__(self) -> ExifTool:
        self.iniciar()
        return self

    def __exit__(self, *_exc) -> None:
        self.fechar()

    def versao(self) -> str:
        return self.executar("-ver").stdout.strip()

    # --- execução ------------------------------------------------------------------------

    def executar(self, *args: str, timeout: float = TIMEOUT_PADRAO) -> Saida:
        """Executa um comando e retorna stdout/stderr completos."""
        stdout, stderr = self._executar_bruto(args, timeout)
        return Saida(stdout.decode("utf-8", errors="replace"), stderr)

    def extrair_binario(
        self, arquivo: str | Path, tag: str, *, timeout: float = TIMEOUT_PADRAO
    ) -> bytes:
        """Retorna o conteúdo binário de uma tag (ex.: PreviewImage) ou b"" se não existir."""
        stdout, _ = self._executar_bruto(("-b", f"-{tag}", str(Path(arquivo).absolute())), timeout)
        return stdout

    def _executar_bruto(self, args: Sequence[str], timeout: float) -> tuple[bytes, str]:
        for arg in args:
            if "\n" in arg or "\r" in arg:
                raise ValueError(f"Argumento com quebra de linha não é permitido: {arg!r}")

        with self._lock:
            self.iniciar()
            self._contador += 1
            marcador = f"{{ready{self._contador}}}".encode()
            linhas = [*ARGS_COMUNS, *args, "-echo4", marcador.decode()]
            linhas.append(f"-execute{self._contador}")
            try:
                self._processo.stdin.write(("\n".join(linhas) + "\n").encode("utf-8"))
                self._processo.stdin.flush()
                stdout = self._coletar(self._fila_out, marcador, timeout)
                stderr = self._coletar(self._fila_err, marcador, timeout)
            except (OSError, ErroExifTool) as e:
                self._abortar()
                raise ErroExifTool(f"Falha ao comunicar com o ExifTool: {e}") from e
        return stdout, stderr.decode("utf-8", errors="replace")

    def _coletar(self, fila: queue.Queue, marcador: bytes, timeout: float) -> bytes:
        partes: list[bytes] = []
        while True:
            try:
                linha = fila.get(timeout=timeout)
            except queue.Empty:
                raise ErroExifTool(f"tempo esgotado ({timeout:.0f}s)") from None
            if linha is None:
                raise ErroExifTool("o processo foi encerrado inesperadamente")
            # O marcador pode vir colado ao fim da última linha se ela não terminar com \n
            # (sempre o caso em saídas binárias com -b).
            sem_quebra = linha.rstrip(b"\r\n")
            if sem_quebra.endswith(marcador):
                partes.append(sem_quebra[: -len(marcador)])
                return b"".join(partes)
            partes.append(linha)

    def _abortar(self) -> None:
        if self._processo:
            self._processo.kill()
            self._processo = None

    # --- leitura -------------------------------------------------------------------------

    def ler(
        self,
        arquivos: Iterable[str | Path],
        tags: Sequence[str] = (),
        *,
        lote: int = 200,
        progresso: Callable[[int, int], None] | None = None,
    ) -> list[ResultadoLeitura]:
        """Lê metadados (grupos G1, todas as ocorrências, valores sem conversão de data).

        `tags` limita os campos lidos (ex.: ["DateTimeOriginal", "QuickTime:CreateDate"]).
        Retorna um resultado por arquivo, na mesma ordem; arquivos com problema vêm com `erro`.
        """
        caminhos = [Path(a) for a in arquivos]
        resultados: list[ResultadoLeitura] = []
        args_tags = [f"-{t}" for t in tags]

        for inicio in range(0, len(caminhos), lote):
            parte = caminhos[inicio : inicio + lote]
            saida = self.executar(
                "-json", "-G1", "-a", "-s", *args_tags, *(str(c.absolute()) for c in parte)
            )
            resultados.extend(self._montar_leitura(parte, saida))
            if progresso:
                progresso(len(resultados), len(caminhos))
        return resultados

    @staticmethod
    def _montar_leitura(parte: list[Path], saida: Saida) -> list[ResultadoLeitura]:
        try:
            dados = json.loads(saida.stdout) if saida.stdout.strip() else []
        except json.JSONDecodeError as e:
            raise ErroExifTool(f"JSON inválido do ExifTool: {e}") from e

        por_arquivo = {_chave(d.get("SourceFile", "")): d for d in dados}
        # Mensagens no formato "Error: <motivo> - <caminho>" (o ExifTool usa "/" no Windows).
        erros_stderr = {
            _chave(ln.rsplit(" - ", 1)[1]): ln.strip()
            for ln in saida.stderr.splitlines()
            if ln.startswith("Error") and " - " in ln
        }

        resultados = []
        for caminho in parte:
            chave = _chave(caminho.absolute())
            d = por_arquivo.get(chave)
            if d is None:
                msg = erros_stderr.get(chave, "Arquivo não lido")
                resultados.append(ResultadoLeitura(caminho, erro=msg))
                continue
            d = dict(d)
            d.pop("SourceFile", None)
            erro = d.get("ExifTool:Error")
            resultados.append(ResultadoLeitura(caminho, tags=d, erro=erro))
        return resultados

    # --- escrita -------------------------------------------------------------------------

    def gravar(
        self,
        arquivo: str | Path,
        valores: dict[str, str],
        *,
        backup: bool = False,
        args_extras: Sequence[str] = (),
    ) -> ResultadoEscrita:
        """Grava `valores` ({tag: valor}) em um arquivo.

        Sem backup usa -overwrite_original; com backup o ExifTool mantém `<arquivo>_original`.
        """
        caminho = Path(arquivo)
        args = [f"-{tag}={valor}" for tag, valor in valores.items()]
        if not backup:
            args.append("-overwrite_original")
        saida = self.executar(*args, *args_extras, str(caminho.absolute()))
        return self._montar_escrita(caminho, saida)

    def gravar_lote(
        self,
        itens: Iterable[tuple[str | Path, dict[str, str]]],
        *,
        backup: bool = False,
        progresso: Callable[[int, int], None] | None = None,
        cancelado: Callable[[], bool] | None = None,
    ) -> list[ResultadoEscrita]:
        """Grava valores diferentes em vários arquivos usando o mesmo processo."""
        lista = list(itens)
        resultados = []
        for i, (arquivo, valores) in enumerate(lista, start=1):
            if cancelado and cancelado():
                break
            resultados.append(self.gravar(arquivo, valores, backup=backup))
            if progresso:
                progresso(i, len(lista))
        return resultados

    @staticmethod
    def _montar_escrita(caminho: Path, saida: Saida) -> ResultadoEscrita:
        erros = [ln.strip() for ln in saida.stderr.splitlines() if ln.startswith("Error")]
        avisos = [ln.strip() for ln in saida.stderr.splitlines() if ln.startswith("Warning")]
        alterado = "1 image files updated" in saida.stdout
        inalterado = "1 image files unchanged" in saida.stdout
        ok = not erros and (alterado or inalterado)
        if not ok and not erros:
            erros = [saida.stdout.strip() or "Falha desconhecida ao gravar"]
        return ResultadoEscrita(caminho, ok=ok, alterado=alterado, erros=erros, avisos=avisos)
