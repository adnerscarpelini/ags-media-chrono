from ags_media_chrono.ui.sobre import LOGO, DialogoSobre, versao_ferramenta


def test_sobre_mostra_versao_creditos_e_logo(qapp):
    assert LOGO.is_file()
    dialogo = DialogoSobre()
    from PySide6.QtWidgets import QLabel

    textos = " ".join(rotulo.text() for rotulo in dialogo.findChildren(QLabel))
    assert "ExifTool" in textos and "FFmpeg" in textos and "MIT" in textos


def test_versao_ferramenta_ausente(monkeypatch):
    from ags_media_chrono.core import ferramentas

    def ausente(nome, **_):
        raise ferramentas.FerramentaNaoEncontrada(nome)

    monkeypatch.setattr("ags_media_chrono.ui.sobre.localizar", ausente)
    assert versao_ferramenta("ffmpeg") == "não encontrado"
