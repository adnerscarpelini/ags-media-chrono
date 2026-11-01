"""Utilitários para código que roda fora da thread da interface."""

from __future__ import annotations

from PySide6.QtCore import SignalInstance


def emitir(sinal: SignalInstance, *args) -> bool:
    """Emite um sinal a partir de uma thread de trabalho.

    Se o objeto dono do sinal já foi destruído (janela fechada enquanto a thread terminava),
    o PySide levanta RuntimeError; nesse caso o resultado simplesmente não interessa mais.
    """
    try:
        sinal.emit(*args)
        return True
    except RuntimeError:
        return False
