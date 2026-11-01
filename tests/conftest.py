import os

import pytest

# Permite rodar os testes de UI sem monitor (CI / Linux headless).
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(autouse=True)
def _cache_isolado(tmp_path_factory, monkeypatch):
    """Cache e histórico em pasta temporária, nunca nos do usuário."""
    pasta = tmp_path_factory.mktemp("cache")
    monkeypatch.setenv("LOCALAPPDATA", str(pasta))
    monkeypatch.setenv("XDG_CACHE_HOME", str(pasta))
    monkeypatch.setenv("XDG_DATA_HOME", str(pasta))  # histórico de alterações (Linux)


@pytest.fixture(autouse=True)
def _configuracoes_isoladas(tmp_path_factory):
    """Configurações (QSettings) em pasta temporária, nunca no perfil real do usuário."""
    from PySide6.QtCore import QSettings

    pasta = tmp_path_factory.mktemp("config")
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(pasta))


@pytest.fixture(autouse=True)
def _sem_caixas_de_mensagem(monkeypatch):
    """Uma QMessageBox modal travaria o teste esperando um clique: falha com a mensagem."""
    from PySide6.QtWidgets import QMessageBox

    def falhar(_parent, titulo, texto, *args, **kwargs):
        raise AssertionError(f"QMessageBox inesperada: {titulo}: {texto}")

    for nome in ("warning", "critical", "information", "question"):
        monkeypatch.setattr(QMessageBox, nome, falhar)


@pytest.fixture(scope="session")
def qapp():
    import gc

    from ags_media_chrono.app import create_app

    app = create_app([])
    yield app
    # Encerramento ordenado: sem isso o Qt pode ser destruído antes de objetos que ainda o
    # usam, e o processo cai ao sair (segfault no Linux) mesmo com todos os testes passando.
    _fechar_janelas()
    gc.collect()
    app.shutdown()


def _fechar_janelas() -> None:
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QApplication

    if QApplication.instance() is None:
        return
    for janela in QApplication.topLevelWidgets():
        janela.close()  # MainWindow.closeEvent para threads e processos do ExifTool
        janela.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QCoreApplication.processEvents()


@pytest.fixture(autouse=True)
def _limpar_janelas_apos_teste():
    """Cada teste deixa a aplicação sem janelas abertas (e sem threads de fundo rodando)."""
    yield
    _fechar_janelas()
