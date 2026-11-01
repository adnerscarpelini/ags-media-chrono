from datetime import datetime, timedelta, timezone
from pathlib import Path

from PySide6.QtGui import QImage

from ags_media_chrono.core.datas import DatasArquivo, candidatas_de_tags
from ags_media_chrono.core.escolhas import Status, escolha_especifica
from ags_media_chrono.core.midias import Midia, TipoMidia
from ags_media_chrono.ui.filtro_galeria import Ordenacao, ProxyGaleria
from ags_media_chrono.ui.galeria import VisaoGaleria
from ags_media_chrono.ui.main_window import resumo_status
from ags_media_chrono.ui.modelo_midias import ModeloMidias, PapelMidia

BRT = timezone(timedelta(hours=-3))


def _m(nome):
    return Midia(Path("/x") / nome, TipoMidia.FOTO, 1, 0.0)


def _modelo():
    modelo = ModeloMidias()
    midias = [_m("a.jpg"), _m("b.jpg"), _m("c.jpg")]
    modelo.adicionar(midias)
    # a: sugerida (tem data de captura), b: pendente, c: ainda não lido
    modelo.definir_datas(
        DatasArquivo(
            midias[0].caminho,
            candidatas_de_tags({"ExifIFD:DateTimeOriginal": "2020:01:01 10:00:00"}),
        )
    )
    modelo.definir_datas(DatasArquivo(midias[1].caminho, []))
    proxy = ProxyGaleria()
    proxy.setSourceModel(modelo)
    return modelo, proxy, midias


def _nomes(proxy):
    return [proxy.index(i, 0).data(PapelMidia).nome for i in range(proxy.rowCount())]


def test_filtro_por_status_acompanha_mudancas(qapp):
    modelo, proxy, midias = _modelo()
    proxy.definir_status(Status.PENDENTE)
    assert _nomes(proxy) == ["b.jpg", "c.jpg"]
    # escolher uma data para b tira o arquivo do filtro "pendente" na hora
    modelo.definir_escolha(midias[1].caminho, escolha_especifica(datetime(2021, 1, 1, tzinfo=BRT)))
    assert _nomes(proxy) == ["c.jpg"]
    proxy.definir_status(Status.SUGERIDA)
    assert _nomes(proxy) == ["a.jpg"]
    assert proxy.filtrando
    proxy.definir_status(None)
    assert proxy.rowCount() == 3


def test_ordenar_por_data_escolhida(qapp):
    modelo, proxy, midias = _modelo()
    modelo.definir_escolha(midias[1].caminho, escolha_especifica(datetime(2019, 1, 1, tzinfo=BRT)))
    proxy.ordenar(Ordenacao.DATA_ESCOLHIDA)
    assert _nomes(proxy) == ["b.jpg", "a.jpg", "c.jpg"]  # sem data vai para o fim
    # mudar a data reordena
    modelo.definir_escolha(midias[1].caminho, escolha_especifica(datetime(2025, 1, 1, tzinfo=BRT)))
    assert _nomes(proxy) == ["a.jpg", "b.jpg", "c.jpg"]


def test_resumo_status():
    assert resumo_status({Status.PENDENTE: 2, Status.SUGERIDA: 1}) == "2 pendentes, 1 sugerida"
    assert resumo_status({Status.ERRO: 3}) == "3 com erro"
    assert resumo_status({}) == ""


def test_selos_desenhados_em_tamanhos_grandes_e_pequenos(qapp):
    modelo, proxy, midias = _modelo()
    modelo.definir_status(midias[2].caminho, Status.ERRO, "falhou")
    for m in midias:
        modelo.definir_miniatura(m.caminho, QImage(160, 120, QImage.Format.Format_RGB888))
    grade = VisaoGaleria()
    grade.setModel(proxy)
    grade.resize(700, 300)
    grade.show()
    for tamanho in (200, 80):
        grade.definir_tamanho(tamanho)
        imagem = grade.viewport().grab().toImage()
        assert not imagem.isNull()
