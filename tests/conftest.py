import os

import pytest

# Permite rodar os testes de UI sem monitor (CI / Linux headless).
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def qapp():
    from ags_media_chrono.app import create_app

    return create_app([])
