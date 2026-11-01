from datetime import datetime
from pathlib import Path

import pytest

from ags_media_chrono.core.historico import TipoOperacao, listar_operacoes
from ags_media_chrono.core.mascaras import (
    Caixa,
    ErroMascara,
    OpcoesNome,
    formatar_data_mascara,
    gerar_nome,
    problema_no_nome,
    remover_acentos,
    validar,
)
from ags_media_chrono.core.midias import Midia, TipoMidia
from ags_media_chrono.core.renomear import (
    ItemEntrada,
    OrigemData,
    desfazer_renomeacao,
    planejar,
    renomear,
)

D = datetime(2026, 11, 1, 20, 5, 9)


def _m(nome, pasta=Path("/fotos/Festa"), tipo=TipoMidia.FOTO):
    return Midia(pasta / nome, tipo, 1, 0)


def _nome(mascara, midia=None, data=D, contador=1, **opcoes):
    return gerar_nome(midia or _m("IMG_0001.JPG"), data, contador, OpcoesNome(mascara, **opcoes))


# --- máscaras (#24) ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("mascara", "esperado"),
    [
        ("{Data}", "2026-11-01.jpg"),
        ("{Data[YYYY]}", "2026.jpg"),
        ("{Data[YY]}{Data[MM]}{Data[DD]}", "261101.jpg"),
        ("{Data[YYYYMMDD]}_{Data[HHmmss]}", "20261101_200509.jpg"),
        ("{Data[YYYY-MM-DD HH.mm.ss]}", "2026-11-01 20.05.09.jpg"),
        ("{Nome}", "IMG_0001.jpg"),
        ("{Nome}.{Ext}", "IMG_0001.JPG.jpg"),
        ("{Pasta}_{Tipo}", "Festa_foto.jpg"),
        ("#", "7.jpg"),
        ("####", "0007.jpg"),
        ("{Data[YYYY]}_ministerio_arcanjos_as_coisas{Data[YYYYMMDD]}_####",
         "2026_ministerio_arcanjos_as_coisas20261101_0007.jpg"),
    ],
)  # fmt: skip
def test_mascaras(mascara, esperado):
    assert _nome(mascara, contador=7) == esperado


def test_mascara_de_video_e_contador_grande():
    video = _m("VID.MOV", tipo=TipoMidia.VIDEO)
    assert _nome("{Tipo}_##", video, contador=123) == "video_123.mov"


def test_hashtag_dentro_do_formato_de_data_nao_vira_contador():
    assert _nome("{Data[YYYY#MM]}", contador=5) == "2026#11.jpg"


@pytest.mark.parametrize(
    ("mascara", "trecho"),
    [
        ("", "vazio"),
        ("{Foo}", "desconhecida"),
        ("{Nome[YYYY]}", "Só {Data}"),
        ("{Data", "sem par"),
        ("abc}", "sem par"),
    ],
)
def test_mascaras_invalidas(mascara, trecho):
    with pytest.raises(ErroMascara, match=trecho):
        validar(mascara)


def test_data_ausente():
    with pytest.raises(ErroMascara):
        _nome("{Data}", data=None)
    assert _nome("{Nome}_#", data=None) == "IMG_0001_1.jpg"


def test_formatar_data_mascara_preserva_texto_livre():
    assert formatar_data_mascara(D, "dia DD de MM") == "dia 01 de 11"


# --- opções (#26) -----------------------------------------------------------------------------


def test_caixa_e_extensao():
    assert _nome("Festa", caixa_nome=Caixa.MAIUSCULAS) == "FESTA.jpg"
    assert _nome("Festa", caixa_nome=Caixa.MINUSCULAS, caixa_extensao=Caixa.MAIUSCULAS) == (
        "festa.JPG"
    )
    assert _nome("Festa", caixa_extensao=Caixa.MANTER) == "Festa.JPG"


def test_substituir_texto_e_regex():
    base = {"mascara": "{Nome}"}
    assert _nome(**base, substituir="img_", substituir_por="foto-") == "foto-0001.jpg"
    assert _nome(**base, substituir="img_", substituir_por="x", diferenciar_maiusculas=True) == (
        "IMG_0001.jpg"
    )
    assert _nome(**base, substituir=r"\d+", substituir_por="N", expressao_regular=True) == (
        "IMG_N.jpg"
    )
    with pytest.raises(ErroMascara, match="Expressão regular"):
        _nome(**base, substituir="(", expressao_regular=True)


def test_remover_acentos():
    assert remover_acentos("Aniversário da Letícia — ação ç") == "Aniversario da Leticia — acao c"
    assert _nome("Comemoração", remover_acentos=True) == "Comemoracao.jpg"


@pytest.mark.parametrize(
    ("nome", "problema"),
    [("ok.jpg", None), ("a:b.jpg", "Caractere inválido"), (".jpg", "vazio"), ("x" * 300, "longo")],
)
def test_problema_no_nome(nome, problema):
    resultado = problema_no_nome(nome)
    assert (resultado is None) if problema is None else (problema in resultado)


def test_opcoes_serializam_e_ignoram_valores_estranhos():
    opcoes = OpcoesNome("{Data}_#", inicio=5, caixa_nome=Caixa.MAIUSCULAS, remover_acentos=True)
    assert OpcoesNome.de_dict(opcoes.para_dict()) == opcoes
    lida = OpcoesNome.de_dict({"mascara": "x", "inicio": "abc", "caixa_nome": "???", "novo": 1})
    assert lida == OpcoesNome("x")


# --- plano e conflitos (#25, #27) ------------------------------------------------------------


