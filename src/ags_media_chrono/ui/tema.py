"""Tema escuro profissional (estilo Lightroom/Bridge).

Usa o estilo Fusion do Qt, que desenha os widgets do mesmo jeito no Windows e no Linux,
mais uma QPalette escura e uma folha de estilo (QSS) para os detalhes.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

# Tokens de cor — use estes nomes no restante da UI em vez de valores soltos.
CORES = {
    "fundo": "#161616",  # área da galeria
    "painel": "#212121",  # painéis laterais, barras
    "painel_alto": "#2a2a2a",  # campos, botões
    "borda": "#333333",
    "borda_forte": "#454545",
    "texto": "#d6d6d6",
    "texto_fraco": "#8c8c8c",
    "texto_desativado": "#5c5c5c",
    "destaque": "#4a8fd8",  # seleção, foco
    "destaque_hover": "#5b9de3",
    "sucesso": "#5fb36b",
    "alerta": "#e0a43c",
    "erro": "#e05a5a",
}

QSS = """
* {{
    font-size: 13px;
}}
QMainWindow, QDialog {{
    background: {painel};
}}
QWidget {{
    color: {texto};
}}
QToolTip {{
    background: {painel_alto};
    color: {texto};
    border: 1px solid {borda_forte};
    padding: 4px 6px;
}}

/* Barras */
QMenuBar {{
    background: {painel};
    border-bottom: 1px solid {borda};
}}
QMenuBar::item {{
    padding: 4px 10px;
    background: transparent;
}}
QMenuBar::item:selected {{
    background: {painel_alto};
}}
QMenu {{
    background: {painel};
    border: 1px solid {borda_forte};
    padding: 4px 0;
}}
QMenu::item {{
    padding: 5px 24px 5px 20px;
}}
QMenu::item:selected {{
    background: {destaque};
    color: white;
}}
QMenu::item:disabled {{
    color: {texto_desativado};
}}
QMenu::separator {{
    height: 1px;
    background: {borda};
    margin: 4px 8px;
}}
QToolBar {{
    background: {painel};
    border: none;
    border-bottom: 1px solid {borda};
    padding: 4px 6px;
    spacing: 4px;
}}
QToolBar::separator {{
    width: 1px;
    background: {borda};
    margin: 4px 6px;
}}
QToolButton {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 4px 10px;
}}
QToolButton:hover {{
    background: {painel_alto};
    border-color: {borda_forte};
}}
QToolButton:pressed, QToolButton:checked {{
    background: {borda_forte};
}}
QToolButton:disabled {{
    color: {texto_desativado};
}}
QStatusBar {{
    background: {painel};
    border-top: 1px solid {borda};
    color: {texto_fraco};
}}
QStatusBar::item {{
    border: none;
}}

/* Painéis */
QSplitter::handle {{
    background: {borda};
}}
QSplitter::handle:hover {{
    background: {destaque};
}}
QFrame#painel {{
    background: {painel};
}}
QFrame#galeria {{
    background: {fundo};
}}
QLabel#tituloPainel {{
    color: {texto_fraco};
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 1px;
    padding: 8px 10px 6px 10px;
    border-bottom: 1px solid {borda};
}}
QLabel#vazio {{
    color: {texto_fraco};
}}
QLabel#vazioTitulo {{
    color: {texto};
    font-size: 16px;
}}

/* Botões */
QPushButton {{
    background: {painel_alto};
    border: 1px solid {borda_forte};
    border-radius: 4px;
    padding: 5px 14px;
}}
QPushButton:hover {{
    border-color: {destaque};
}}
QPushButton:pressed {{
    background: {borda_forte};
}}
QPushButton:disabled {{
    color: {texto_desativado};
    border-color: {borda};
}}
QPushButton#primario {{
    background: {destaque};
    border-color: {destaque};
    color: white;
}}
QPushButton#primario:hover {{
    background: {destaque_hover};
}}
QPushButton#primario:disabled {{
    background: {painel_alto};
    border-color: {borda};
    color: {texto_desativado};
}}

/* Campos */
QLineEdit, QSpinBox, QComboBox, QDateTimeEdit {{
    background: {fundo};
    border: 1px solid {borda_forte};
    border-radius: 3px;
    padding: 4px 6px;
    selection-background-color: {destaque};
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QDateTimeEdit:focus {{
    border-color: {destaque};
}}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 14px;
    height: 14px;
}}
QRadioButton::indicator {{
    border: 1px solid {texto_desativado};
    border-radius: 8px;
    background: {fundo};
}}
QRadioButton::indicator:hover {{
    border-color: {destaque};
}}
QRadioButton::indicator:checked {{
    border: 4px solid {destaque};
    background: white;
    width: 8px;
    height: 8px;
}}
QWidget#listaDatas {{
    background: {painel};
}}
QFrame#linhaData {{
    border-radius: 4px;
}}
QFrame#linhaData:hover {{
    background: {painel_alto};
}}
QLabel#detalheData {{
    color: {texto_fraco};
    font-size: 11px;
}}

