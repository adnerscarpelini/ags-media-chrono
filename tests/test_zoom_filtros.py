import time
from pathlib import Path

from PySide6.QtCore import QEventLoop, QPoint, QPointF, Qt, QTimer
from PySide6.QtGui import QWheelEvent

from ags_media_chrono.core.midias import Midia, TipoMidia
from ags_media_chrono.ui.filtro_galeria import Ordenacao, ProxyGaleria
from ags_media_chrono.ui.galeria import PASSO_ZOOM, TAMANHO_PADRAO, VisaoGaleria
from ags_media_chrono.ui.main_window import MainWindow
from ags_media_chrono.ui.modelo_midias import ModeloMidias, PapelMidia, chave_natural


def _m(nome, tipo=TipoMidia.FOTO, tamanho=1, modificado=0.0):
    return Midia(Path("/x") / nome, tipo, tamanho, modificado)


def _nomes(proxy):
    return [proxy.index(i, 0).data(PapelMidia).nome for i in range(proxy.rowCount())]


def _proxy(midias):
    modelo = ModeloMidias()
    modelo.adicionar(midias)
    proxy = ProxyGaleria()
    proxy.setSourceModel(modelo)
    return modelo, proxy


def test_chave_natural():
    nomes = ["IMG_10.jpg", "img_2.jpg", "IMG_1.jpg"]
    assert sorted(nomes, key=chave_natural) == ["IMG_1.jpg", "img_2.jpg", "IMG_10.jpg"]


def test_ordenacao_por_nome_natural_e_decrescente():
    _, proxy = _proxy([_m("IMG_10.jpg"), _m("IMG_2.jpg"), _m("IMG_1.jpg")])
    assert _nomes(proxy) == ["IMG_1.jpg", "IMG_2.jpg", "IMG_10.jpg"]
    proxy.ordenar(Ordenacao.NOME, crescente=False)
    assert _nomes(proxy) == ["IMG_10.jpg", "IMG_2.jpg", "IMG_1.jpg"]


def test_ordenacao_por_data_tipo_e_tamanho():
    _, proxy = _proxy(
        [
            _m("a.mov", TipoMidia.VIDEO, tamanho=30, modificado=300),
            _m("b.jpg", TipoMidia.FOTO, tamanho=10, modificado=100),
            _m("c.heic", TipoMidia.FOTO, tamanho=20, modificado=200),
        ]
    )
    proxy.ordenar(Ordenacao.DATA_MODIFICACAO)
    assert _nomes(proxy) == ["b.jpg", "c.heic", "a.mov"]
    proxy.ordenar(Ordenacao.TIPO)
    assert _nomes(proxy) == ["c.heic", "b.jpg", "a.mov"]  # fotos (por extensão) e depois vídeos
    proxy.ordenar(Ordenacao.TAMANHO, crescente=False)
    assert _nomes(proxy) == ["a.mov", "c.heic", "b.jpg"]


def test_filtros_combinados():
    _, proxy = _proxy(
        [
            _m("festa_01.jpg"),
            _m("festa_02.mov", TipoMidia.VIDEO),
            _m("praia_01.jpg"),
            _m("praia_02.mp4", TipoMidia.VIDEO),
        ]
    )
    proxy.definir_tipo(TipoMidia.VIDEO)
    assert _nomes(proxy) == ["festa_02.mov", "praia_02.mp4"]
    proxy.definir_texto("PRAIA")
    assert _nomes(proxy) == ["praia_02.mp4"]
    proxy.definir_tipo(None)
    assert _nomes(proxy) == ["praia_01.jpg", "praia_02.mp4"]
    assert proxy.filtrando
    proxy.definir_texto("")
    assert not proxy.filtrando and proxy.rowCount() == 4


def test_itens_novos_entram_ordenados_e_filtrados():
    modelo, proxy = _proxy([_m("b.jpg")])
    proxy.definir_tipo(TipoMidia.FOTO)
    modelo.adicionar([_m("a.jpg"), _m("c.mov", TipoMidia.VIDEO)])
    assert _nomes(proxy) == ["a.jpg", "b.jpg"]


def test_ctrl_roda_do_mouse_faz_zoom(qapp):
    grade = VisaoGaleria()
    tamanhos = []
    grade.tamanho_alterado.connect(tamanhos.append)

    def roda(delta, mods):
        evento = QWheelEvent(
            QPointF(10, 10), QPointF(10, 10), QPoint(0, 0), QPoint(0, delta),
            Qt.MouseButton.NoButton, mods, Qt.ScrollPhase.NoScrollPhase, False,
        )  # fmt: skip
        grade.wheelEvent(evento)

    roda(120, Qt.KeyboardModifier.ControlModifier)
    roda(-240, Qt.KeyboardModifier.ControlModifier)
    roda(120, Qt.KeyboardModifier.NoModifier)  # sem Ctrl: só rola
    assert tamanhos == [TAMANHO_PADRAO + PASSO_ZOOM, TAMANHO_PADRAO - PASSO_ZOOM]


def test_zoom_mantem_item_atual_visivel(qapp):
    modelo = ModeloMidias()
    modelo.adicionar([_m(f"{i:05d}.jpg") for i in range(2000)])
    grade = VisaoGaleria()
    grade.setModel(modelo)
    grade.resize(900, 600)
    grade.show()
    qapp.processEvents()
    alvo = modelo.index(1500)
    grade.setCurrentIndex(alvo)
    grade.scrollTo(alvo)
    qapp.processEvents()

    inicio = time.perf_counter()
    grade.definir_tamanho(80)
    duracao_ms = (time.perf_counter() - inicio) * 1000
    qapp.processEvents()
    assert grade.viewport().rect().intersects(grade.visualRect(alvo))
    assert duracao_ms < 150, f"zoom levou {duracao_ms:.0f} ms"


def test_janela_slider_atalhos_e_status(qapp, tmp_path):
    for nome in ("a.jpg", "b.jpg", "c.mov"):
        (tmp_path / nome).write_bytes(b"x")
    janela = MainWindow()
    janela.abrir_pasta(tmp_path)
    loop = QEventLoop()
    janela.carregador.concluido.connect(lambda *_: loop.quit())
    QTimer.singleShot(5000, loop.quit)
    loop.exec()

    janela.slider_zoom.setValue(240)
    assert janela.galeria.grade.tamanho == 240
    janela.galeria.grade.definir_tamanho(100)
    assert janela.slider_zoom.value() == 100

    janela.acao_selecionar_tudo.trigger()
    assert "3 selecionados" in janela.statusBar().currentMessage()
    janela.acoes_tipo[2].trigger()  # só vídeos
    status = janela.statusBar().currentMessage()
    assert "exibindo 1" in status and "2 fotos · 1 vídeo" in status
    janela.acao_limpar_selecao.trigger()
    assert "selecionado" not in janela.statusBar().currentMessage()
