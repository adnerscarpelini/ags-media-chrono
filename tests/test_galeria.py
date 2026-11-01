import time
from pathlib import Path

import pytest
from PySide6.QtCore import QSize
from PySide6.QtGui import QImage

from ags_media_chrono.core.midias import Midia, TipoMidia
from ags_media_chrono.ui.galeria import (
    TAMANHO_MAX,
    TAMANHO_MIN,
    DelegadoMiniatura,
    VisaoGaleria,
    formatar_duracao,
)
from ags_media_chrono.ui.modelo_midias import ModeloMidias, PapelDuracao, PapelMiniatura


def _midias(n, tipo=TipoMidia.FOTO, ext=".jpg"):
    return [Midia(Path(f"/fotos/{i:05d}{ext}"), tipo, 1, 0.0) for i in range(n)]


@pytest.mark.parametrize(
    ("segundos", "texto"), [(5, "0:05"), (65.4, "1:05"), (3600, "1:00:00"), (3725, "1:02:05")]
)
def test_formatar_duracao(segundos, texto):
    assert formatar_duracao(segundos) == texto


def test_modelo_miniatura_e_duracao():
    modelo = ModeloMidias()
    [foto, video] = _midias(1) + _midias(1, TipoMidia.VIDEO, ".mov")
    modelo.adicionar([foto, video])
    alterados = []
    modelo.dataChanged.connect(lambda a, b, papeis: alterados.append((a.row(), papeis)))

    imagem = QImage(10, 10, QImage.Format.Format_RGB32)
    modelo.definir_miniatura(foto.caminho, imagem)
    modelo.definir_duracao(video.caminho, 12.5)
    modelo.definir_miniatura(Path("/outra/pasta.jpg"), imagem)  # ignorado

    assert modelo.index(0).data(PapelMiniatura) == imagem
    assert modelo.index(1).data(PapelDuracao) == 12.5
    assert alterados == [(0, [PapelMiniatura]), (1, [PapelDuracao])]


def test_tamanho_da_celula_respeita_limites(qapp):
    grade = VisaoGaleria()
    grade.definir_tamanho(10)
    assert grade.delegado.tamanho == TAMANHO_MIN
    grade.definir_tamanho(10_000)
    assert grade.delegado.tamanho == TAMANHO_MAX
    grade.definir_tamanho(200)
    assert grade.delegado.sizeHint(None, None).width() > 200


def test_encaixar_mantem_proporcao():
    from PySide6.QtCore import QRect

    alvo = DelegadoMiniatura._encaixar(QSize(4000, 3000), QRect(0, 0, 160, 160))
    assert (alvo.width(), alvo.height()) == (160, 120)
    assert alvo.y() == 20  # centralizado verticalmente


def test_grade_com_5000_itens_renderiza_rapido(qapp):
    modelo = ModeloMidias()
    modelo.adicionar(_midias(4000) + _midias(1000, TipoMidia.VIDEO, ".mov"))
    for i in range(0, 5000, 7):
        modelo.definir_miniatura(
            modelo.midia(i).caminho, QImage(160, 120, QImage.Format.Format_RGB32)
        )

    grade = VisaoGaleria()
    grade.setModel(modelo)
    grade.resize(1000, 800)
    grade.show()
    qapp.processEvents()

    barra = grade.verticalScrollBar()
    inicio = time.perf_counter()
    for passo in range(20):
        barra.setValue(barra.maximum() * passo // 19)
        grade.viewport().grab()
    media_ms = (time.perf_counter() - inicio) / 20 * 1000
    assert barra.maximum() > 0
    assert media_ms < 50, f"cada quadro levou {media_ms:.1f} ms"
