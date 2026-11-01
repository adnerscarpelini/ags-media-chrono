"""Escolha da data correta de cada arquivo e seu status.

Fluxo: ao ler as datas, a data de captura (se existir) vira a escolha com status SUGERIDA
(decisão de 2026-11-01, issue #14). O usuário pode trocar (ESCOLHIDA). Ao gravar, o status vira
APLICADO ou ERRO (issue #18).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from enum import StrEnum

from ags_media_chrono.core.datas import DataCandidata, DatasArquivo, OpcoesFuso


class Status(StrEnum):
    PENDENTE = "pendente"  # sem data escolhida
    SUGERIDA = "sugerida"  # data de captura pré-selecionada automaticamente
    ESCOLHIDA = "escolhida"  # escolhida/confirmada pelo usuário (ou por regra em lote)
    APLICADO = "aplicado"  # gravada no arquivo
    ERRO = "erro"  # falha ao ler ou gravar

    @property
    def rotulo(self) -> str:
        return {
            Status.PENDENTE: "Pendente",
            Status.SUGERIDA: "Sugerida",
            Status.ESCOLHIDA: "Escolhida",
            Status.APLICADO: "Aplicado",
            Status.ERRO: "Erro",
        }[self]

    @property
    def pronto_para_aplicar(self) -> bool:
        return self in (Status.SUGERIDA, Status.ESCOLHIDA)


class TipoEscolha(StrEnum):
    CANDIDATA = "candidata"  # uma das datas encontradas no arquivo
    ESPECIFICA = "especifica"  # data digitada pelo usuário
    ATUAL = "atual"  # data/hora do momento da escolha


@dataclass(frozen=True)
class Escolha:
    tipo: TipoEscolha
    valor: datetime  # sempre com fuso (instante)
    campo: str | None = None  # campo da candidata, quando tipo == CANDIDATA
    deslocamento: timedelta = timedelta(0)  # ajuste manual (issue #16)
    somente_data: bool = False

    @property
    def final(self) -> datetime:
        """Data que será gravada: valor + deslocamento."""
        return self.valor + self.deslocamento

    def com_deslocamento(self, deslocamento: timedelta) -> Escolha:
        return replace(self, deslocamento=deslocamento)


def escolha_de_candidata(
    datas: DatasArquivo, candidata: DataCandidata, opcoes: OpcoesFuso | None = None
) -> Escolha:
    return Escolha(
        TipoEscolha.CANDIDATA,
        datas.hora_local(candidata, opcoes),
        campo=candidata.campo,
        somente_data=candidata.somente_data,
    )


def fuso_para_escolha_manual(datas: DatasArquivo | None) -> timezone | None:
    """Fuso aplicado a uma data digitada: o de referência do arquivo, senão o do sistema."""
    if datas is not None and (fuso := datas.fuso_referencia()) is not None:
        return timezone(fuso)
    return None


def escolha_especifica(valor: datetime, datas: DatasArquivo | None = None) -> Escolha:
    if valor.tzinfo is None:
        fuso = fuso_para_escolha_manual(datas)
        valor = valor.replace(tzinfo=fuso) if fuso else valor.astimezone()
    return Escolha(TipoEscolha.ESPECIFICA, valor)


def escolha_atual(datas: DatasArquivo | None = None) -> Escolha:
    fuso = fuso_para_escolha_manual(datas)
    agora = datetime.now(fuso) if fuso else datetime.now().astimezone()
    return Escolha(TipoEscolha.ATUAL, agora.replace(microsecond=0))


@dataclass
class EstadoMidia:
    """Tudo que o app sabe sobre as datas de um arquivo nesta sessão."""

    datas: DatasArquivo | None = None  # None = ainda não lido
    escolha: Escolha | None = None
    status: Status = Status.PENDENTE
    mensagem: str = ""  # detalhe do erro, se houver

    @property
    def lido(self) -> bool:
        return self.datas is not None

    def receber_datas(self, datas: DatasArquivo, opcoes: OpcoesFuso | None = None) -> None:
        """Guarda as datas lidas e aplica a sugestão, sem sobrescrever escolha do usuário."""
        self.datas = datas
        if datas.erro:
            self.status, self.mensagem = Status.ERRO, datas.erro
            return
        if self.escolha is not None:
            return
        sugerida = datas.captura_sugerida()
        if sugerida is not None:
            self.escolha = escolha_de_candidata(datas, sugerida, opcoes)
            self.status = Status.SUGERIDA

    def escolher(self, escolha: Escolha | None) -> None:
        self.escolha = escolha
        self.status = Status.ESCOLHIDA if escolha else Status.PENDENTE
        self.mensagem = ""
