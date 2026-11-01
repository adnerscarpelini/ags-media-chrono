from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QEventLoop, QTimer

from ags_media_chrono.core.escolhas import EstadoMidia, escolha_especifica
from ags_media_chrono.core.historico import listar_operacoes
from ags_media_chrono.core.mascaras import OpcoesNome
from ags_media_chrono.core.midias import Midia, TipoMidia
from ags_media_chrono.core.renomear import ItemEntrada, OrigemData, entrada_para
from ags_media_chrono.ui.dialogo_renomear import DialogoRenomear
from ags_media_chrono.ui.main_window import MainWindow

D1 = datetime(2026, 11, 1, 20, 0).astimezone()
D2 = datetime(2026, 10, 28, 10, 0).astimezone()


def _itens(pasta, nomes_datas):
    itens = []
    for nome, data in nomes_datas:
        caminho = pasta / nome
        caminho.write_bytes(nome.encode())
        itens.append(ItemEntrada(Midia(caminho, TipoMidia.FOTO, 1, 0), data, OrigemData.ESCOLHIDA))
    return itens


def test_entrada_para_escolhe_a_melhor_data(tmp_path):
    midia = Midia(tmp_path / "a.jpg", TipoMidia.FOTO, 1, 1_700_000_000)
    assert entrada_para(midia, None).origem_data == OrigemData.MODIFICACAO
    estado = EstadoMidia()
    estado.escolher(escolha_especifica(D1))
    item = entrada_para(midia, estado)
    assert item.origem_data == OrigemData.ESCOLHIDA and item.data == D1


def test_dialogo_previa_conflitos_e_ordem(qapp, tmp_path):
    itens = _itens(tmp_path, [("b.jpg", D1), ("a.jpg", D2)])
    dialogo = DialogoRenomear(itens)
    dialogo.definir_opcoes(OpcoesNome("{Data[YYYYMMDD]}_##"))
    assert [p.destino.name for p in dialogo.plano] == ["20261101_01.jpg", "20261028_02.jpg"]
    assert dialogo.botao_renomear.isEnabled()

    dialogo.ordenar_por_data()
    assert [p.destino.name for p in dialogo.plano] == ["20261028_01.jpg", "20261101_02.jpg"]

    dialogo.tabela.selectRow(1)
    dialogo._mover(-1)
    assert dialogo.itens[0].midia.caminho.name == "b.jpg"

    dialogo.campo_mascara.setEditText("mesmo")
    dialogo.atualizar_previa()
    assert not dialogo.botao_renomear.isEnabled()
    assert "problema" in dialogo.resumo.text()

    dialogo._modelo_do_nome(0, 0)  # duplo clique no nome antigo
    assert dialogo.campo_mascara.currentText() == "b"


def test_dialogo_opcoes_e_predefinicoes(qapp, tmp_path):
    itens = _itens(tmp_path, [("Ação.JPG", D1)])
    dialogo = DialogoRenomear(itens)
    opcoes = OpcoesNome("{Nome}_x", caixa_nome="maiusculas", remover_acentos=True,
                        substituir="_X", substituir_por="-Y")  # fmt: skip
    dialogo.definir_opcoes(OpcoesNome.de_dict(opcoes.para_dict()))
    assert dialogo.plano[0].destino.name == "ACAO-Y.jpg"
    dialogo.salvar_predefinicao("Minha")
    novo = DialogoRenomear(itens)
    indice = novo.combo_predefinicao.findData("Minha")
    novo._carregar_predefinicao(indice)
    assert novo.opcoes() == dialogo.opcoes()


def _esperar_carregar(janela):
    loop = QEventLoop()
    janela.carregador.concluido.connect(lambda *_: loop.quit())
    QTimer.singleShot(10_000, loop.quit)
    loop.exec()


def test_renomear_e_desfazer_pela_janela(qapp, tmp_path):
    for nome in ("x.jpg", "y.jpg"):
        (tmp_path / nome).write_bytes(nome.encode())
    janela = MainWindow()
    janela.abrir_pasta(tmp_path)
    _esperar_carregar(janela)
    modelo = janela.galeria.modelo
    modelo.definir_escolha(tmp_path / "x.jpg", escolha_especifica(D1))
    assert janela.acao_renomear.isEnabled()

    itens = [entrada_para(m, modelo.estado(m.caminho)) for m in modelo.midias()]
    dialogo = DialogoRenomear(itens)
    dialogo.definir_opcoes(OpcoesNome("festa_#"))
    assert janela.renomear_em_lote(dialogo)

    assert sorted(p.name for p in tmp_path.iterdir()) == ["festa_1.jpg", "festa_2.jpg"]
    nomes = sorted(m.nome for m in modelo.midias())
    assert nomes == ["festa_1.jpg", "festa_2.jpg"]
    # o estado (escolha) acompanha o arquivo renomeado
    assert modelo.estado(tmp_path / "festa_1.jpg").escolha.final == D1

    assert janela.desfazer_ultima(confirmar=False)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["x.jpg", "y.jpg"]
    assert modelo.estado(Path(tmp_path / "x.jpg")).escolha.final == D1
    assert listar_operacoes()[0].desfeita
    janela.close()
