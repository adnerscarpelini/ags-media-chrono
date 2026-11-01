from ags_media_chrono.ui.filtro_galeria import Ordenacao
from ags_media_chrono.ui.main_window import MainWindow


def test_configuracoes_sao_lembradas(qapp, tmp_path):
    janela = MainWindow()
    janela.resize(1111, 777)
    janela.galeria.grade.definir_tamanho(240)
    janela.galeria.combo_ordem.setCurrentIndex(list(Ordenacao).index(Ordenacao.TAMANHO))
    janela.galeria.botao_direcao.setChecked(True)
    janela.acao_subpastas.setChecked(True)
    janela.acao_quicktime_utc.setChecked(False)
    janela.abrir_pasta(tmp_path)
    janela.close()

    nova = MainWindow()
    assert nova.galeria.grade.tamanho == 240
    assert nova.slider_zoom.value() == 240
    assert nova.galeria.proxy.ordenacao == Ordenacao.TAMANHO
    assert not nova.galeria.proxy.crescente
    assert nova.acao_subpastas.isChecked()
    assert not nova.galeria.modelo.opcoes_fuso.quicktime_utc
    assert nova.ultima_pasta() == tmp_path
    # (o tamanho exato não é comparado: a tela virtual dos testes é pequena e o Qt ajusta)
    from ags_media_chrono.ui.config import configuracoes

    assert configuracoes().value("janela/geometria")
    nova.close()


def test_ultima_pasta_que_nao_existe_mais(qapp, tmp_path):
    pasta = tmp_path / "apagada"
    pasta.mkdir()
    janela = MainWindow()
    janela.abrir_pasta(pasta)
    janela.close()
    pasta.rmdir()
    assert MainWindow.ultima_pasta() is None
