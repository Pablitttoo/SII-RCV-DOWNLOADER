# -*- coding: utf-8 -*-
"""
Shim de compatibilidad hacia main.py y src.ui.
Permite ejecutar `python app.py` directamente de forma transparente.
"""

from main import main, AppSII

if __name__ == "__main__":
    main()
