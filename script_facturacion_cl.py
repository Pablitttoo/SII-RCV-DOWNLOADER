# -*- coding: utf-8 -*-
"""
Shim de compatibilidad hacia src.core.desis_engine.
"""

import sys
from src.core import desis_engine

sys.modules[__name__] = desis_engine
