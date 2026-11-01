import subprocess

import pytest
from PIL import Image
from PySide6.QtCore import QEvent, QEventLoop, Qt, QTimer
from PySide6.QtGui import QKeyEvent

from ags_media_chrono.core.ferramentas import FerramentaNaoEncontrada, localizar
from ags_media_chrono.core.midias import listar_midias
from ags_media_chrono.core.miniaturas import imagem_ampliada
from ags_media_chrono.ui.filtro_galeria import ProxyGaleria
from ags_media_chrono.ui.modelo_midias import ModeloMidias
from ags_media_chrono.ui.visualizador import Visualizador


def _tem_ffmpeg():
    try:
        localizar("ffmpeg")
        return True
    except FerramentaNaoEncontrada:
        return False


def _esperar(sinal, timeout_ms=5000):
    loop = QEventLoop()
    sinal.connect(lambda *_: loop.quit())
    QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec()


def _tecla(janela, tecla):
    janela.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, tecla, Qt.KeyboardModifier.NoModifier))


@pytest.fixture
def pasta(tmp_path):
    Image.new("RGB", (3000, 2000), "red").save(tmp_path / "a.jpg")
    Image.new("RGB", (800, 600), "green").save(tmp_path / "b.HEIC", format="HEIF")
    Image.new("RGB", (400, 300), "blue").save(tmp_path / "c.png")
    if _tem_ffmpeg():
        subprocess.run(
            [str(localizar("ffmpeg")), "-v", "error", "-f", "lavfi", "-i",
             "testsrc=duration=2:size=320x240:rate=10", "-pix_fmt", "yuv420p",
             str(tmp_path / "d.mp4")],
            check=True,
        )  # fmt: skip
    return tmp_path


@pytest.fixture
def modelo(pasta):
    fonte = ModeloMidias()
    fonte.adicionar(list(listar_midias(pasta)))
    proxy = ProxyGaleria()
    proxy.setSourceModel(fonte)
    return proxy


def test_imagem_ampliada_respeita_lado_maximo(pasta):
    [midia] = [m for m in listar_midias(pasta) if m.nome == "a.jpg"]
    imagem = imagem_ampliada(midia, 1500)
    assert imagem.size == (1500, 1000)
    assert imagem.mode == "RGB"


def test_abre_foto_e_carrega_imagem_grande(qapp, modelo):
    v = Visualizador(modelo, 0)
    _esperar(v._sinais.carregada)
    assert v.pilha.currentWidget() is v.tela
    assert v.controles.isHidden()
    assert v.tela.imagem.width() == min(3000, v._lado_max())
    assert v.rotulo_nome.text() == "a.jpg"
    v.close()


def test_navegacao_por_teclado_e_limites(qapp, modelo):
    v = Visualizador(modelo, 0)
    indices = []
    v.indice_alterado.connect(lambda i: indices.append(i.row()))
    _tecla(v, Qt.Key.Key_Right)
    assert v.rotulo_nome.text() == "b.HEIC"
    _tecla(v, Qt.Key.Key_Left)
    _tecla(v, Qt.Key.Key_Left)  # já está no primeiro: continua nele
    assert v.linha == 0
    _tecla(v, Qt.Key.Key_End)
    assert v.linha == modelo.rowCount() - 1
    assert indices == [1, 0, 0, modelo.rowCount() - 1]
    v.close()


def test_navegacao_respeita_filtro(qapp, modelo):
    modelo.definir_texto("c.png")
    v = Visualizador(modelo, 0)
    assert v.total == 1 and v.rotulo_nome.text() == "c.png"
    _tecla(v, Qt.Key.Key_Right)
    assert v.rotulo_nome.text() == "c.png"
    v.close()


@pytest.mark.skipif(not _tem_ffmpeg(), reason="FFmpeg não instalado")
def test_video_usa_player(qapp, modelo):
    v = Visualizador(modelo, modelo.rowCount() - 1)
    assert v.rotulo_nome.text() == "d.mp4"
    assert v.pilha.currentWidget() is v.video
    assert not v.controles.isHidden()
    assert v.player.source().toLocalFile().endswith("d.mp4")
    _tecla(v, Qt.Key.Key_Home)  # voltar para foto para o player
    assert v.player.source().isEmpty()
    v.close()
