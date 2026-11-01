import os

import pytest

# Permite rodar os testes de UI sem monitor (CI / Linux headless).
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(autouse=True)
def _cache_isolado(tmp_path_factory, monkeypatch):
    """Cache de miniaturas em pasta temporária, nunca no cache real do usuário."""
    pasta = tmp_path_factory.mktemp("cache")
    monkeypatch.setenv("LOCALAPPDATA", str(pasta))
    monkeypatch.setenv("XDG_CACHE_HOME", str(pasta))


@pytest.fixture(scope="session")
def qapp():
    from ags_media_chrono.app import create_app

    return create_app([])
