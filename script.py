# -*- coding: utf-8 -*-
"""
Shim de compatibilidad hacia src.core.rcv_engine.
"""

import sys
from src.core import rcv_engine

sys.modules[__name__] = rcv_engine
