# ruff: noqa: E501  (tabela de exemplos fica mais legível em uma linha por caso)
from datetime import UTC, datetime

import pytest

from ags_media_chrono.core.datas import Origem, candidata_do_nome
from ags_media_chrono.core.nome_arquivo import data_do_nome

D = datetime


@pytest.mark.parametrize(
    ("nome", "valor", "somente_data", "rotulo"),
    [
        # WhatsApp (celular): só a data
        ("IMG-20230512-WA0001.jpg", D(2023, 5, 12), True, "WhatsApp"),
        ("VID-20230512-WA0003.mp4", D(2023, 5, 12), True, "WhatsApp"),
        ("AUD-20230512-WA0010.opus", D(2023, 5, 12), True, "WhatsApp"),
        # WhatsApp (desktop)
        ("WhatsApp Image 2023-05-12 at 14.30.00.jpeg", D(2023, 5, 12, 14, 30), False, "WhatsApp"),
        ("WhatsApp Image 2023-05-12 at 2.30.00 PM.jpeg", D(2023, 5, 12, 14, 30), False, "WhatsApp"),
        ("WhatsApp Video 2023-05-12 at 12.05.09 AM (1).mp4", D(2023, 5, 12, 0, 5, 9), False, "WhatsApp"),
        ("Imagem do WhatsApp de 2024-03-15 à(s) 10.20.30_8f3a2b1c.jpg", D(2024, 3, 15, 10, 20, 30), False, "WhatsApp"),
        # Android / Samsung / OPPO
        ("IMG_20230512_143000.jpg", D(2023, 5, 12, 14, 30), False, "Android"),
        ("IMG_20230512_143000_123.jpg", D(2023, 5, 12, 14, 30), False, "Android"),
        ("VID_20230512_143000.mp4", D(2023, 5, 12, 14, 30), False, "Android"),
        ("20230512_143000.jpg", D(2023, 5, 12, 14, 30), False, None),
        ("IMG20230512143000.jpg", D(2023, 5, 12, 14, 30), False, "Android"),
        # Capturas de tela
        ("Screenshot_20230512-143000.png", D(2023, 5, 12, 14, 30), False, "captura de tela"),
        ("Screenshot_2023-05-12-14-30-00-123_com.whatsapp.jpg", D(2023, 5, 12, 14, 30), False, "captura de tela"),
        ("Screenshot 2023-05-12 at 14.30.00.png", D(2023, 5, 12, 14, 30), False, "captura de tela"),
        ("Captura de tela 2023-05-12 143000.png", D(2023, 5, 12, 14, 30), False, "captura de tela"),
        # Signal / Telegram
        ("signal-2023-05-12-143000.jpg", D(2023, 5, 12, 14, 30), False, "Signal"),
        ("photo_2023-05-12_14-30-00.jpg", D(2023, 5, 12, 14, 30), False, "Telegram"),
        # Genéricos e nomes já renomeados pelo usuário
        ("2023-05-12 14.30.00.jpg", D(2023, 5, 12, 14, 30), False, None),
        ("2026_aniversario_leticia_20261101_0001.jpg", D(2026, 11, 1), True, None),
        ("Festa 2023-05-12.jpg", D(2023, 5, 12), True, None),
    ],
)  # fmt: skip
def test_padroes_reconhecidos(nome, valor, somente_data, rotulo):
    encontrada = data_do_nome(nome)
    assert encontrada is not None, nome
    assert encontrada.valor == valor
    assert encontrada.somente_data == somente_data
    sufixo = f" ({rotulo})" if rotulo else ""
    assert encontrada.rotulo == f"Data no nome do arquivo{sufixo}"


def test_pixel_em_utc():
    encontrada = data_do_nome("PXL_20230512_173000123.jpg")
    assert encontrada.valor == datetime(2023, 5, 12, 17, 30, tzinfo=UTC)
    assert "UTC" in encontrada.rotulo


@pytest.mark.parametrize(
    "nome",
    [
        "IMG_1234.JPG",
        "DSC_0105.JPG",
        "DSC_0105_b.jpg",
        "_ministerio_arcanjos_as_coisas_0001.mp4",
        "45111a49-9171-4885-85b3-0e26b1001d3f.mp4",
        "ABF248E1-305F-4B70-A6A8-AD33862B6AAB.mp4",
        "20231512-20235000.jpg",  # data impossível
        "18000512_143000.jpg",  # antes de 1990
        "foto 12345678.jpg",
        "sem_extensao",
    ],
)
def test_nomes_sem_data(nome):
    assert data_do_nome(nome) is None


def test_hora_invalida_vira_somente_data():
    encontrada = data_do_nome("IMG_20230512_253000.jpg")
    assert encontrada.valor == datetime(2023, 5, 12)
    assert encontrada.somente_data


def test_candidata_do_nome_nao_e_captura():
    c = candidata_do_nome("VID-20230512-WA0003.mp4")
    assert c.origem == Origem.NOME
    assert not c.captura
    assert c.texto == "VID-20230512-WA0003.mp4"
    assert candidata_do_nome("IMG_1234.JPG") is None