/* Listas e árvores */
QTreeView, QListView, QTableView {{
    background: {painel};
    border: none;
    outline: none;
    selection-background-color: {destaque};
    selection-color: white;
}}
QFrame#barraGaleria {{
    background: {painel};
    border-bottom: 1px solid {borda};
}}
QToolButton#segmento {{
    border: 1px solid {borda_forte};
    border-radius: 4px;
    padding: 3px 12px;
}}
QToolButton#segmento:checked {{
    background: {destaque};
    border-color: {destaque};
    color: white;
}}
QComboBox QAbstractItemView {{
    background: {painel};
    border: 1px solid {borda_forte};
    selection-background-color: {destaque};
}}
QListView#grade {{
    background: {fundo};
    padding: 6px;
}}
QTreeView::item {{
    padding: 3px 2px;
}}
QTreeView::item:hover, QListView::item:hover {{
    background: {painel_alto};
}}
QTreeView::item:selected, QListView::item:selected {{
    background: {destaque};
    color: white;
}}
QHeaderView::section {{
    background: {painel};
    color: {texto_fraco};
    border: none;
    border-right: 1px solid {borda};
    border-bottom: 1px solid {borda};
    padding: 4px 6px;
}}

/* Barras de rolagem finas */
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 0;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 0;
}}
QScrollBar::handle {{
    background: {borda_forte};
    border-radius: 4px;
    min-height: 30px;
    min-width: 30px;
    margin: 2px;
}}
QScrollBar::handle:hover {{
    background: {texto_desativado};
}}
QScrollBar::add-line, QScrollBar::sub-line,
QScrollBar::add-page, QScrollBar::sub-page {{
    background: none;
    width: 0;
    height: 0;
}}

QSlider::groove:horizontal {{
    height: 4px;
    background: {borda_forte};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {texto};
    width: 12px;
    height: 12px;
    margin: -4px 0;
    border-radius: 6px;
}}
QSlider::sub-page:horizontal {{
    background: {destaque};
    border-radius: 2px;
}}
QProgressBar {{
    background: {fundo};
    border: 1px solid {borda};
    border-radius: 3px;
    text-align: center;
    height: 14px;
}}
QProgressBar::chunk {{
    background: {destaque};
    border-radius: 2px;
}}
"""


def _paleta() -> QPalette:
    c = {k: QColor(v) for k, v in CORES.items()}
    p = QPalette()
    p.setColor(QPalette.ColorRole.Window, c["painel"])
    p.setColor(QPalette.ColorRole.WindowText, c["texto"])
    p.setColor(QPalette.ColorRole.Base, c["fundo"])
    p.setColor(QPalette.ColorRole.AlternateBase, c["painel"])
    p.setColor(QPalette.ColorRole.ToolTipBase, c["painel_alto"])
    p.setColor(QPalette.ColorRole.ToolTipText, c["texto"])
    p.setColor(QPalette.ColorRole.PlaceholderText, c["texto_fraco"])
    p.setColor(QPalette.ColorRole.Text, c["texto"])
    p.setColor(QPalette.ColorRole.Button, c["painel_alto"])
    p.setColor(QPalette.ColorRole.ButtonText, c["texto"])
    p.setColor(QPalette.ColorRole.BrightText, QColor("white"))
    p.setColor(QPalette.ColorRole.Highlight, c["destaque"])
    p.setColor(QPalette.ColorRole.HighlightedText, QColor("white"))
    p.setColor(QPalette.ColorRole.Link, c["destaque"])
    p.setColor(QPalette.ColorRole.Mid, c["borda"])
    p.setColor(QPalette.ColorRole.Dark, c["fundo"])
    p.setColor(QPalette.ColorRole.Light, c["borda_forte"])
    for papel in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
    ):
        p.setColor(QPalette.ColorGroup.Disabled, papel, c["texto_desativado"])
    return p


def aplicar_tema(app: QApplication) -> None:
    # Faz a barra de título nativa (Windows 11 / Linux com suporte) também ficar escura.
    app.styleHints().setColorScheme(Qt.ColorScheme.Dark)
    app.setStyle("Fusion")
    app.setPalette(_paleta())
    app.setStyleSheet(QSS.format(**CORES))
