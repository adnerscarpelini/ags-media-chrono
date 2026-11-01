"""Painel à direita: todas as datas do arquivo em foco e a escolha da data correta."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from PySide6.QtCore import QDateTime, Qt, QTimeZone, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QDateTimeEdit,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ags_media_chrono.core.datas import (
    DataCandidata,
    DatasArquivo,
    OpcoesFuso,
    formatar_data,
    formatar_fuso,
)
from ags_media_chrono.core.escolhas import (
    Escolha,
    EstadoMidia,
    TipoEscolha,
    escolha_atual,
    escolha_de_candidata,
    escolha_especifica,
)
from ags_media_chrono.ui.tema import CORES, CORES_STATUS


def formatar_deslocamento(deslocamento: timedelta) -> str:
    """timedelta(days=1, hours=-2) -> "+22 h"; timedelta(minutes=-90) -> "-1 h 30 min"."""
    minutos = int(deslocamento.total_seconds()) // 60
    sinal = "-" if minutos < 0 else "+"
    dias, resto = divmod(abs(minutos), 1440)
    horas, mins = divmod(resto, 60)
    partes = [
        f"{dias} d" if dias else "",
        f"{horas} h" if horas else "",
        f"{mins} min" if mins else "",
    ]
    return sinal + " ".join(p for p in partes if p) if minutos else "0"


def _titulo(texto: str) -> QLabel:
    rotulo = QLabel(texto.upper())
    rotulo.setObjectName("tituloPainel")
    return rotulo


def _para_qdatetime(valor: datetime) -> QDateTime:
    """datetime com fuso -> QDateTime exibindo o mesmo relógio."""
    fuso = QTimeZone(int(valor.utcoffset().total_seconds())) if valor.tzinfo else None
    qdt = QDateTime(valor.year, valor.month, valor.day, valor.hour, valor.minute, valor.second)
    if fuso is not None:
        qdt.setTimeZone(fuso)
    return qdt


class PainelDatas(QFrame):
    escolha_alterada = Signal(object, object)  # Path, Escolha | None
    aplicar_solicitado = Signal()
    deslocamento_em_lote = Signal(object)  # timedelta para todos os selecionados

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("painel")
        self.arquivo: Path | None = None
        self.estado: EstadoMidia | None = None
        self.opcoes_fuso = OpcoesFuso()
        self._candidatas: list[DataCandidata] = []
        self._atualizando = False  # evita emitir sinais enquanto a tela é preenchida

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(_titulo("Datas do arquivo"))

        self.pilha = QStackedWidget()
        self.mensagem = QLabel("Selecione um arquivo para ver\ntodas as datas encontradas.")
        self.mensagem.setObjectName("vazio")
        self.mensagem.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mensagem.setWordWrap(True)
        self.pilha.addWidget(self.mensagem)
        self.pilha.addWidget(self._criar_conteudo())
        layout.addWidget(self.pilha, 1)

        rodape = QWidget()
        rodape_layout = QVBoxLayout(rodape)
        rodape_layout.setContentsMargins(10, 10, 10, 10)
        self.botao_aplicar = QPushButton("Aplicar datas")
        self.botao_aplicar.setObjectName("primario")
        self.botao_aplicar.setEnabled(False)
        self.botao_aplicar.clicked.connect(self.aplicar_solicitado)
        rodape_layout.addWidget(self.botao_aplicar)
        layout.addWidget(rodape)

    # --- montagem -------------------------------------------------------------------------

    def _criar_conteudo(self) -> QWidget:
        conteudo = QWidget()
        layout = QVBoxLayout(conteudo)
        layout.setContentsMargins(10, 8, 10, 4)
        layout.setSpacing(8)

        self.rotulo_nome = QLabel()
        fonte = QFont()
        fonte.setBold(True)
        self.rotulo_nome.setFont(fonte)
        self.rotulo_nome.setWordWrap(True)
        layout.addWidget(self.rotulo_nome)

        linha = QHBoxLayout()
        self.rotulo_status = QLabel()
        self.rotulo_status.setObjectName("seloStatus")
        linha.addWidget(self.rotulo_status)
        self.rotulo_fuso = QLabel()
        self.rotulo_fuso.setObjectName("vazio")
        linha.addWidget(self.rotulo_fuso)
        linha.addStretch(1)
        layout.addLayout(linha)
        self.rotulo_selecao = QLabel()
        self.rotulo_selecao.setObjectName("vazio")
        self.rotulo_selecao.setWordWrap(True)
        layout.addWidget(self.rotulo_selecao)

        self.grupo = QButtonGroup(self)
        self.grupo.setExclusive(True)
        self.grupo.buttonToggled.connect(self._ao_marcar)

        self.rolagem = QScrollArea()
        self.rolagem.setWidgetResizable(True)
        self.rolagem.setFrameShape(QFrame.Shape.NoFrame)
        self.lista = QWidget()
        self.lista.setObjectName("listaDatas")
        self.lista_layout = QVBoxLayout(self.lista)
        self.lista_layout.setContentsMargins(0, 0, 0, 0)
        self.lista_layout.setSpacing(2)
        self.lista_layout.addStretch(1)
        self.rolagem.setWidget(self.lista)
        layout.addWidget(self.rolagem, 1)
        self._linhas: list[LinhaData] = []

        outras = QGridLayout()
        outras.setContentsMargins(0, 0, 0, 0)
        self.radio_especifica = QRadioButton("Data específica")
        self.grupo.addButton(self.radio_especifica)
        self.edicao_especifica = QDateTimeEdit()
        self.edicao_especifica.setCalendarPopup(True)
        self.edicao_especifica.setDisplayFormat("dd/MM/yyyy HH:mm:ss")
        self.edicao_especifica.dateTimeChanged.connect(self._ao_editar_especifica)
        self.radio_atual = QRadioButton("Data e hora atuais")
        self.grupo.addButton(self.radio_atual)
        outras.addWidget(self.radio_especifica, 0, 0)
        outras.addWidget(self.edicao_especifica, 0, 1)
        outras.addWidget(self.radio_atual, 1, 0, 1, 2)
        layout.addLayout(outras)

        self.rotulo_final = QLabel()
        self.rotulo_final.setObjectName("resumoEscolha")
        self.rotulo_final.setWordWrap(True)
        layout.addWidget(self.rotulo_final)

        layout.addWidget(self._criar_ajuste())
        return conteudo

    def _criar_ajuste(self) -> QFrame:
        """Ajuste (deslocamento) somado à data escolhida — câmera com relógio errado."""
        quadro = QFrame()
        quadro.setObjectName("quadroAjuste")
        grade = QGridLayout(quadro)
        grade.setContentsMargins(0, 4, 0, 0)
        grade.addWidget(QLabel("Ajustar"), 0, 0)
        self.spins_ajuste: dict[str, QSpinBox] = {}
        for coluna, (chave, sufixo, limite) in enumerate(
            (("dias", " d", 36500), ("horas", " h", 23), ("minutos", " min", 59)), start=1
        ):
            spin = QSpinBox()
            spin.setRange(-limite, limite)
            spin.setSuffix(sufixo)
            spin.setToolTip("Valores negativos atrasam a data")
            spin.valueChanged.connect(self._ao_ajustar)
            self.spins_ajuste[chave] = spin
            grade.addWidget(spin, 0, coluna)
        self.botao_ajuste_lote = QPushButton("Aplicar ajuste aos selecionados")
        self.botao_ajuste_lote.setToolTip(
            "Usa este mesmo ajuste em todos os arquivos selecionados que têm data escolhida"
        )
        self.botao_ajuste_lote.clicked.connect(
            lambda: self.deslocamento_em_lote.emit(self.deslocamento())
        )
        grade.addWidget(self.botao_ajuste_lote, 1, 0, 1, 4)
        return quadro

    def deslocamento(self) -> timedelta:
        s = self.spins_ajuste
        return timedelta(
            days=s["dias"].value(), hours=s["horas"].value(), minutes=s["minutos"].value()
        )

    def _mostrar_deslocamento(self, deslocamento: timedelta) -> None:
        minutos = int(deslocamento.total_seconds()) // 60
        sinal = -1 if minutos < 0 else 1
        dias, resto = divmod(abs(minutos), 1440)
        horas, mins = divmod(resto, 60)
        for chave, valor in (("dias", dias), ("horas", horas), ("minutos", mins)):
            spin = self.spins_ajuste[chave]
            spin.blockSignals(True)
            spin.setValue(sinal * valor)
            spin.blockSignals(False)

    def _ao_ajustar(self, *_args) -> None:
        if self._atualizando or self.estado is None or self.estado.escolha is None:
            return
        escolha = self.estado.escolha.com_deslocamento(self.deslocamento())
        self._mostrar_final(escolha)
        self.escolha_alterada.emit(self.arquivo, escolha)

    def _botao_da_linha(self, linha: int) -> QRadioButton:
        return self._linhas[linha].radio

    # --- exibição -------------------------------------------------------------------------

    def limpar(self, mensagem: str = "Selecione um arquivo para ver\ntodas as datas encontradas."):
        self.arquivo, self.estado = None, None
        self.mensagem.setText(mensagem)
        self.pilha.setCurrentIndex(0)

    def mostrar(self, arquivo: Path, estado: EstadoMidia, selecionados: int = 1) -> None:
        self.arquivo, self.estado = arquivo, estado
        if estado.datas is None:
            self.mensagem.setText(f"{arquivo.name}\n\nLendo datas…")
            self.pilha.setCurrentIndex(0)
            return
        if estado.datas.erro:
            self.mensagem.setText(
                f"{arquivo.name}\n\nNão foi possível ler as datas:\n{estado.mensagem}"
            )
            self.pilha.setCurrentIndex(0)
            return

        self._atualizando = True
        try:
            self._preencher(arquivo, estado, selecionados)
        finally:
            self._atualizando = False
        self.pilha.setCurrentIndex(1)

    def _preencher(self, arquivo: Path, estado: EstadoMidia, selecionados: int) -> None:
        datas: DatasArquivo = estado.datas
        self.rotulo_nome.setText(arquivo.name)
        self._mostrar_status(estado)
        fuso = datas.fuso_referencia()
        self.rotulo_fuso.setText(f"fuso {formatar_fuso(fuso)}" if fuso is not None else "")
        self.rotulo_selecao.setText(
            f"{selecionados} arquivos selecionados — mostrando o arquivo em foco."
            if selecionados > 1
            else ""
        )
        self.rotulo_selecao.setVisible(selecionados > 1)

        for botao in list(self.grupo.buttons()):
            if botao not in (self.radio_especifica, self.radio_atual):
                self.grupo.removeButton(botao)
        self._candidatas = sorted(
            datas.candidatas, key=lambda c: datas.instante(c, self.opcoes_fuso)
        )
        sugerida = datas.captura_sugerida()
        mais_antiga = self._candidatas[0] if self._candidatas else None
        for antiga in self._linhas:
            antiga.deleteLater()
        self._linhas = []
        for c in self._candidatas:
            linha = self._criar_linha(datas, c, c is sugerida, c is mais_antiga)
            self.lista_layout.insertWidget(self.lista_layout.count() - 1, linha)
            self._linhas.append(linha)

        escolha = estado.escolha
        marcado = None
        if escolha is not None and escolha.tipo == TipoEscolha.CANDIDATA:
            for linha, c in enumerate(self._candidatas):
                if c.campo == escolha.campo:
                    marcado = self._botao_da_linha(linha)
                    break
        elif escolha is not None and escolha.tipo == TipoEscolha.ESPECIFICA:
            marcado = self.radio_especifica
        elif escolha is not None and escolha.tipo == TipoEscolha.ATUAL:
            marcado = self.radio_atual

        self.grupo.setExclusive(False)
        for botao in self.grupo.buttons():
            botao.setChecked(botao is marcado)
        self.grupo.setExclusive(True)

        base = (
            escolha.final
            if escolha
            else (
                datas.hora_local(sugerida, self.opcoes_fuso)
                if sugerida
                else datetime.now().astimezone()
            )
        )
        self.edicao_especifica.setDateTime(_para_qdatetime(base))
        self._mostrar_deslocamento(escolha.deslocamento if escolha else timedelta(0))
        self._mostrar_final(escolha)

    def _criar_linha(
        self, datas: DatasArquivo, c: DataCandidata, sugerida: bool, antiga: bool
    ) -> LinhaData:
        local = datas.hora_local(c, self.opcoes_fuso)
        marcas = []
        if sugerida:
            marcas.append("★ sugerida")
        if antiga:
            marcas.append("mais antiga")
        if c.utc_presumido and self.opcoes_fuso.quicktime_utc:
            marcas.append("convertida de UTC")
        detalhe = " · ".join([c.origem.value, c.rotulo, *marcas])
        linha = LinhaData(formatar_data(local, c.somente_data), detalhe, destaque=sugerida)
        linha.setToolTip(f"{c.campo}\nValor gravado no arquivo: {c.texto}")
        linha.radio.setProperty("campo", c.campo)
        self.grupo.addButton(linha.radio)
        return linha

    def _mostrar_status(self, estado: EstadoMidia) -> None:
        cor = CORES_STATUS[estado.status.value]
        self.rotulo_status.setText(estado.status.rotulo)
        self.rotulo_status.setStyleSheet(
            f"color: {cor}; border: 1px solid {cor}; border-radius: 3px; padding: 1px 6px;"
        )

    def _mostrar_final(self, escolha: Escolha | None) -> None:
        if escolha is None:
            self.rotulo_final.setText("Nenhuma data escolhida.")
            for spin in self.spins_ajuste.values():
                spin.setEnabled(False)
            self.botao_ajuste_lote.setEnabled(False)
            return
        final = escolha.final
        texto = formatar_data(final, escolha.somente_data)
        if final.tzinfo is not None:
            texto += f" ({formatar_fuso(final.utcoffset())})"
        ajuste = ""
        if escolha.deslocamento:
            ajuste = f"<br><span style='color:{CORES['alerta']}'>com ajuste de " + (
                f"{formatar_deslocamento(escolha.deslocamento)}</span>"
            )
        self.rotulo_final.setText(f"Será gravada: <b>{texto}</b>{ajuste}")
        for spin in self.spins_ajuste.values():
            spin.setEnabled(True)
        self.botao_ajuste_lote.setEnabled(True)

    # --- interação ------------------------------------------------------------------------

    def _escolha_do_botao(self, botao) -> Escolha | None:
        datas = self.estado.datas if self.estado else None
        if botao is self.radio_especifica:
            return escolha_especifica(self._valor_especifico(), datas)
        if botao is self.radio_atual:
            return escolha_atual(datas)
        campo = botao.property("campo")
        candidata = next((c for c in self._candidatas if c.campo == campo), None)
        if candidata is None or datas is None:
            return None
        return escolha_de_candidata(datas, candidata, self.opcoes_fuso)

    def _valor_especifico(self) -> datetime:
        qdt = self.edicao_especifica.dateTime()
        d, t = qdt.date(), qdt.time()
        return datetime(d.year(), d.month(), d.day(), t.hour(), t.minute(), t.second())

    def _ao_marcar(self, botao, marcado: bool) -> None:
        if self._atualizando or not marcado or self.arquivo is None:
            return
        self._emitir(self._escolha_do_botao(botao))

    def _ao_editar_especifica(self, *_args) -> None:
        if self._atualizando or self.arquivo is None:
            return
        if self.radio_especifica.isChecked():
            self._emitir(self._escolha_do_botao(self.radio_especifica))
        else:
            self.radio_especifica.setChecked(True)  # editar a data já seleciona a opção

    def _emitir(self, escolha: Escolha | None) -> None:
        anterior = self.estado.escolha if self.estado else None
        if escolha is not None and anterior is not None:
            escolha = escolha.com_deslocamento(anterior.deslocamento)  # mantém o ajuste (#16)
        self._mostrar_final(escolha)
        self.escolha_alterada.emit(self.arquivo, escolha)

    def ao_estado_alterado(self, estado: EstadoMidia) -> None:
        """Atualiza só o selo e o resumo quando a mudança veio deste painel."""
        self.estado = estado
        self._mostrar_status(estado)
        self._mostrar_final(estado.escolha)

    def botao_do_campo(self, campo: str) -> QRadioButton | None:
        return next((ln.radio for ln in self._linhas if ln.radio.property("campo") == campo), None)

    @property
    def quantidade_datas(self) -> int:
        return len(self._linhas)


class LinhaData(QFrame):
    """Uma data da lista: rádio com a data e, abaixo, origem/descrição. Clicar em qualquer
    parte da linha seleciona a data."""

    def __init__(self, data: str, detalhe: str, destaque: bool = False) -> None:
        super().__init__()
        self.setObjectName("linhaData")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(0)
        self.radio = QRadioButton(data)
        if destaque:
            fonte = self.radio.font()
            fonte.setBold(True)
            self.radio.setFont(fonte)
        self.detalhe = QLabel(detalhe)
        self.detalhe.setObjectName("detalheData")
        self.detalhe.setWordWrap(True)
        self.detalhe.setContentsMargins(22, 0, 0, 0)  # alinhado ao texto do rádio
        layout.addWidget(self.radio)
        layout.addWidget(self.detalhe)

    def mousePressEvent(self, evento) -> None:
        self.radio.click()
        super().mousePressEvent(evento)
