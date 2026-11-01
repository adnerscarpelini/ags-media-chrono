"""Gera os prints do README (assets/captura-*.png) a partir da pasta de demonstração.

Uso:
    python tools/capturar_telas.py

Cria a demonstração (tools/criar_demo.py) numa pasta temporária, abre o app com configurações
temporárias e salva só a janela do app (widget.grab, nunca a tela). A árvore de pastas mostra
apenas a pasta "Fotos" da demonstração e caminhos completos não aparecem — o repositório é
público e eles revelariam pastas e o nome do usuário do computador.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QSettings, QTimer

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tools"))
SAIDA = RAIZ / "assets"

QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, tempfile.mkdtemp())

import criar_demo  # noqa: E402

from ags_media_chrono.app import create_app  # noqa: E402
from ags_media_chrono.core.datas import Origem  # noqa: E402
from ags_media_chrono.core.escolhas import escolha_de_candidata  # noqa: E402
from ags_media_chrono.core.mascaras import OpcoesNome  # noqa: E402
from ags_media_chrono.core.renomear import entrada_para  # noqa: E402
from ags_media_chrono.ui.dialogo_renomear import DialogoRenomear  # noqa: E402
from ags_media_chrono.ui.main_window import MainWindow  # noqa: E402
from ags_media_chrono.ui.modelo_midias import PapelMidia  # noqa: E402


def main() -> int:
    temporaria = Path(tempfile.mkdtemp()) / "Fotos"
    for vizinha in ("Aniversário 2025", "Família", "Natal 2023"):
        (temporaria / vizinha).mkdir(parents=True)
    pasta = temporaria / "Viagem 2024"
    criar_demo.criar(pasta)

    app = create_app([])
    janela = MainWindow()
    janela.resize(1480, 860)
    janela.show()
    janela.abrir_pasta(pasta)
    janela.galeria.grade.definir_tamanho(176)
    painel = janela.painel_pastas
    painel.arvore.setRootIndex(painel.filtro.mapFromSource(painel.modelo.index(str(temporaria))))
    painel.mostrar(pasta)

    def linha(nome: str) -> int:
        modelo = janela.galeria.grade.model()
        return next(
            i for i in range(modelo.rowCount()) if modelo.index(i, 0).data(PapelMidia).nome == nome
        )

    def preparar() -> None:
        modelo = janela.galeria.modelo
        whatsapp = pasta / "IMG-20240315-WA0012.jpg"  # escolhida pela data do nome
        datas = modelo.estado(whatsapp).datas
        do_nome = next(c for c in datas.candidatas if c.origem == Origem.NOME)
        modelo.definir_escolha(whatsapp, escolha_de_candidata(datas, do_nome))
        grade = janela.galeria.grade
        grade.setCurrentIndex(grade.model().index(linha("IMG_4830.MOV"), 0))
        QTimer.singleShot(1200, principal)

    def principal() -> None:
        mensagem = janela.statusBar().currentMessage()
        janela.statusBar().showMessage(mensagem.replace(str(pasta), f"Fotos\\{pasta.name}"))
        QTimer.singleShot(100, lambda: janela.grab().save(str(SAIDA / "captura-principal.png")))
        QTimer.singleShot(300, renomear)

    def renomear() -> None:
        modelo = janela.galeria.modelo
        itens = [
            entrada_para(m, modelo.estado(m.caminho), modelo.opcoes_fuso)
            for m in modelo.midias()
            if modelo.estado(m.caminho).escolha
        ]
        dialogo = DialogoRenomear(itens, janela)
        dialogo.resize(1240, 560)
        dialogo.definir_opcoes(OpcoesNome("{Data[YYYY]}_viagem_{Data[YYYYMMDD]}_####"))
        dialogo.ordenar_por_data()
        dialogo.tabela.setColumnHidden(3, True)  # coluna Pasta: caminho completo
        dialogo.tabela.setColumnWidth(1, 340)
        dialogo.show()

        def salvar() -> None:
            dialogo.grab().save(str(SAIDA / "captura-renomear.png"))
            dialogo.reject()
            janela.close()
            app.quit()

        QTimer.singleShot(600, salvar)

    QTimer.singleShot(5000, preparar)  # tempo para ler datas e gerar miniaturas
    app.exec()
    print(f"Prints salvos em {SAIDA}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
