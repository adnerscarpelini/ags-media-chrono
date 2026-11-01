from ags_media_chrono import APP_NAME, __version__
from ags_media_chrono.ui.main_window import MainWindow


def test_main_window_opens(qapp):
    window = MainWindow()
    window.show()
    assert window.isVisible()
    assert window.windowTitle() == f"{APP_NAME} {__version__}"
    window.close()


def test_tema_dark_aplicado(qapp):
    assert qapp.palette().window().color().lightness() < 60
    assert "QSplitter" in qapp.styleSheet()


def test_tres_paineis_redimensionaveis(qapp):
    window = MainWindow()
    assert window.divisor.count() == 3
    assert not window.divisor.childrenCollapsible()


def test_abrir_pasta_atualiza_interface(qapp, tmp_path):
    window = MainWindow()
    window.abrir_pasta(tmp_path)
    assert window.pasta_atual == tmp_path
    assert tmp_path.name in window.windowTitle()


def test_icone_do_app(qapp):
    from ags_media_chrono.app import RECURSOS

    assert (RECURSOS / "icone.png").is_file()
    assert (RECURSOS / "icone.ico").is_file()
    assert not qapp.windowIcon().isNull()
