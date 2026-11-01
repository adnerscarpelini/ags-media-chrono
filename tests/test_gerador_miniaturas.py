from PIL import Image
from PySide6.QtCore import QEventLoop, QTimer

from ags_media_chrono.core.midias import listar_midias
from ags_media_chrono.core.miniaturas import CacheMiniaturas
from ags_media_chrono.ui.gerador_miniaturas import GeradorMiniaturas
from ags_media_chrono.ui.modelo_midias import ModeloMidias, PapelMiniatura


def _fotos(pasta, n):
    for i in range(n):
        Image.new("RGB", (640, 480), (i * 20 % 255, 100, 150)).save(pasta / f"{i:03d}.jpg")
    (pasta / "quebrada.jpg").write_bytes(b"x")
    return list(listar_midias(pasta))


def _esperar(gerador, total, timeout_ms=15_000):
    recebidos = []
    loop = QEventLoop()

    def contar(*args):
        recebidos.append(args)
        if len(recebidos) >= total:
            loop.quit()

    gerador.pronta.connect(contar)
    gerador.falhou.connect(contar)
    QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec()
    return recebidos


def test_gera_em_segundo_plano_e_reaproveita_cache(qapp, tmp_path):
    pasta = tmp_path / "fotos"
    pasta.mkdir()
    midias = _fotos(pasta, 8)
    cache = CacheMiniaturas(tmp_path / "cache")

    gerador = GeradorMiniaturas(cache=cache)
    gerador.nova_geracao()
    gerador.pre_carregar(midias)
    _esperar(gerador, len(midias))
    gerador.fechar()
    assert gerador.estatisticas == {"cache": 0, "geradas": 8, "falhas": 1}

    # Segunda abertura (novo gerador, mesmo cache): nada é gerado de novo
    gerador2 = GeradorMiniaturas(cache=cache)
    gerador2.nova_geracao()
    gerador2.pre_carregar(midias)
    _esperar(gerador2, len(midias))
    gerador2.fechar()
    assert gerador2.estatisticas == {"cache": 8, "geradas": 0, "falhas": 1}


def test_arquivo_com_falha_nao_e_pedido_de_novo(qapp, tmp_path):
    midias = _fotos(tmp_path, 0)
    gerador = GeradorMiniaturas(cache=CacheMiniaturas(tmp_path / "cache"))
    gerador.nova_geracao()
    gerador.solicitar(midias[0])
    _esperar(gerador, 1)
    gerador.solicitar(midias[0])
    gerador.fechar()
    assert gerador.estatisticas["falhas"] == 1


def test_troca_de_geracao_descarta_resultados(qapp, tmp_path):
    midias = _fotos(tmp_path, 3)
    gerador = GeradorMiniaturas(cache=CacheMiniaturas(tmp_path / "cache"))
    geracao_antiga = gerador.nova_geracao()
    gerador.pre_carregar(midias)
    gerador.nova_geracao()
    resultados = _esperar(gerador, 1, timeout_ms=1500)
    gerador.fechar()
    assert all(r[0] != geracao_antiga for r in resultados)


def test_modelo_limita_miniaturas_em_memoria(qapp, tmp_path):
    from PySide6.QtGui import QImage

    midias = _fotos(tmp_path, 5)[:5]
    modelo = ModeloMidias()
    modelo.max_miniaturas = 3
    modelo.adicionar(midias)
    for m in midias:
        modelo.definir_miniatura(m.caminho, QImage(4, 4, QImage.Format.Format_RGB888))
    em_memoria = [modelo.index(i).data(PapelMiniatura) is not None for i in range(5)]
    assert em_memoria == [False, False, True, True, True]


def test_item_nas_duas_filas_e_processado_uma_vez(qapp, tmp_path):
    midias = _fotos(tmp_path, 6)[:6]
    gerador = GeradorMiniaturas(cache=CacheMiniaturas(tmp_path / "cache"))
    gerador.nova_geracao()
    gerador.pre_carregar(midias)
    for m in midias:
        gerador.solicitar(m)
    _esperar(gerador, 6)
    gerador.fechar()
    assert gerador.estatisticas == {"cache": 0, "geradas": 6, "falhas": 0}


def test_pedido_repetido_apos_descarte_da_memoria(qapp, tmp_path):
    [midia] = _fotos(tmp_path, 1)[:1]
    gerador = GeradorMiniaturas(cache=CacheMiniaturas(tmp_path / "cache"))
    gerador.nova_geracao()
    gerador.solicitar(midia)
    _esperar(gerador, 1)
    gerador.solicitar(midia)  # modelo descartou a imagem (LRU) e a tela pediu de novo
    _esperar(gerador, 1)
    gerador.fechar()
    assert gerador.estatisticas == {"cache": 1, "geradas": 1, "falhas": 0}
