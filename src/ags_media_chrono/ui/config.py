"""Configurações persistentes do app (arquivo INI por usuário, igual no Windows e no Linux).

Windows: %APPDATA%\\AGS\ags-media-chrono.ini · Linux: ~/.config/AGS/ags-media-chrono.ini
"""

from __future__ import annotations

from PySide6.QtCore import QSettings


def configuracoes() -> QSettings:
    return QSettings(
        QSettings.Format.IniFormat, QSettings.Scope.UserScope, "AGS", "ags-media-chrono"
    )
