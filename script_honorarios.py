# -*- coding: utf-8 -*-
"""
Shim de compatibilidad hacia src.core.bhe_engine.
"""

import sys
from src.core import bhe_engine

sys.modules[__name__] = bhe_engine
