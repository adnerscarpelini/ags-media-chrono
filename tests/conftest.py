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


@pytest.fixture(scope="session")
def qapp():
    from ags_media_chrono.app import create_app

    return create_app([])
