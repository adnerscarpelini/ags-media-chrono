from ags_media_chrono import APP_NAME, __version__
from ags_media_chrono.ui.main_window import MainWindow


def test_main_window_opens(qapp):
    window = MainWindow()
    window.show()
    assert window.isVisible()
    assert window.windowTitle() == f"{APP_NAME} {__version__}"
    window.close()
