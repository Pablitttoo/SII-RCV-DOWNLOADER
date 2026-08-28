#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Punto de entrada principal para el Gestor Tributario SII & Facturación.
"""

import os
import sys
import ctypes

# Asegurar ruta raíz en sys.path
DIRECTORIO_ACTUAL = os.path.dirname(os.path.abspath(__file__)) if not getattr(sys, 'frozen', False) else os.path.dirname(sys.executable)
if DIRECTORIO_ACTUAL not in sys.path:
    sys.path.insert(0, DIRECTORIO_ACTUAL)

from src.utils import cargar_variables_entorno
cargar_variables_entorno()

# Activar escalado DPI nítido y AppUserModelID para Windows
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

try:
    app_id = "sii.gestor.facturas.v2"
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID.argtypes = [ctypes.c_wchar_p]
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
except Exception:
    pass

from src.ui import AppSII


def main():
    """Inicializa y ejecuta la aplicación de escritorio."""
    app = AppSII()
    app.mainloop()


if __name__ == "__main__":
    main()
