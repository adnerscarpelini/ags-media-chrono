"""Fluxo completo na janela: ler datas -> gravar -> status -> desfazer."""

from datetime import datetime, timedelta, timezone

import pytest
from amostras import criar_amostras, tem
from PySide6.QtCore import QEventLoop, QTimer

from ags_media_chrono.core.datas import ler_datas
from ags_media_chrono.core.escolhas import Status, escolha_especifica
from ags_media_chrono.core.exiftool import ExifTool
from ags_media_chrono.core.gravacao import OpcoesGravacao
from ags_media_chrono.core.historico import listar_operacoes
from ags_media_chrono.ui.aplicacao import DialogoAplicar, DialogoHistorico, DialogoRelatorio
from ags_media_chrono.ui.main_window import MainWindow

BRT = timezone(timedelta(hours=-3))
NOVA = datetime(2024, 2, 29, 15, 45, 30, tzinfo=BRT)

pytestmark = pytest.mark.skipif(not tem("exiftool"), reason="ExifTool não instalado")


def _esperar(sinal, condicao=lambda: True, timeout_ms=20_000):
    loop = QEventLoop()

    def verificar(*_):
        if condicao():
            loop.quit()

    sinal.connect(verificar)
    QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec()
    sinal.disconnect(verificar)


@pytest.fixture
def janela(qapp, tmp_path):
    pasta = tmp_path / "midias"
    with ExifTool() as et:
        amostras = criar_amostras(pasta, et)
    for extra in ("bmp", "avi"):  # deixa só formatos com metadados
        if extra in amostras:
            amostras.pop(extra).unlink()
    j = MainWindow()
    j.abrir_pasta(pasta)
    total = len(amostras)
    _esperar(j.leitor.lote, lambda: sum(
        j.galeria.modelo.estado(m.caminho).lido for m in j.galeria.modelo.midias()
    ) == total)  # fmt: skip
    yield j, amostras
    j.close()


def _status(j):
    m = j.galeria.modelo
    return {x.caminho.name: m.estado(x.caminho).status for x in m.midias()}


def test_gravar_e_desfazer_pela_janela(janela):
    j, amostras = janela
    modelo = j.galeria.modelo
    whatsapp = amostras["whatsapp_jpg"]
    modelo.definir_escolha(whatsapp, escolha_especifica(NOVA))
    prontos = set(j.arquivos_prontos())
    assert whatsapp in prontos and amostras["iphone_jpg"] in prontos
    assert amostras["screenshot_png"] not in prontos  # pendente: fica de fora

    assert j.aplicar_datas(OpcoesGravacao())
    _esperar(j.trabalho.terminado)
    status = _status(j)
    assert all(status[p.name] == Status.APLICADO for p in prontos), status
    assert status[amostras["screenshot_png"].name] == Status.PENDENTE
    assert isinstance(j.relatorio, DialogoRelatorio)
    assert j.relatorio.lista.topLevelItemCount() == len(prontos)

    with ExifTool() as et:
        [d] = ler_datas([whatsapp], et)
    assert d.hora_local(d.captura_sugerida()) == NOVA

    [op] = listar_operacoes()
    assert op.quantidade_ok == len(prontos)
    assert j.desfazer_ultima(confirmar=False)
    _esperar(j.trabalho.terminado)
    with ExifTool() as et:
        [d] = ler_datas([whatsapp], et)
    assert d.captura_sugerida() is None  # voltou a não ter data de captura
    assert listar_operacoes()[0].desfeita
    _esperar(j.leitor.lote, lambda: j.galeria.modelo.estado(whatsapp).lido)
    assert _status(j)[whatsapp.name] == Status.PENDENTE
    assert _status(j)[amostras["iphone_jpg"].name] == Status.SUGERIDA


def test_dialogos_de_opcoes_e_historico(janela):
    j, _ = janela
    dialogo = DialogoAplicar(3)
    opcoes = dialogo.opcoes()
    assert opcoes.grupos and not opcoes.backup
    for caixa in dialogo.caixas.values():
        caixa.setChecked(False)
    assert not dialogo.opcoes().grupos
    historico = DialogoHistorico()
    assert historico.lista.topLevelItemCount() == 1  # "nenhuma alteração"
    assert not historico.botao_desfazer.isEnabled()
