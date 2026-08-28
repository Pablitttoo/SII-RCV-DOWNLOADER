# -*- coding: utf-8 -*-
"""
Shim de compatibilidad hacia src.ai.glosa_extractor.
"""

import sys
from src.ai import glosa_extractor

sys.modules[__name__] = glosa_extractor
