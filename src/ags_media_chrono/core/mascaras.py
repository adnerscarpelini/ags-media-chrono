"""Motor de máscaras de nome (issue #24).

Máscaras disponíveis:
    {Data}            data no formato AAAA-MM-DD
    {Data[FORMATO]}   FORMATO livre com YYYY, YY, MM, DD, HH, mm, ss
                      (ex.: {Data[YYYY]}, {Data[YYYYMMDD]}, {Data[YYYY-MM-DD_HHmmss]})
    {Nome}            nome original sem extensão
    {Ext}             extensão original sem o ponto
    {Pasta}           nome da pasta do arquivo
    {Tipo}            foto ou video
    #, ##, ####       contador sequencial com zeros à esquerda (largura = quantidade de #)

Ex.: "{Data[YYYY]}_aniversario_{Data[YYYYMMDD]}_####" -> "2026_aniversario_20261101_0001"
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from ags_media_chrono.core.midias import Midia, TipoMidia


class ErroMascara(ValueError):
    pass


# Códigos de data, do mais longo para o mais curto (YYYY antes de YY).
_CODIGOS_DATA = (
    ("YYYY", "%Y"), ("YY", "%y"), ("MM", "%m"), ("DD", "%d"),
    ("HH", "%H"), ("mm", "%M"), ("ss", "%S"),
)  # fmt: skip
_TOKEN = re.compile(r"\{(?P<nome>[A-Za-zÀ-ú]+)(?:\[(?P<formato>[^\]]*)\])?\}")
_CHAVE_SOLTA = re.compile(r"[{}]")
_SEQUENCIA = re.compile(r"#+")
TOKENS = ("Data", "Nome", "Ext", "Pasta", "Tipo")

# Inseridos pelo menu do diálogo: (texto, descrição)
SUGESTOES = (
    ("{Data}", "Data (AAAA-MM-DD)"),
    ("{Data[YYYY]}", "Ano"),
    ("{Data[MM]}", "Mês"),
    ("{Data[DD]}", "Dia"),
    ("{Data[YYYYMMDD]}", "Data compacta (AAAAMMDD)"),
    ("{Data[HHmmss]}", "Hora (HHMMSS)"),
    ("{Data[YYYY-MM-DD_HH-mm-ss]}", "Data e hora"),
    ("{Nome}", "Nome original"),
    ("{Ext}", "Extensão original"),
    ("{Pasta}", "Nome da pasta"),
    ("{Tipo}", "foto / video"),
    ("####", "Sequencial (0001, 0002…)"),
)

CARACTERES_INVALIDOS = set('<>:"/\\|?*')


def formatar_data_mascara(valor: datetime, formato: str) -> str:
    resultado, i = [], 0
    while i < len(formato):
        for codigo, strftime in _CODIGOS_DATA:
            if formato.startswith(codigo, i):
                resultado.append(valor.strftime(strftime))
                i += len(codigo)
                break
        else:
            resultado.append(formato[i])
            i += 1
    return "".join(resultado)


def validar(mascara: str) -> None:
    """Levanta ErroMascara com uma mensagem clara se a máscara tiver problema."""
    if not mascara.strip():
        raise ErroMascara("O modelo de nome está vazio.")
    for m in _TOKEN.finditer(mascara):
        if m["nome"] not in TOKENS:
            sugestao = ", ".join("{" + t + "}" for t in TOKENS)
            raise ErroMascara(f"Máscara desconhecida: {m.group()}. Use {sugestao}.")
        if m["formato"] is not None and m["nome"] != "Data":
            raise ErroMascara(f"Só {{Data}} aceita formato entre colchetes: {m.group()}")
    if _CHAVE_SOLTA.search(_TOKEN.sub("", mascara)):
        raise ErroMascara("Há uma chave { ou } sem par no modelo de nome.")


def usa_data(mascara: str) -> bool:
    return any(m["nome"] == "Data" for m in _TOKEN.finditer(mascara))


class Caixa(StrEnum):
    MANTER = "manter"
    MINUSCULAS = "minusculas"
    MAIUSCULAS = "maiusculas"

    @property
    def rotulo(self) -> str:
        return {"manter": "Manter", "minusculas": "minúsculas", "maiusculas": "MAIÚSCULAS"}[
            self.value
        ]

    def aplicar(self, texto: str) -> str:
        if self == Caixa.MINUSCULAS:
            return texto.lower()
        if self == Caixa.MAIUSCULAS:
            return texto.upper()
        return texto


@dataclass(frozen=True)
class OpcoesNome:
    """Tudo que define o novo nome (exceto a ordem dos arquivos). Serializável (predefinições)."""

    mascara: str = "{Data[YYYYMMDD]}_####"
    inicio: int = 1
    etapa: int = 1
    reiniciar_por_dia: bool = False
    caixa_nome: Caixa = Caixa.MANTER
    caixa_extensao: Caixa = Caixa.MINUSCULAS
    substituir: str = ""
    substituir_por: str = ""
    diferenciar_maiusculas: bool = False
    expressao_regular: bool = False
    remover_acentos: bool = False

    def para_dict(self) -> dict:
        return {k: (v.value if isinstance(v, Caixa) else v) for k, v in self.__dict__.items()}

    @classmethod
    def de_dict(cls, dados: dict) -> OpcoesNome:
        padrao = cls()
        valores = {}
        for campo, atual in padrao.__dict__.items():
            if campo not in dados:
                continue
            bruto = dados[campo]
            try:
                valores[campo] = Caixa(bruto) if isinstance(atual, Caixa) else type(atual)(bruto)
            except (TypeError, ValueError):
                continue
        return cls(**valores)


def remover_acentos(texto: str) -> str:
    """ "Aniversário da Letícia — ação" -> "Aniversario da Leticia — acao"."""
    decomposto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in decomposto if not unicodedata.combining(c))


def _substituir(texto: str, opcoes: OpcoesNome) -> str:
    if not opcoes.substituir:
        return texto
    flags = 0 if opcoes.diferenciar_maiusculas else re.IGNORECASE
    padrao = opcoes.substituir if opcoes.expressao_regular else re.escape(opcoes.substituir)
    try:
        return re.sub(padrao, opcoes.substituir_por, texto, flags=flags)
    except re.error as e:
        raise ErroMascara(f"Expressão regular inválida: {e}") from e


def gerar_nome(midia: Midia, data: datetime | None, contador: int, opcoes: OpcoesNome) -> str:
    """Novo nome completo (com extensão) para uma mídia."""
    caminho = midia.caminho

    def trocar(m: re.Match) -> str:
        nome, formato = m["nome"], m["formato"]
        if nome == "Data":
            if data is None:
                raise ErroMascara("Arquivo sem data para usar em {Data}.")
            return formatar_data_mascara(data, formato or "YYYY-MM-DD")
        if nome == "Nome":
            return caminho.stem
        if nome == "Ext":
            return caminho.suffix.lstrip(".")
        if nome == "Pasta":
            return caminho.parent.name
        return "video" if midia.tipo == TipoMidia.VIDEO else "foto"

    validar(opcoes.mascara)
    # Sequências (#) fora das máscaras {...}: protegidas para não colidir com o texto gerado.
    partes = re.split(r"(\{[^}]*\})", opcoes.mascara)
    base = "".join(
        _TOKEN.sub(trocar, p) if p.startswith("{")
        else _SEQUENCIA.sub(lambda s: str(contador).zfill(len(s.group())), p)
        for p in partes
    )  # fmt: skip
    base = _substituir(base, opcoes)
    if opcoes.remover_acentos:
        base = remover_acentos(base)
    base = opcoes.caixa_nome.aplicar(base).strip()
    if not base:
        raise ErroMascara("O modelo gera um nome vazio.")
    extensao = opcoes.caixa_extensao.aplicar(caminho.suffix)
    return base + extensao


def problema_no_nome(nome: str) -> str | None:
    """Motivo pelo qual o nome não pode ser usado (ou None)."""
    base = nome.rsplit(".", 1)[0] if "." in nome else nome  # ".jpg" -> nome vazio
    if not base.strip(" ."):
        return "Nome vazio"
    invalidos = sorted(set(nome) & CARACTERES_INVALIDOS)
    if invalidos:
        return "Caractere inválido: " + " ".join(invalidos)
    if nome.endswith((" ", ".")):
        return "Nome não pode terminar com espaço ou ponto"
    if len(nome) > 240:
        return "Nome longo demais"
    return None
