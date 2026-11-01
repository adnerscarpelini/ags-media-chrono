"""Escolha de datas em lote por regra de prioridade (issue #15).

Uma regra é uma lista ordenada de critérios: para cada arquivo, o primeiro critério que
encontrar uma data define a escolha. Ex.: captura -> nome do arquivo -> mais antiga.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from ags_media_chrono.core.datas import DataCandidata, DatasArquivo, OpcoesFuso, Origem
from ags_media_chrono.core.escolhas import Escolha, EstadoMidia, Status, escolha_de_candidata


class Criterio(StrEnum):
    CAPTURA = "captura"
    NOME = "nome"
    MAIS_ANTIGA_METADADOS = "mais_antiga_metadados"
    CRIACAO_ARQUIVO = "criacao_arquivo"
    MODIFICACAO_ARQUIVO = "modificacao_arquivo"
    MAIS_ANTIGA = "mais_antiga"

    @property
    def rotulo(self) -> str:
        return {
            Criterio.CAPTURA: "Data de captura (metadados)",
            Criterio.NOME: "Data no nome do arquivo",
            Criterio.MAIS_ANTIGA_METADADOS: "Mais antiga dos metadados (sem datas do arquivo)",
            Criterio.CRIACAO_ARQUIVO: "Data de criação do arquivo",
            Criterio.MODIFICACAO_ARQUIVO: "Data de modificação do arquivo",
            Criterio.MAIS_ANTIGA: "Mais antiga de todas",
        }[self]


class Alvo(StrEnum):
    PENDENTES = "pendentes"
    PENDENTES_E_SUGERIDAS = "pendentes_e_sugeridas"
    TODOS = "todos"

    @property
    def rotulo(self) -> str:
        return {
            Alvo.PENDENTES: "Só arquivos sem data escolhida",
            Alvo.PENDENTES_E_SUGERIDAS: "Sem data e com data sugerida (mantém escolhas manuais)",
            Alvo.TODOS: "Todos (substitui inclusive escolhas manuais)",
        }[self]

    def inclui(self, status: Status) -> bool:
        if self == Alvo.TODOS:
            return status != Status.ERRO
        if self == Alvo.PENDENTES_E_SUGERIDAS:
            return status in (Status.PENDENTE, Status.SUGERIDA)
        return status == Status.PENDENTE


@dataclass
class Regra:
    criterios: list[Criterio] = field(
        default_factory=lambda: [Criterio.CAPTURA, Criterio.NOME, Criterio.MAIS_ANTIGA]
    )
    alvo: Alvo = Alvo.PENDENTES_E_SUGERIDAS

    def para_dict(self) -> dict:
        return {"criterios": [c.value for c in self.criterios], "alvo": self.alvo.value}

    @classmethod
    def de_dict(cls, dados: dict) -> Regra:
        """Lê uma regra salva; valores desconhecidos (versões antigas/futuras) são ignorados."""
        validos = {c.value for c in Criterio}
        criterios = [Criterio(c) for c in dados.get("criterios", []) if c in validos]
        try:
            alvo = Alvo(dados.get("alvo"))
        except ValueError:
            alvo = Alvo.PENDENTES_E_SUGERIDAS
        return cls(criterios or Regra().criterios, alvo)


def _mais_antiga(
    datas: DatasArquivo, candidatas: list[DataCandidata], opcoes
) -> DataCandidata | None:
    return min(candidatas, key=lambda c: datas.instante(c, opcoes)) if candidatas else None


def candidata_do_criterio(
    datas: DatasArquivo, criterio: Criterio, opcoes: OpcoesFuso | None = None
) -> DataCandidata | None:
    todas = datas.candidatas
    if criterio == Criterio.CAPTURA:
        return datas.captura_sugerida()
    if criterio == Criterio.NOME:
        return next((c for c in todas if c.origem == Origem.NOME), None)
    if criterio == Criterio.CRIACAO_ARQUIVO:
        return next((c for c in todas if c.campo == "System:FileCreateDate"), None)
    if criterio == Criterio.MODIFICACAO_ARQUIVO:
        return next((c for c in todas if c.campo == "System:FileModifyDate"), None)
    if criterio == Criterio.MAIS_ANTIGA_METADADOS:
        metadados = [c for c in todas if c.origem not in (Origem.ARQUIVO, Origem.NOME)]
        return _mais_antiga(datas, metadados, opcoes)
    return _mais_antiga(datas, todas, opcoes)


def escolha_por_regra(
    datas: DatasArquivo, criterios: list[Criterio], opcoes: OpcoesFuso | None = None
) -> Escolha | None:
    for criterio in criterios:
        if (candidata := candidata_do_criterio(datas, criterio, opcoes)) is not None:
            return escolha_de_candidata(datas, candidata, opcoes)
    return None


@dataclass
class ResultadoRegra:
    escolhas: dict = field(default_factory=dict)  # caminho -> Escolha
    sem_data: list = field(default_factory=list)  # caminhos sem nenhum critério atendido
    ignorados: int = 0  # fora do alvo (ex.: escolha manual preservada)
    nao_lidos: int = 0  # datas ainda não lidas


def simular_regra(estados: dict, regra: Regra, opcoes: OpcoesFuso | None = None) -> ResultadoRegra:
    """Calcula o que a regra faria, sem alterar nada. `estados`: caminho -> EstadoMidia."""
    resultado = ResultadoRegra()
    for caminho, estado in estados.items():
        estado: EstadoMidia
        if estado.datas is None:
            resultado.nao_lidos += 1
            continue
        if not regra.alvo.inclui(estado.status):
            resultado.ignorados += 1
            continue
        escolha = escolha_por_regra(estado.datas, regra.criterios, opcoes)
        if escolha is None:
            resultado.sem_data.append(caminho)
        else:
            if estado.escolha is not None:
                escolha = escolha.com_deslocamento(estado.escolha.deslocamento)
            resultado.escolhas[caminho] = escolha
    return resultado
