"""Diálogo "Renomear em lote" (issues #25–#28), no estilo do Renomear lote do XnView."""

from __future__ import annotations

import json

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ags_media_chrono.core.datas import formatar_data
from ags_media_chrono.core.mascaras import SUGESTOES, Caixa, OpcoesNome
from ags_media_chrono.core.renomear import ItemEntrada, ItemPlano, OrigemData, planejar
from ags_media_chrono.ui.config import configuracoes
from ags_media_chrono.ui.tema import CORES

CHAVE_PREDEFINICOES = "renomear/predefinicoes"
CHAVE_ULTIMA = "renomear/ultima"
CHAVE_HISTORICO_MASCARAS = "renomear/mascaras_recentes"
MAX_RECENTES = 12


class DialogoRenomear(QDialog):
    def __init__(self, itens: list[ItemEntrada], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Renomear em lote — {len(itens)} arquivo(s)")
        self.resize(1180, 600)
        self.itens = list(itens)
        self.plano: list[ItemPlano] = []
        self.config = configuracoes()
        self._timer = QTimer(self, singleShot=True, interval=120)
        self._timer.timeout.connect(self.atualizar_previa)

        divisor = QSplitter(Qt.Orientation.Horizontal)
        divisor.addWidget(self._criar_opcoes())
        divisor.addWidget(self._criar_previa())
        divisor.setStretchFactor(1, 1)
        divisor.setSizes([400, 780])

        layout = QVBoxLayout(self)
        layout.addWidget(divisor, 1)
        rodape = QHBoxLayout()
        self.resumo = QLabel()
        self.resumo.setWordWrap(True)
        rodape.addWidget(self.resumo, 1)
        self.botao_renomear = QPushButton("Renomear")
        self.botao_renomear.setObjectName("primario")
        self.botao_renomear.clicked.connect(self._aceitar)
        fechar = QPushButton("Fechar")
        fechar.clicked.connect(self.reject)
        rodape.addWidget(self.botao_renomear)
        rodape.addWidget(fechar)
        layout.addLayout(rodape)

        self._recarregar_predefinicoes()
        self.definir_opcoes(self._ultimas_opcoes())

    # --- montagem -------------------------------------------------------------------------

    def _criar_opcoes(self) -> QWidget:
        painel = QWidget()
        layout = QVBoxLayout(painel)
        layout.setContentsMargins(0, 0, 6, 0)

        grupo_modelo = QGroupBox("Modelo de nome")
        g = QVBoxLayout(grupo_modelo)
        linha = QHBoxLayout()
        self.campo_mascara = QComboBox()
        self.campo_mascara.setEditable(True)
        self.campo_mascara.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.campo_mascara.addItems(self._mascaras_recentes())
        self.campo_mascara.editTextChanged.connect(self._agendar)
        self.campo_mascara.lineEdit().setPlaceholderText("{Data[YYYYMMDD]}_####")
        linha.addWidget(self.campo_mascara, 1)
        botao_inserir = QToolButton()
        botao_inserir.setText("▸")
        botao_inserir.setToolTip("Inserir máscara")
        botao_inserir.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(botao_inserir)
        for texto, descricao in SUGESTOES:
            acao = QAction(f"{texto}    {descricao}", menu)
            acao.triggered.connect(lambda _=False, t=texto: self._inserir(t))
            menu.addAction(acao)
        botao_inserir.setMenu(menu)
        linha.addWidget(botao_inserir)
        g.addLayout(linha)

        numeros = QHBoxLayout()
        numeros.addWidget(QLabel("Início"))
        self.spin_inicio = QSpinBox()
        self.spin_inicio.setRange(0, 9_999_999)
        self.spin_inicio.valueChanged.connect(self._agendar)
        numeros.addWidget(self.spin_inicio)
        numeros.addWidget(QLabel("Etapa"))
        self.spin_etapa = QSpinBox()
        self.spin_etapa.setRange(1, 10_000)
        self.spin_etapa.valueChanged.connect(self._agendar)
        numeros.addWidget(self.spin_etapa)
        numeros.addStretch(1)
        g.addLayout(numeros)
        self.caixa_reiniciar = QCheckBox("Reiniciar o sequencial (#) a cada dia")
        self.caixa_reiniciar.toggled.connect(self._agendar)
        g.addWidget(self.caixa_reiniciar)
        dica = QLabel("A data usada é a escolhida no painel; sem ela, a de captura ou a de "
                      "modificação do arquivo.")  # fmt: skip
        dica.setObjectName("vazio")
        dica.setWordWrap(True)
        g.addWidget(dica)
        layout.addWidget(grupo_modelo)

        grupo_caixa = QGroupBox("Maiúsculas / minúsculas")
        f = QFormLayout(grupo_caixa)
        self.combo_caixa_nome = self._combo_caixa()
        self.combo_caixa_extensao = self._combo_caixa()
        f.addRow("Nome", self.combo_caixa_nome)
        f.addRow("Extensão", self.combo_caixa_extensao)
        layout.addWidget(grupo_caixa)

        self.grupo_substituir = QGroupBox("Substituir")
        self.grupo_substituir.setCheckable(True)
        self.grupo_substituir.toggled.connect(self._agendar)
        s = QFormLayout(self.grupo_substituir)
        self.campo_substituir = QLineEdit()
        self.campo_substituir.textChanged.connect(self._agendar)
        self.campo_com = QLineEdit()
        self.campo_com.textChanged.connect(self._agendar)
        s.addRow("Substituir", self.campo_substituir)
        s.addRow("Com", self.campo_com)
        self.caixa_maiusculas = QCheckBox("Sensível a maiúsculas/minúsculas")
        self.caixa_maiusculas.toggled.connect(self._agendar)
        self.caixa_regex = QCheckBox("Usar expressão regular")
        self.caixa_regex.toggled.connect(self._agendar)
        s.addRow(self.caixa_maiusculas)
        s.addRow(self.caixa_regex)
        layout.addWidget(self.grupo_substituir)

        self.caixa_acentos = QCheckBox("Remover acentos (á → a, ç → c)")
        self.caixa_acentos.toggled.connect(self._agendar)
        layout.addWidget(self.caixa_acentos)
        layout.addStretch(1)

        linha_pred = QHBoxLayout()
        linha_pred.addWidget(QLabel("Predefinições"))
        self.combo_predefinicao = QComboBox()
        self.combo_predefinicao.activated.connect(self._carregar_predefinicao)
        linha_pred.addWidget(self.combo_predefinicao, 1)
        salvar = QToolButton()
        salvar.setText("Salvar")
        salvar.clicked.connect(self._salvar_predefinicao)
        excluir = QToolButton()
        excluir.setText("Excluir")
        excluir.clicked.connect(self._excluir_predefinicao)
        linha_pred.addWidget(salvar)
        linha_pred.addWidget(excluir)
        layout.addLayout(linha_pred)
        return painel

    def _combo_caixa(self) -> QComboBox:
        combo = QComboBox()
        for caixa in Caixa:
            combo.addItem(caixa.rotulo, caixa.value)
        combo.currentIndexChanged.connect(self._agendar)
        return combo

    def _criar_previa(self) -> QWidget:
        painel = QFrame()
        layout = QVBoxLayout(painel)
        layout.setContentsMargins(6, 0, 0, 0)
        barra = QHBoxLayout()
        for texto, dica, acao in (
            ("⤒", "Mover para o início", lambda: self._mover("inicio")),
            ("▲", "Mover para cima", lambda: self._mover(-1)),
            ("▼", "Mover para baixo", lambda: self._mover(+1)),
            ("⤓", "Mover para o fim", lambda: self._mover("fim")),
        ):
            botao = QToolButton()
            botao.setText(texto)
            botao.setToolTip(dica)
            botao.clicked.connect(acao)
            barra.addWidget(botao)
        ordenar = QToolButton()
        ordenar.setText("Ordenar por data")
        ordenar.clicked.connect(self.ordenar_por_data)
        barra.addWidget(ordenar)
        barra.addStretch(1)
        layout.addLayout(barra)

        self.tabela = QTableWidget(0, 4)
        self.tabela.setHorizontalHeaderLabels(["Nome antigo", "Novo nome", "Data usada", "Pasta"])
        self.tabela.verticalHeader().hide()
        self.tabela.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabela.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabela.setWordWrap(False)
        cab = self.tabela.horizontalHeader()
        cab.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        cab.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        cab.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.tabela.setColumnWidth(0, 260)
        self.tabela.setColumnWidth(1, 300)
        self.tabela.setColumnWidth(2, 170)
        self.tabela.cellDoubleClicked.connect(self._modelo_do_nome)
        self.tabela.setToolTip(
            "Clique duas vezes em um nome antigo para criar um modelo a partir dele"
        )
        layout.addWidget(self.tabela, 1)
        return painel

    # --- opções <-> tela ------------------------------------------------------------------

    def opcoes(self) -> OpcoesNome:
        substituir = self.grupo_substituir.isChecked()
        return OpcoesNome(
            mascara=self.campo_mascara.currentText(),
            inicio=self.spin_inicio.value(),
            etapa=self.spin_etapa.value(),
            reiniciar_por_dia=self.caixa_reiniciar.isChecked(),
            caixa_nome=Caixa(self.combo_caixa_nome.currentData()),
            caixa_extensao=Caixa(self.combo_caixa_extensao.currentData()),
            substituir=self.campo_substituir.text() if substituir else "",
            substituir_por=self.campo_com.text() if substituir else "",
            diferenciar_maiusculas=self.caixa_maiusculas.isChecked(),
            expressao_regular=self.caixa_regex.isChecked(),
            remover_acentos=self.caixa_acentos.isChecked(),
        )

    def definir_opcoes(self, o: OpcoesNome) -> None:
        self.campo_mascara.setEditText(o.mascara)
        self.spin_inicio.setValue(o.inicio)
        self.spin_etapa.setValue(o.etapa)
        self.caixa_reiniciar.setChecked(o.reiniciar_por_dia)
        self.combo_caixa_nome.setCurrentIndex(list(Caixa).index(o.caixa_nome))
        self.combo_caixa_extensao.setCurrentIndex(list(Caixa).index(o.caixa_extensao))
        self.grupo_substituir.setChecked(bool(o.substituir))
        self.campo_substituir.setText(o.substituir)
        self.campo_com.setText(o.substituir_por)
        self.caixa_maiusculas.setChecked(o.diferenciar_maiusculas)
        self.caixa_regex.setChecked(o.expressao_regular)
        self.caixa_acentos.setChecked(o.remover_acentos)
        self.atualizar_previa()

    def _inserir(self, texto: str) -> None:
        campo = self.campo_mascara.lineEdit()
        campo.insert(texto)
        campo.setFocus()

    def _modelo_do_nome(self, linha: int, coluna: int) -> None:
        if coluna == 0 and 0 <= linha < len(self.itens):
            self.campo_mascara.setEditText(self.itens[linha].midia.caminho.stem)

    # --- prévia ---------------------------------------------------------------------------

    def _agendar(self, *_args) -> None:
        self._timer.start()

    def atualizar_previa(self) -> None:
        self._timer.stop()
        self.plano = planejar(self.itens, self.opcoes())
        self.tabela.setRowCount(len(self.plano))
        vermelho, fraco = QColor(CORES["erro"]), QColor(CORES["texto_fraco"])
        for linha, p in enumerate(self.plano):
            data = formatar_data(p.data) if p.data else "—"
            if p.origem_data not in (OrigemData.ESCOLHIDA, OrigemData.NENHUMA):
                data += f"  ({p.origem_data.value})"
            valores = [p.origem.name, p.destino.name if p.ok else f"⚠ {p.problema}", data,
                       str(p.origem.parent)]  # fmt: skip
            for coluna, texto in enumerate(valores):
                item = QTableWidgetItem(texto)
                item.setToolTip(p.problema or texto)
                if not p.ok:
                    item.setForeground(vermelho)
                elif not p.muda and coluna == 1:
                    item.setForeground(fraco)
                self.tabela.setItem(linha, coluna, item)
        self._atualizar_resumo()

    def _atualizar_resumo(self) -> None:
        mudam = sum(1 for p in self.plano if p.ok and p.muda)
        problemas = sum(1 for p in self.plano if not p.ok)
        partes = [f"<b>{len(self.plano)}</b> arquivo(s)", f"<b>{mudam}</b> serão renomeados"]
        if problemas:
            partes.append(
                f"<span style='color:{CORES['erro']}'><b>{problemas}</b> com problema "
                "— corrija antes de renomear</span>"
            )
        self.resumo.setText(", ".join(partes))
        self.botao_renomear.setEnabled(mudam > 0 and problemas == 0)

    # --- ordem ----------------------------------------------------------------------------

    def _linhas_selecionadas(self) -> list[int]:
        return sorted({i.row() for i in self.tabela.selectedIndexes()})

    def _mover(self, passo) -> None:
        linhas = self._linhas_selecionadas()
        if not linhas:
            return
        selecionados = [self.itens[i] for i in linhas]
        restantes = [x for i, x in enumerate(self.itens) if i not in linhas]
        if passo == "inicio":
            destino = 0
        elif passo == "fim":
            destino = len(restantes)
        else:
            destino = max(0, min(len(restantes), linhas[0] + passo))
        self.itens = restantes[:destino] + selecionados + restantes[destino:]
        self.atualizar_previa()
        # Mantém os itens movidos selecionados, para poder continuar movendo.
        selecao = self.tabela.selectionModel()
        selecao.clearSelection()
        marcar = selecao.SelectionFlag.Select | selecao.SelectionFlag.Rows
        for linha in range(destino, destino + len(selecionados)):
            selecao.select(self.tabela.model().index(linha, 0), marcar)

    def ordenar_por_data(self) -> None:
        self.itens.sort(key=lambda x: (x.data is None, x.data.timestamp() if x.data else 0))
        self.atualizar_previa()

    # --- predefinições e histórico de máscaras ------------------------------------------------

    def _ler_json(self, chave: str, padrao):
        try:
            return json.loads(self.config.value(chave, json.dumps(padrao)))
        except (TypeError, ValueError):
            return padrao

    def _mascaras_recentes(self) -> list[str]:
        return [m for m in self._ler_json(CHAVE_HISTORICO_MASCARAS, []) if isinstance(m, str)]

    def _ultimas_opcoes(self) -> OpcoesNome:
        return OpcoesNome.de_dict(self._ler_json(CHAVE_ULTIMA, {}))

    def _recarregar_predefinicoes(self) -> None:
        self.combo_predefinicao.clear()
        self.combo_predefinicao.addItem("—", None)
        for nome in sorted(self._ler_json(CHAVE_PREDEFINICOES, {})):
            self.combo_predefinicao.addItem(nome, nome)

    def _carregar_predefinicao(self, indice: int) -> None:
        nome = self.combo_predefinicao.itemData(indice)
        salvas = self._ler_json(CHAVE_PREDEFINICOES, {})
        if nome in salvas:
            self.definir_opcoes(OpcoesNome.de_dict(salvas[nome]))

    def salvar_predefinicao(self, nome: str) -> None:
        salvas = self._ler_json(CHAVE_PREDEFINICOES, {})
        salvas[nome] = self.opcoes().para_dict()
        self.config.setValue(CHAVE_PREDEFINICOES, json.dumps(salvas, ensure_ascii=False))
        self._recarregar_predefinicoes()
        self.combo_predefinicao.setCurrentIndex(self.combo_predefinicao.findData(nome))

    def _salvar_predefinicao(self) -> None:
        nome, ok = QInputDialog.getText(self, "Salvar predefinição", "Nome da predefinição:")
        if ok and nome.strip():
            self.salvar_predefinicao(nome.strip())

    def _excluir_predefinicao(self) -> None:
        nome = self.combo_predefinicao.currentData()
        salvas = self._ler_json(CHAVE_PREDEFINICOES, {})
        if nome in salvas:
            del salvas[nome]
            self.config.setValue(CHAVE_PREDEFINICOES, json.dumps(salvas, ensure_ascii=False))
            self._recarregar_predefinicoes()

    def _aceitar(self) -> None:
        self.atualizar_previa()
        if not self.botao_renomear.isEnabled():
            return
        opcoes = self.opcoes()
        self.config.setValue(CHAVE_ULTIMA, json.dumps(opcoes.para_dict(), ensure_ascii=False))
        recentes = [opcoes.mascara] + [m for m in self._mascaras_recentes() if m != opcoes.mascara]
        self.config.setValue(
            CHAVE_HISTORICO_MASCARAS, json.dumps(recentes[:MAX_RECENTES], ensure_ascii=False)
        )
        self.accept()
