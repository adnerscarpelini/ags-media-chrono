from datetime import datetime, timedelta, timezone
from pathlib import Path

from PySide6.QtCore import QEventLoop, QTimer

from ags_media_chrono.core.datas import DatasArquivo, candidatas_de_tags
from ags_media_chrono.core.escolhas import (
    EstadoMidia,
    Status,
    TipoEscolha,
    escolha_atual,
    escolha_de_candidata,
    escolha_especifica,
)
from ags_media_chrono.ui.painel_datas import PainelDatas

BRT = timezone(timedelta(hours=-3))
MOV = {
    "QuickTime:CreateDate": "2026:10:21 21:53:40",
    "Keys:CreationDate": "2026:10:21 18:53:40-03:00",
    "System:FileModifyDate": "2026:10:22 07:25:28-03:00",
}
WHATSAPP = {"System:FileModifyDate": "2026:10:30 08:02:48-03:00"}


def _datas(tags, nome="a.mov"):
    return DatasArquivo(Path(nome), candidatas_de_tags(tags))


# --- core/escolhas ---------------------------------------------------------------------


def test_sugestao_automatica_da_data_de_captura():
    estado = EstadoMidia()
    estado.receber_datas(_datas(MOV))
    assert estado.status == Status.SUGERIDA
    assert estado.escolha.campo == "Keys:CreationDate"
    assert estado.escolha.final == datetime(2026, 10, 21, 18, 53, 40, tzinfo=BRT)


def test_sem_data_de_captura_fica_pendente():
    estado = EstadoMidia()
    estado.receber_datas(_datas(WHATSAPP))
    assert estado.status == Status.PENDENTE and estado.escolha is None


def test_escolha_manual_vira_escolhida_e_nao_e_sobrescrita_pela_leitura():
    estado = EstadoMidia()
    datas = _datas(MOV)
    estado.receber_datas(datas)
    arquivo = next(c for c in datas.candidatas if c.campo == "System:FileModifyDate")
    estado.escolher(escolha_de_candidata(datas, arquivo))
    assert estado.status == Status.ESCOLHIDA
    estado.receber_datas(datas)  # releitura
    assert estado.escolha.campo == "System:FileModifyDate"


def test_erro_de_leitura():
    estado = EstadoMidia()
    estado.receber_datas(DatasArquivo(Path("x.jpg"), erro="File is empty"))
    assert estado.status == Status.ERRO and estado.mensagem == "File is empty"


def test_escolha_especifica_usa_fuso_do_arquivo():
    escolha = escolha_especifica(datetime(2020, 1, 2, 3, 4, 5), _datas(MOV))
    assert escolha.tipo == TipoEscolha.ESPECIFICA
    assert escolha.valor.utcoffset() == timedelta(hours=-3)


def test_escolha_atual_e_deslocamento():
    escolha = escolha_atual()
    assert escolha.tipo == TipoEscolha.ATUAL and escolha.valor.tzinfo is not None
    ajustada = escolha.com_deslocamento(timedelta(hours=2))
    assert ajustada.final - escolha.final == timedelta(hours=2)


def test_status_pronto_para_aplicar():
    assert Status.SUGERIDA.pronto_para_aplicar and Status.ESCOLHIDA.pronto_para_aplicar
    assert not Status.PENDENTE.pronto_para_aplicar and not Status.APLICADO.pronto_para_aplicar


# --- painel -----------------------------------------------------------------------------


def _painel_com(tags):
    painel = PainelDatas()
    estado = EstadoMidia()
    estado.receber_datas(_datas(tags))
    emitidas = []

    def ao_escolher(arquivo, escolha):
        estado.escolher(escolha)
        painel.ao_estado_alterado(estado)
        emitidas.append(escolha)

    painel.escolha_alterada.connect(ao_escolher)
    painel.mostrar(Path("a.mov"), estado)
    return painel, estado, emitidas


def test_painel_lista_datas_e_marca_sugerida(qapp):
    painel, estado, emitidas = _painel_com(MOV)
    assert painel.pilha.currentIndex() == 1
    assert painel.quantidade_datas == 3
    assert painel.botao_do_campo("Keys:CreationDate").isChecked()
    # QuickTime (UTC) aparece no mesmo horário local do Keys
    assert painel.botao_do_campo("QuickTime:CreateDate").text() == "21/10/2026 18:53:40"
    assert painel.rotulo_status.text() == "Sugerida"
    assert "21/10/2026 18:53:40 (-03:00)" in painel.rotulo_final.text()
    assert emitidas == []  # preencher a tela não conta como escolha


def test_painel_clicar_em_outra_data_escolhe(qapp):
    painel, estado, emitidas = _painel_com(MOV)
    painel.botao_do_campo("System:FileModifyDate").click()
    assert estado.status == Status.ESCOLHIDA
    assert estado.escolha.campo == "System:FileModifyDate"
    assert painel.rotulo_status.text() == "Escolhida"