def _entradas(pasta, nomes, datas=None):
    entradas = []
    for i, nome in enumerate(nomes):
        caminho = pasta / nome
        caminho.write_bytes(nome.encode())
        data = datas[i] if datas else D
        entradas.append(
            ItemEntrada(Midia(caminho, TipoMidia.FOTO, 1, 0), data, OrigemData.ESCOLHIDA)
        )
    return entradas


def test_plano_sequencial_inicio_etapa(tmp_path):
    entradas = _entradas(tmp_path, ["a.jpg", "b.jpg", "c.jpg"])
    plano = planejar(entradas, OpcoesNome("festa_##", inicio=10, etapa=5))
    assert [p.destino.name for p in plano] == ["festa_10.jpg", "festa_15.jpg", "festa_20.jpg"]
    assert all(p.ok and p.muda for p in plano)


def test_reiniciar_contagem_por_dia(tmp_path):
    datas = [datetime(2026, 1, 1, 9), datetime(2026, 1, 1, 10), datetime(2026, 1, 2, 8)]
    entradas = _entradas(tmp_path, ["a.jpg", "b.jpg", "c.jpg"], datas)
    plano = planejar(entradas, OpcoesNome("{Data[YYYYMMDD]}_#", reiniciar_por_dia=True))
    assert [p.destino.name for p in plano] == ["20260101_1.jpg", "20260101_2.jpg", "20260102_1.jpg"]


def test_conflitos_repetidos_existentes_e_invalidos(tmp_path):
    (tmp_path / "ocupado.jpg").write_bytes(b"x")
    entradas = _entradas(tmp_path, ["a.jpg", "b.jpg"])
    repetidos = planejar(entradas, OpcoesNome("igual"))
    assert all(p.problema and "repetido" in p.problema for p in repetidos)
    existente = planejar(entradas[:1], OpcoesNome("ocupado"))
    assert "Já existe" in existente[0].problema
    invalido = planejar(entradas[:1], OpcoesNome("{Data[HH:mm]}"))
    assert "Caractere inválido" in invalido[0].problema
    sem_data = planejar([ItemEntrada(entradas[0].midia, None, OrigemData.NENHUMA)], OpcoesNome())
    assert "Sem data" in sem_data[0].problema


def test_troca_de_nomes_e_desfazer(tmp_path):
    entradas = _entradas(tmp_path, ["a.jpg", "b.jpg"])
    # a -> b e b -> a (troca): permitido, pois os destinos pertencem ao próprio lote
    plano = planejar(entradas, OpcoesNome("{Nome}"))
    plano[0].destino, plano[1].destino = plano[1].origem, plano[0].origem
    resultado = renomear(plano)
    assert resultado.erro is None
    assert (tmp_path / "a.jpg").read_bytes() == b"b.jpg"
    assert (tmp_path / "b.jpg").read_bytes() == b"a.jpg"

    [op] = listar_operacoes(TipoOperacao.RENOMEAR)
    assert desfazer_renomeacao(op) is None
    assert (tmp_path / "a.jpg").read_bytes() == b"a.jpg"
    assert listar_operacoes()[0].desfeita


def test_renomear_somente_maiusculas(tmp_path):
    entradas = _entradas(tmp_path, ["IMG.JPG"])
    plano = planejar(entradas, OpcoesNome("{Nome}", caixa_nome=Caixa.MINUSCULAS))
    assert plano[0].ok, plano[0].problema
    assert renomear(plano).erro is None
    assert [p.name for p in tmp_path.iterdir()] == ["img.jpg"]


def test_falha_no_meio_reverte_tudo(tmp_path, monkeypatch):
    entradas = _entradas(tmp_path, ["a.jpg", "b.jpg", "c.jpg"])
    plano = planejar(entradas, OpcoesNome("novo_#"))
    import ags_media_chrono.core.renomear as modulo

    original = modulo.os.rename
    chamadas = {"n": 0}

    def rename_falhando(origem, destino):
        chamadas["n"] += 1
        if chamadas["n"] == 5:  # 3 para temporários + 2 finais; falha no 2º final
            raise OSError("disco removido")
        return original(origem, destino)

    monkeypatch.setattr(modulo.os, "rename", rename_falhando)
    resultado = renomear(plano)
    monkeypatch.setattr(modulo.os, "rename", original)
    assert "disco removido" in resultado.erro
    assert sorted(p.name for p in tmp_path.iterdir()) == ["a.jpg", "b.jpg", "c.jpg"]
    assert listar_operacoes() == []  # nada salvo no histórico


def test_itens_sem_mudanca_ou_com_problema_ficam_de_fora(tmp_path):
    entradas = _entradas(tmp_path, ["a.jpg", "b.jpg"])
    plano = planejar(entradas, OpcoesNome("{Nome}"))
    assert not any(p.muda for p in plano)
    assert renomear(plano).erro == "Nenhum arquivo para renomear"


def test_arquivo_ocupado_por_um_instante_e_renomeado(tmp_path, monkeypatch):
    entradas = _entradas(tmp_path, ["a.jpg"])
    plano = planejar(entradas, OpcoesNome("novo"))
    import ags_media_chrono.core.renomear as modulo

    original = modulo.os.rename
    falhas = {"n": 2}

    def ocupado(origem, destino):
        if falhas["n"]:
            falhas["n"] -= 1
            raise PermissionError("em uso por outro processo")
        return original(origem, destino)

    monkeypatch.setattr(modulo.os, "rename", ocupado)
    monkeypatch.setattr(modulo.time, "sleep", lambda _s: None)
    assert renomear(plano).erro is None
    assert [p.name for p in tmp_path.iterdir()] == ["novo.jpg"]
