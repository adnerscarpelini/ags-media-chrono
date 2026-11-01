"""Plano e execução da renomeação em lote (issues #25–#28).

Execução segura em duas etapas: primeiro todos os arquivos vão para nomes temporários únicos,
depois para os nomes finais. Assim trocas (A->B, B->A) funcionam, e se algo falhar no meio o
que já foi feito é revertido.
"""

from __future__ import annotations

import os
import sys
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path

from ags_media_chrono.core.historico import Operacao, TipoOperacao
from ags_media_chrono.core.mascaras import (
    ErroMascara,
    OpcoesNome,
    gerar_nome,
    problema_no_nome,
    usa_data,
)
from ags_media_chrono.core.midias import Midia

DIFERENCIA_MAIUSCULAS = sys.platform != "win32"  # NTFS ignora maiúsculas/minúsculas


class OrigemData(StrEnum):
    ESCOLHIDA = "escolhida"
    CAPTURA = "captura"
    MODIFICACAO = "modificação do arquivo"
    NENHUMA = "sem data"


@dataclass(frozen=True)
class ItemEntrada:
    midia: Midia
    data: datetime | None
    origem_data: OrigemData


@dataclass
class ItemPlano:
    origem: Path
    destino: Path
    data: datetime | None
    origem_data: OrigemData
    problema: str | None = None

    @property
    def muda(self) -> bool:
        # Compara o texto: no Windows, Path("IMG.JPG") == Path("img.jpg").
        return str(self.origem) != str(self.destino)

    @property
    def ok(self) -> bool:
        return self.problema is None


def _chave(caminho: Path) -> str:
    texto = os.path.normpath(str(caminho))
    return texto if DIFERENCIA_MAIUSCULAS else texto.casefold()


def planejar(itens: list[ItemEntrada], opcoes: OpcoesNome) -> list[ItemPlano]:
    """Calcula os novos nomes na ordem dada e marca os problemas (sem tocar em nada)."""
    plano: list[ItemPlano] = []
    contador = opcoes.inicio
    dia_atual = None
    precisa_data = usa_data(opcoes.mascara)
    for item in itens:
        if opcoes.reiniciar_por_dia and item.data is not None:
            dia = item.data.date()
            if dia != dia_atual:
                contador, dia_atual = opcoes.inicio, dia
        try:
            if precisa_data and item.data is None:
                raise ErroMascara("Sem data para {Data}")
            nome = gerar_nome(item.midia, item.data, contador, opcoes)
            problema = problema_no_nome(nome)
        except ErroMascara as e:
            nome, problema = item.midia.caminho.name, str(e)
        plano.append(
            ItemPlano(item.midia.caminho, item.midia.caminho.with_name(nome), item.data,
                      item.origem_data, problema)
        )  # fmt: skip
        contador += opcoes.etapa
    _marcar_conflitos(plano)
    return plano


def _marcar_conflitos(plano: list[ItemPlano]) -> None:
    origens = {_chave(p.origem) for p in plano}
    destinos: dict[str, ItemPlano] = {}
    for p in plano:
        if not p.ok:
            continue
        chave = _chave(p.destino)
        if chave in destinos:
            primeiro = destinos[chave]
            p.problema = f"Nome repetido (igual a {primeiro.origem.name})"
            primeiro.problema = primeiro.problema or f"Nome repetido (igual a {p.origem.name})"
            continue
        destinos[chave] = p
        # Destino já existe e não é um dos arquivos do lote: conflito. Comparar com as origens
        # permite trocas (A->B, B->A) e, no Windows, mudar só maiúsculas/minúsculas.
        if p.muda and chave not in origens and p.destino.exists():
            p.problema = "Já existe um arquivo com este nome na pasta"


@dataclass
class ResultadoRenomeacao:
    operacao: Operacao
    erro: str | None = None  # erro que interrompeu (e foi revertido)


def _mover(origem: Path, destino: Path, tentativas: int = 20, espera: float = 0.1) -> None:
    """os.rename com novas tentativas: no Windows o arquivo pode estar aberto por um instante
    (ex.: miniatura ou leitura de datas em segundo plano) e a renomeação falha com
    PermissionError. Outros erros não são repetidos."""
    for tentativa in range(tentativas):
        try:
            os.rename(origem, destino)
            return
        except PermissionError:
            if tentativa == tentativas - 1:
                raise
            time.sleep(espera)


def _executar(
    pares: list[tuple[Path, Path]],
    progresso: Callable[[int, int, Path], None] | None,
) -> str | None:
    """Renomeia em duas etapas; em caso de erro desfaz o que já foi feito e retorna o erro."""
    temporarios: list[tuple[Path, Path, Path]] = []  # (origem, temporário, destino)
    finalizados: list[tuple[Path, Path, Path]] = []
    try:
        for origem, destino in pares:
            temporario = origem.with_name(f".ags-renomear-{uuid.uuid4().hex[:12]}{origem.suffix}")
            _mover(origem, temporario)
            temporarios.append((origem, temporario, destino))
        for i, (origem, temporario, destino) in enumerate(temporarios, start=1):
            if progresso:
                progresso(i, len(temporarios), origem)
            if destino.exists():
                raise FileExistsError(f"{destino.name} já existe")
            _mover(temporario, destino)
            finalizados.append((origem, temporario, destino))
        return None
    except OSError as e:
        for _origem, temporario, destino in reversed(finalizados):
            _mover(destino, temporario)
        for origem, temporario, _destino in reversed(temporarios):
            if temporario.exists():
                _mover(temporario, origem)
        return str(e)


def renomear(
    plano: list[ItemPlano], progresso: Callable[[int, int, Path], None] | None = None
) -> ResultadoRenomeacao:
    """Executa o plano (só itens válidos que mudam) e salva no histórico."""
    pares = [(p.origem, p.destino) for p in plano if p.ok and p.muda]
    operacao = Operacao(TipoOperacao.RENOMEAR)
    if not pares:
        return ResultadoRenomeacao(operacao, "Nenhum arquivo para renomear")
    erro = _executar(pares, progresso)
    operacao.entradas = [
        {"de": str(o), "para": str(d), "ok": erro is None, "mensagem": erro or ""} for o, d in pares
    ]
    if erro is None:
        operacao.salvar()
    return ResultadoRenomeacao(operacao, erro)


def desfazer_renomeacao(operacao: Operacao) -> str | None:
    pares = [(Path(e["para"]), Path(e["de"])) for e in operacao.entradas if e.get("ok")]
    faltando = [o.name for o, _ in pares if not o.exists()]
    if faltando:
        return "Arquivo(s) não encontrado(s): " + ", ".join(faltando[:5])
    erro = _executar(pares, None)
    if erro is None:
        operacao.desfeita = True
        operacao.salvar()
    return erro


def entrada_para(midia: Midia, estado, opcoes_fuso=None) -> ItemEntrada:
    """Data usada nas máscaras: escolhida > captura sugerida > modificação do arquivo."""
    if estado is not None and estado.escolha is not None:
        return ItemEntrada(midia, estado.escolha.final, OrigemData.ESCOLHIDA)
    if estado is not None and estado.datas is not None:
        sugerida = estado.datas.captura_sugerida()
        if sugerida is not None:
            hora = estado.datas.hora_local(sugerida, opcoes_fuso)
            return ItemEntrada(midia, hora, OrigemData.CAPTURA)
    if midia.modificado:
        modificacao = datetime.fromtimestamp(midia.modificado).astimezone()
        return ItemEntrada(midia, modificacao, OrigemData.MODIFICACAO)
    return ItemEntrada(midia, None, OrigemData.NENHUMA)
