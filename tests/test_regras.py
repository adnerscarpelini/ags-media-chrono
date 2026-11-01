from pathlib import Path

from PySide6.QtCore import Qt

from ags_media_chrono.core.datas import DatasArquivo, candidata_do_nome, candidatas_de_tags
from ags_media_chrono.core.escolhas import EstadoMidia, Status, escolha_atual
from ags_media_chrono.core.regras import (
    Alvo,
    Criterio,
    Regra,
    candidata_do_criterio,
    escolha_por_regra,
    simular_regra,
)
from ags_media_chrono.ui.dialogo_regra import DialogoRegra, carregar_predefinicoes

IPHONE = {
    "ExifIFD:DateTimeOriginal": "2026:10:28 10:00:08",
    "ExifIFD:OffsetTimeOriginal": "-03:00",
    "System:FileModifyDate": "2026:10:29 09:26:20-03:00",
}
WHATSAPP = {
    "System:FileModifyDate": "2023:05:20 08:02:48-03:00",
    "System:FileCreateDate": "2026:11:01 10:45:52-03:00",
}


def _datas(tags, nome):
    candidatas = candidatas_de_tags(tags)
    if (n := candidata_do_nome(nome)) is not None:
        candidatas.append(n)
    return DatasArquivo(Path(nome), candidatas)


def _estado(tags, nome):
    estado = EstadoMidia()
    estado.receber_datas(_datas(tags, nome))
    return estado


def test_criterios_individuais():
    d = _datas(WHATSAPP, "VID-20230512-WA0003.mp4")
    assert candidata_do_criterio(d, Criterio.CAPTURA) is None
    assert candidata_do_criterio(d, Criterio.NOME).texto == "VID-20230512-WA0003.mp4"
    assert candidata_do_criterio(d, Criterio.MODIFICACAO_ARQUIVO).campo == "System:FileModifyDate"
    assert candidata_do_criterio(d, Criterio.CRIACAO_ARQUIVO).campo == "System:FileCreateDate"
    assert candidata_do_criterio(d, Criterio.MAIS_ANTIGA).origem.value == "Nome do arquivo"
    assert candidata_do_criterio(d, Criterio.MAIS_ANTIGA_METADADOS) is None


def test_primeiro_criterio_que_encontra_data_vence():
    d = _datas(WHATSAPP, "VID-20230512-WA0003.mp4")
    escolha = escolha_por_regra(d, [Criterio.CAPTURA, Criterio.NOME, Criterio.MAIS_ANTIGA])
    assert escolha.campo == "Nome:Arquivo"
    assert escolha_por_regra(d, [Criterio.CAPTURA]) is None


def test_simular_respeita_alvo_e_nao_altera_estado():
    manual = _estado(IPHONE, "IMG_0001.HEIC")
    manual.escolher(escolha_atual())
    estados = {
        Path("iphone.heic"): _estado(IPHONE, "IMG_0001.HEIC"),  # sugerida
        Path("whats.mp4"): _estado(WHATSAPP, "VID-20230512-WA0003.mp4"),  # pendente
        Path("manual.heic"): manual,  # escolhida manualmente
        Path("sem_nada.mp4"): _estado({}, "abc.mp4"),  # pendente, sem datas
        Path("nao_lido.jpg"): EstadoMidia(),
    }
    regra = Regra([Criterio.NOME], Alvo.PENDENTES_E_SUGERIDAS)
    r = simular_regra(estados, regra)
    assert set(r.escolhas) == {Path("whats.mp4")}
    assert set(r.sem_data) == {Path("iphone.heic"), Path("sem_nada.mp4")}
    assert r.ignorados == 1 and r.nao_lidos == 1
    assert estados[Path("whats.mp4")].status == Status.PENDENTE  # simulação não altera

    r_todos = simular_regra(estados, Regra([Criterio.MAIS_ANTIGA], Alvo.TODOS))
    assert Path("manual.heic") in r_todos.escolhas
    r_pend = simular_regra(estados, Regra([Criterio.MAIS_ANTIGA], Alvo.PENDENTES))
    assert Path("iphone.heic") not in r_pend.escolhas


def test_regra_serializa_e_ignora_valores_desconhecidos():
    regra = Regra([Criterio.NOME, Criterio.MAIS_ANTIGA], Alvo.TODOS)
    assert Regra.de_dict(regra.para_dict()) == regra
    lida = Regra.de_dict({"criterios": ["nome", "inexistente"], "alvo": "???"})
    assert lida == Regra([Criterio.NOME], Alvo.PENDENTES_E_SUGERIDAS)
    assert Regra.de_dict({}).criterios == Regra().criterios


def test_dialogo_previa_ordem_e_predefinicoes(qapp):
    estados = {
        Path("whats.mp4"): _estado(WHATSAPP, "VID-20230512-WA0003.mp4"),
        Path("sem_nada.mp4"): _estado({}, "abc.mp4"),
    }
    dialogo = DialogoRegra(estados)
    assert "1</b> recebem data" in dialogo.previa.text()
    assert "1</b> continuam sem data" in dialogo.previa.text()

    # desmarca tudo exceto "modificação do arquivo"
    for i in range(dialogo.lista.count()):
        item = dialogo.lista.item(i)
        manter = item.data(Qt.ItemDataRole.UserRole) == Criterio.MODIFICACAO_ARQUIVO
        item.setCheckState(Qt.CheckState.Checked if manter else Qt.CheckState.Unchecked)
    assert dialogo.regra().criterios == [Criterio.MODIFICACAO_ARQUIVO]

    dialogo.lista.setCurrentRow(dialogo.lista.count() - 1)
    ultimo = dialogo.lista.currentItem().data(Qt.ItemDataRole.UserRole)
    dialogo._mover(-1)
    assert dialogo.lista.item(dialogo.lista.count() - 2).data(Qt.ItemDataRole.UserRole) == ultimo

    from ags_media_chrono.ui.dialogo_regra import salvar_predefinicao

    salvar_predefinicao(dialogo.config, "Minha", dialogo.regra())
    assert carregar_predefinicoes(dialogo.config)["Minha"] == dialogo.regra()
    dialogo._aceitar()
    assert set(dialogo.resultado.escolhas) == {Path("whats.mp4")}

    # a última regra usada volta na próxima abertura
    assert DialogoRegra(estados).regra().criterios == [Criterio.MODIFICACAO_ARQUIVO]