def test_painel_data_especifica_e_atual(qapp):
    painel, estado, _ = _painel_com(WHATSAPP)
    assert estado.status == Status.PENDENTE
    assert not any(b.isChecked() for b in painel.grupo.buttons())
    from PySide6.QtCore import QDateTime

    painel.edicao_especifica.setDateTime(QDateTime(2023, 5, 12, 14, 30, 0))
    assert estado.escolha.tipo == TipoEscolha.ESPECIFICA
    assert estado.escolha.final.replace(tzinfo=None) == datetime(2023, 5, 12, 14, 30)
    painel.radio_atual.click()
    assert estado.escolha.tipo == TipoEscolha.ATUAL


def test_painel_lendo_e_erro(qapp):
    painel = PainelDatas()
    painel.mostrar(Path("a.jpg"), EstadoMidia())
    assert "Lendo datas" in painel.mensagem.text()
    estado = EstadoMidia()
    estado.receber_datas(DatasArquivo(Path("a.jpg"), erro="File is empty"))
    painel.mostrar(Path("a.jpg"), estado)
    assert "File is empty" in painel.mensagem.text()


def test_janela_le_datas_e_mostra_no_painel(qapp, tmp_path):
    from PIL import Image

    from ags_media_chrono.core.ferramentas import FerramentaNaoEncontrada, localizar
    from ags_media_chrono.ui.main_window import MainWindow

    try:
        localizar("exiftool")
    except FerramentaNaoEncontrada:
        import pytest

        pytest.skip("ExifTool não instalado")

    exif = Image.Exif()
    exif[0x9003] = "2023:05:12 14:30:00"  # DateTimeOriginal (no IFD Exif)
    imagem = Image.new("RGB", (8, 8))
    ifd = exif.get_ifd(0x8769)
    ifd[0x9003] = "2023:05:12 14:30:00"
    imagem.save(tmp_path / "foto.jpg", exif=exif)
    Image.new("RGB", (8, 8)).save(tmp_path / "sem_data.jpg")

    janela = MainWindow()
    janela.abrir_pasta(tmp_path)
    loop = QEventLoop()
    recebidos = []

    def contar(_g, lista):
        recebidos.extend(lista)
        if len(recebidos) >= 2:
            loop.quit()

    janela.leitor.lote.connect(contar)
    QTimer.singleShot(15_000, loop.quit)
    loop.exec()

    modelo = janela.galeria.modelo
    status = {m.nome: modelo.estado(m.caminho).status for m in modelo.midias()}
    assert status == {"foto.jpg": Status.SUGERIDA, "sem_data.jpg": Status.PENDENTE}
    janela.galeria.grade.setCurrentIndex(janela.galeria.grade.model().index(0, 0))
    assert janela.painel_datas.pilha.currentIndex() == 1
    assert janela.painel_datas.botao_aplicar.text() == "Aplicar datas (1)"
    janela.close()


# --- ajuste / deslocamento (#16) -------------------------------------------------------


def test_formatar_deslocamento():
    from ags_media_chrono.ui.painel_datas import formatar_deslocamento

    assert formatar_deslocamento(timedelta(0)) == "0"
    assert formatar_deslocamento(timedelta(days=1, hours=-2)) == "+22 h"
    assert formatar_deslocamento(timedelta(minutes=-90)) == "-1 h 30 min"
    assert formatar_deslocamento(timedelta(days=365, minutes=5)) == "+365 d 5 min"


def test_painel_ajuste_altera_data_final(qapp):
    painel, estado, _ = _painel_com(MOV)
    painel.spins_ajuste["horas"].setValue(-2)
    painel.spins_ajuste["minutos"].setValue(-30)
    assert estado.escolha.deslocamento == timedelta(hours=-2, minutes=-30)
    assert estado.escolha.final == datetime(2026, 10, 21, 16, 23, 40, tzinfo=BRT)
    assert "16:23:40" in painel.rotulo_final.text() and "-2 h 30 min" in painel.rotulo_final.text()
    assert estado.status == Status.ESCOLHIDA

    # trocar a data base mantém o ajuste
    painel.botao_do_campo("System:FileModifyDate").click()
    assert estado.escolha.deslocamento == timedelta(hours=-2, minutes=-30)

    # reabrir o arquivo mostra o ajuste salvo
    painel.mostrar(Path("a.mov"), estado)
    assert painel.spins_ajuste["horas"].value() == -2
    assert painel.spins_ajuste["minutos"].value() == -30


def test_painel_ajuste_desativado_sem_escolha(qapp):
    painel, _, _ = _painel_com(WHATSAPP)
    assert not painel.spins_ajuste["dias"].isEnabled()
    assert not painel.botao_ajuste_lote.isEnabled()


def test_ajuste_em_lote_emite_deslocamento(qapp):
    painel, _, _ = _painel_com(MOV)
    recebido = []
    painel.deslocamento_em_lote.connect(recebido.append)
    painel.spins_ajuste["dias"].setValue(1)
    painel.botao_ajuste_lote.click()
    assert recebido == [timedelta(days=1)]
