"""Histórico de alterações (para desfazer): um arquivo JSON por operação.

Fica na pasta de dados do usuário, não nas pastas de fotos:
- Windows: %LOCALAPPDATA%\\ags-media-chrono\\historico
- Linux:   ~/.local/share/ags-media-chrono/historico (ou $XDG_DATA_HOME)
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path


class TipoOperacao:
    DATAS = "datas"
    RENOMEAR = "renomear"


def pasta_dados() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / "ags-media-chrono"


def pasta_historico() -> Path:
    return pasta_dados() / "historico"


@dataclass
class Operacao:
    tipo: str
    entradas: list[dict] = field(default_factory=list)
    quando: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    id: str = field(default_factory=lambda: datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
    desfeita: bool = False

    @property
    def caminho(self) -> Path:
        return pasta_historico() / f"{self.id}-{self.tipo}.json"

    @property
    def quantidade_ok(self) -> int:
        return sum(1 for e in self.entradas if e.get("ok"))

    def salvar(self) -> Path:
        destino = self.caminho
        destino.parent.mkdir(parents=True, exist_ok=True)
        temporario = destino.with_suffix(".tmp")
        temporario.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=1), "utf-8")
        os.replace(temporario, destino)
        return destino

    @classmethod
    def carregar(cls, caminho: Path) -> Operacao:
        dados = json.loads(caminho.read_text("utf-8"))
        return cls(**{k: dados[k] for k in ("tipo", "entradas", "quando", "id", "desfeita")})


def listar_operacoes(tipo: str | None = None) -> list[Operacao]:
    """Operações salvas, da mais recente para a mais antiga (arquivos corrompidos são ignorados)."""
    pasta = pasta_historico()
    if not pasta.is_dir():
        return []
    operacoes = []
    for arquivo in sorted(pasta.glob("*.json"), reverse=True):
        try:
            operacao = Operacao.carregar(arquivo)
        except (OSError, ValueError, KeyError, TypeError):
            continue
        if tipo is None or operacao.tipo == tipo:
            operacoes.append(operacao)
    return operacoes
