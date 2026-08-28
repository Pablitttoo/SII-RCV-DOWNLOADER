"""
Módulo de interfaz de usuario (Tkinter / Deep Slate UI).
"""

from .theme import aplicar_estilos_ttk, C_CANVAS, C_SIDEBAR, C_PRIMARY, C_SUCCESS, C_WARNING, C_DANGER, C_INFO
from .app_window import AppSII
from .pdf_viewer import VentanaVisorPDF

__all__ = [
    "aplicar_estilos_ttk",
    "AppSII",
    "VentanaVisorPDF",
    "C_CANVAS",
    "C_SIDEBAR",
    "C_PRIMARY",
    "C_SUCCESS",
    "C_WARNING",
    "C_DANGER",
    "C_INFO",
]
