import time

from PySide6.QtCore import QEventLoop, QTimer

from ags_media_chrono.ui.main_window import MainWindow


def _criar(base, n, ext=".jpg"):
    for i in range(n):
        (base / f"{i:05d}{ext}").write_bytes(b"x")


def _esperar_carregamento(janela, timeout_ms=10_000):
    loop = QEventLoop()
    janela.carregador.concluido.connect(lambda *_: loop.quit())
    QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec()


def test_abrir_pasta_lista_midias(qapp, tmp_path):
    _criar(tmp_path, 3)
    _criar(tmp_path, 2, ".mov")
    (tmp_path / "leia-me.txt").write_text("x")
    janela = MainWindow()
    janela.abrir_pasta(tmp_path)
    _esperar_carregamento(janela)
    assert janela.galeria.modelo.rowCount() == 5
    assert janela.galeria.pilha.currentIndex() == 1
    assert "3 fotos · 2 vídeos" in janela.statusBar().currentMessage()


def test_pasta_sem_midias_mostra_aviso(qapp, tmp_path):
    janela = MainWindow()
    janela.abrir_pasta(tmp_path)
    _esperar_carregamento(janela)
    assert janela.galeria.pilha.currentIndex() == 0
    assert "Nenhuma foto" in janela.galeria.titulo.text()


def test_alternar_subpastas_recarrega(qapp, tmp_path):
    _criar(tmp_path, 1)
    (tmp_path / "sub").mkdir()
    _criar(tmp_path / "sub", 4)
    janela = MainWindow()
    janela.abrir_pasta(tmp_path)
    _esperar_carregamento(janela)
    assert janela.galeria.modelo.rowCount() == 1
    janela.acao_subpastas.setChecked(True)
    _esperar_carregamento(janela)
    assert janela.galeria.modelo.rowCount() == 5


def test_pasta_grande_nao_trava_interface(qapp, tmp_path):
    _criar(tmp_path, 5000)
    janela = MainWindow()
    inicio = time.perf_counter()
    janela.abrir_pasta(tmp_path)
    # abrir_pasta deve retornar imediatamente; a leitura acontece em segundo plano
    assert time.perf_counter() - inicio < 0.5
    _esperar_carregamento(janela)
    assert janela.galeria.modelo.rowCount() == 5000


def test_abrir_outra_pasta_descarta_lotes_antigos(qapp, tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    _criar(a, 3000)
    _criar(b, 2)
    janela = MainWindow()
    janela.abrir_pasta(a)
    janela.abrir_pasta(b)
    _esperar_carregamento(janela)
    janela.carregador.aguardar()
    qapp.processEvents()
    assert janela.galeria.modelo.rowCount() == 2
