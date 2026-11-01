import os

import pytest

from ags_media_chrono.core.midias import TipoMidia, listar_midias, tipo_por_extensao


def _criar(base, *nomes):
    for nome in nomes:
        caminho = base / nome
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_bytes(b"x")


@pytest.mark.parametrize(
    ("nome", "esperado"),
    [
        ("IMG_0001.JPG", TipoMidia.FOTO),
        ("IMG_0001.heic", TipoMidia.FOTO),
        ("DSC_1234.NEF", TipoMidia.FOTO),
        ("IMG_0002.MOV", TipoMidia.VIDEO),
        ("VID-20230512-WA0001.mp4", TipoMidia.VIDEO),
        ("notas.txt", None),
        ("sem_extensao", None),
        ("IMG_0001.AAE", None),  # arquivo de edição do iPhone
    ],
)
def test_tipo_por_extensao(nome, esperado):
    assert tipo_por_extensao(nome) == esperado


def test_lista_apenas_midias_em_ordem(tmp_path):
    _criar(tmp_path, "b.jpg", "A.MOV", "c.txt", "d.heic", "IMG_0001.AAE")
    nomes = [m.nome for m in listar_midias(tmp_path)]
    assert nomes == ["A.MOV", "b.jpg", "d.heic"]


def test_ignora_ocultos_e_appledouble(tmp_path):
    _criar(tmp_path, "foto.jpg", "._foto.jpg", ".oculta/x.jpg")
    assert [m.nome for m in listar_midias(tmp_path, subpastas=True)] == ["foto.jpg"]


def test_subpastas(tmp_path):
    _criar(tmp_path, "raiz.jpg", "2023/maio/a.jpg", "2023/b.mp4", "2024/c.jpg")
    assert [m.nome for m in listar_midias(tmp_path)] == ["raiz.jpg"]
    com_sub = [
        m.caminho.relative_to(tmp_path).as_posix() for m in listar_midias(tmp_path, subpastas=True)
    ]
    assert com_sub == ["raiz.jpg", "2023/b.mp4", "2023/maio/a.jpg", "2024/c.jpg"]


def test_dados_da_midia(tmp_path):
    _criar(tmp_path, "v.mp4")
    os.utime(tmp_path / "v.mp4", (1_600_000_000, 1_600_000_000))
    [m] = listar_midias(tmp_path)
    assert m.tipo == TipoMidia.VIDEO
    assert m.tamanho == 1
    assert m.modificado == 1_600_000_000


def test_pasta_inexistente_nao_quebra(tmp_path):
    assert list(listar_midias(tmp_path / "nao-existe")) == []


def test_cancelamento(tmp_path):
    _criar(tmp_path, *(f"{i}.jpg" for i in range(10)))
    chamadas = {"n": 0}

    def cancelado():
        chamadas["n"] += 1
        return chamadas["n"] > 3

    assert len(list(listar_midias(tmp_path, cancelado=cancelado))) == 3
